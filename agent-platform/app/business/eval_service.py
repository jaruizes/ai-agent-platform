from __future__ import annotations

import asyncio
import json
import re
import time
from statistics import mean
from typing import Any
from uuid import UUID, uuid4

from app.business.governance_runtime import (
    GovernanceRuntimeContext,
    reset_governance_context,
    set_governance_context,
)
from app.domain.evals import EVAL_METRICS, EvalDataset, EvalDefinition
from app.domain.execution import Command, ExecutionSubmission


class EvalService:
    def __init__(self, repository, execution_service, governance_service, model_gateway,
                 *, worker_poll_seconds: float = 2.0):
        self._repository = repository
        self._execution_service = execution_service
        self._governance_service = governance_service
        self._model_gateway = model_gateway
        self._worker_poll_seconds = worker_poll_seconds
        self._stop = asyncio.Event()

    async def list_datasets(self):
        return await self._repository.list_datasets()

    async def save_dataset(self, dataset: EvalDataset):
        if not dataset.name.strip():
            raise ValueError("Dataset name is required")
        if not dataset.items:
            raise ValueError("Dataset must contain at least one item")
        return await self._repository.save_dataset(dataset)

    async def delete_dataset(self, dataset_id: UUID):
        return await self._repository.delete_dataset(dataset_id)

    async def list_definitions(self):
        return await self._repository.list_definitions()

    async def save_definition(self, definition: EvalDefinition):
        dataset = await self._repository.get_dataset(definition.dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")
        unknown = set(definition.metrics) - EVAL_METRICS
        if unknown:
            raise ValueError("Unknown eval metrics: " + ", ".join(sorted(unknown)))
        for name, value in definition.thresholds.items():
            if name not in definition.metrics and name != "passRate":
                raise ValueError(f"Threshold '{name}' is not an enabled metric")
            if not 0 <= float(value) <= 1:
                raise ValueError(f"Threshold '{name}' must be between 0 and 1")
        if definition.metrics and not definition.judge_model_profile:
            raise ValueError("judgeModelProfile is required when LLM metrics are enabled")
        return await self._repository.save_definition(definition)

    async def delete_definition(self, definition_id: UUID):
        return await self._repository.delete_definition(definition_id)

    async def create_run(self, definition_id: UUID, baseline_run_id: UUID | None):
        definition = await self._repository.get_definition(definition_id)
        if not definition or not definition["enabled"]:
            raise ValueError("Enabled eval definition not found")
        if baseline_run_id:
            baseline = await self._repository.get_run(baseline_run_id)
            if not baseline or baseline["definitionId"] != definition_id:
                raise ValueError("Baseline run must belong to the same eval definition")
        snapshot = {
            "definition": {
                "name": definition["name"],
                "datasetId": str(definition["datasetId"]),
                "metrics": definition["metrics"],
                "thresholds": definition["thresholds"],
                "judgeModelProfile": definition["judgeModelProfile"],
            }
        }
        return await self._repository.create_run(
            run_id=uuid4(), definition=definition,
            baseline_run_id=baseline_run_id, configuration_snapshot=snapshot,
        )

    async def list_runs(self, definition_id: UUID | None = None):
        return await self._repository.list_runs(definition_id)

    async def get_run(self, run_id: UUID):
        return await self._repository.get_run(run_id)

    async def worker_loop(self):
        while not self._stop.is_set():
            run = await self._repository.claim_next_run()
            if not run:
                await asyncio.sleep(self._worker_poll_seconds)
                continue
            try:
                await self._execute_run(run)
            except Exception as exc:
                await self._repository.fail_run(
                    run["id"], {"type": type(exc).__name__, "message": str(exc)[:4000]}
                )

    async def stop(self):
        self._stop.set()

    async def _execute_run(self, run: dict[str, Any]):
        definition = await self._repository.get_definition(run["definitionId"])
        dataset = await self._repository.get_dataset(definition["datasetId"])
        score_rows: list[dict[str, float]] = []
        passed_cases = failed_cases = total_tokens = 0
        total_cost = 0.0

        for item in dataset["items"]:
            started = time.monotonic()
            execution_id = uuid4()
            command_data = item["command"]
            command = Command(
                name=command_data.get("name") or "eval-case",
                intent=command_data.get("intent") or "",
                input=command_data.get("input") or {},
                context=command_data.get("context") or {},
                instructions=command_data.get("instructions") or [],
                metadata={**(command_data.get("metadata") or {}), "evalRunId": str(run["id"])},
            )
            await self._execution_service.submit(
                ExecutionSubmission(
                    execution_id=execution_id, message_id=str(uuid4()),
                    correlation_id=f"eval:{run['id']}:{item['id']}",
                    source={"type": "eval", "name": definition["name"]},
                    session_id=None, command=command,
                )
            )
            execution = await self._wait_terminal(execution_id)
            latency_ms = int((time.monotonic() - started) * 1000)
            if execution["status"] != "COMPLETED":
                await self._repository.save_result(
                    run_id=run["id"], item_id=item["id"], execution_id=execution_id,
                    status=execution["status"], output=None, scores={}, checks=[],
                    passed=False, token_usage={}, cost_usd=0, latency_ms=latency_ms,
                    error=execution.get("error"),
                )
                failed_cases += 1
                continue

            output = self._output_text(execution.get("result"))
            checks = self._deterministic_checks(output, item.get("assertions") or [])
            scores = {}
            if definition["metrics"]:
                scores = await self._judge(
                    execution_id=execution_id, definition=definition, item=item,
                    output=output,
                )
            passed = all(x["passed"] for x in checks)
            for metric, threshold in (definition["thresholds"] or {}).items():
                if metric != "passRate" and scores.get(metric, 0) < float(threshold):
                    passed = False

            usage_summary = await self._governance_service.usage_summary(execution_id)
            totals = usage_summary.get("total") or {}
            case_tokens = int(totals.get("total_tokens") or 0)
            case_cost = float(totals.get("cost_usd") or 0)
            total_tokens += case_tokens
            total_cost += case_cost
            passed_cases += int(passed)
            failed_cases += int(not passed)
            score_rows.append(scores)
            await self._repository.save_result(
                run_id=run["id"], item_id=item["id"], execution_id=execution_id,
                status="COMPLETED", output=output, scores=scores, checks=checks,
                passed=passed, token_usage=totals, cost_usd=case_cost,
                latency_ms=latency_ms, error=None,
            )

        aggregate = {}
        for metric in definition["metrics"]:
            values = [row[metric] for row in score_rows if metric in row]
            aggregate[metric] = round(mean(values), 4) if values else 0.0
        aggregate["passRate"] = round(
            passed_cases / max(1, passed_cases + failed_cases), 4
        )
        regression = await self._regression(run, aggregate, definition["thresholds"])
        await self._repository.complete_run(
            run["id"], aggregate_scores=aggregate, regression=regression,
            passed_cases=passed_cases, failed_cases=failed_cases,
            total_tokens=total_tokens, total_cost_usd=total_cost,
        )

    async def _wait_terminal(self, execution_id: UUID):
        while not self._stop.is_set():
            execution = await self._execution_service.get_execution(execution_id)
            if execution and execution["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                return execution
            await asyncio.sleep(0.5)
        raise RuntimeError("Eval worker stopped")

    async def _judge(self, *, execution_id: UUID, definition, item, output: str):
        metrics = definition["metrics"]
        system = (
            "You are an evaluation judge. Score only the requested metrics from 0.0 to 1.0. "
            "Return strict JSON with a top-level 'scores' object and no markdown."
        )
        user = json.dumps({
            "metrics": metrics,
            "intent": (item.get("command") or {}).get("intent"),
            "expectedOutput": item.get("expectedOutput"),
            "actualOutput": output,
            "rubric": {
                "relevance": "Directly addresses the requested intent.",
                "completeness": "Covers the important expected information.",
                "groundedness": "Does not make unsupported claims relative to expected evidence.",
                "coherence": "Is internally consistent and understandable.",
                "instruction_adherence": "Follows explicit command instructions.",
            },
        }, ensure_ascii=False)
        token = set_governance_context(GovernanceRuntimeContext(
            execution_id=execution_id, step_id="__eval_judge__",
            session_scope=None, session_owner_key=None,
        ))
        try:
            detail = await self._model_gateway.complete_detailed(
                system_prompt=system, user_prompt=user,
                model_profile=definition["judgeModelProfile"],
                temperature=0.0, max_tokens=512,
            )
        finally:
            reset_governance_context(token)
        data = self._json_object(detail["content"])
        raw = data.get("scores") or {}
        return {m: max(0.0, min(1.0, float(raw.get(m, 0)))) for m in metrics}

    @staticmethod
    def _deterministic_checks(output: str, assertions: list[dict[str, Any]]):
        results = []
        for assertion in assertions:
            kind = str(assertion.get("type") or "").upper()
            value = assertion.get("value")
            passed = True
            if kind == "CONTAINS":
                passed = str(value).lower() in output.lower()
            elif kind == "NOT_CONTAINS":
                passed = str(value).lower() not in output.lower()
            elif kind == "REGEX":
                passed = re.search(str(value), output, flags=re.I | re.M) is not None
            elif kind == "MAX_LENGTH":
                passed = len(output) <= int(value)
            elif kind == "MIN_LENGTH":
                passed = len(output) >= int(value)
            elif kind:
                passed = False
            results.append({"type": kind, "value": value, "passed": passed})
        return results

    async def _regression(self, run, aggregate, thresholds):
        baseline_id = run.get("baselineRunId")
        result = {"baselineRunId": str(baseline_id) if baseline_id else None,
                  "regressed": False, "deltas": {}, "violations": []}
        for metric, threshold in (thresholds or {}).items():
            actual = aggregate.get(metric, 0)
            if actual < float(threshold):
                result["violations"].append({
                    "metric": metric, "actual": actual, "threshold": float(threshold)
                })
        if baseline_id:
            baseline = await self._repository.get_run(baseline_id)
            for metric, actual in aggregate.items():
                previous = float((baseline["aggregateScores"] or {}).get(metric, 0))
                result["deltas"][metric] = round(actual - previous, 4)
        result["regressed"] = bool(result["violations"]) or any(
            delta < 0 for delta in result["deltas"].values()
        )
        return result

    @staticmethod
    def _output_text(result: Any) -> str:
        if not result:
            return ""
        if isinstance(result, str):
            return result
        return str(result.get("summary") or json.dumps(result, ensure_ascii=False))

    @staticmethod
    def _json_object(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Eval judge must return a JSON object")
        return data
