from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.domain.evals import EvalDataset, EvalDatasetItem, EvalDefinition


class PostgresEvalRepository:
    def __init__(self, database):
        self._database = database

    async def list_datasets(self) -> list[dict[str, Any]]:
        rows = await self._database.require_pool().fetch(
            "SELECT * FROM eval_datasets ORDER BY name, version DESC"
        )
        return [await self._dataset_row(row, include_items=True) for row in rows]

    async def get_dataset(self, dataset_id: UUID) -> dict[str, Any] | None:
        row = await self._database.require_pool().fetchrow(
            "SELECT * FROM eval_datasets WHERE id=$1", dataset_id
        )
        return await self._dataset_row(row, include_items=True) if row else None

    async def save_dataset(self, dataset: EvalDataset) -> dict[str, Any]:
        pool = self._database.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow(
                    "SELECT * FROM eval_datasets WHERE name=$1 AND version=$2",
                    dataset.name, dataset.version,
                )
                if existing:
                    used = await conn.fetchval(
                        """
                        SELECT EXISTS(
                          SELECT 1 FROM eval_results r
                          JOIN eval_dataset_items i ON i.id=r.dataset_item_id
                          WHERE i.dataset_id=$1
                        )
                        """,
                        existing["id"],
                    )
                    if used:
                        raise ValueError(
                            "Dataset version is immutable after it has been used by an eval run; create a new version."
                        )
                    dataset_id = existing["id"]
                    await conn.execute(
                        """
                        UPDATE eval_datasets SET description=$2,enabled=$3,updated_at=now()
                        WHERE id=$1
                        """,
                        dataset_id, dataset.description, dataset.enabled,
                    )
                    await conn.execute(
                        "DELETE FROM eval_dataset_items WHERE dataset_id=$1", dataset_id
                    )
                else:
                    dataset_id = dataset.id
                    await conn.execute(
                        """
                        INSERT INTO eval_datasets(id,name,description,version,enabled)
                        VALUES($1,$2,$3,$4,$5)
                        """,
                        dataset_id, dataset.name, dataset.description,
                        dataset.version, dataset.enabled,
                    )
                for item in dataset.items:
                    await conn.execute(
                        """
                        INSERT INTO eval_dataset_items(
                          id,dataset_id,name,command,expected_output,assertions,tags
                        ) VALUES($1,$2,$3,$4::jsonb,$5,$6::jsonb,$7::jsonb)
                        """,
                        item.id, dataset_id, item.name,
                        json.dumps(item.command), item.expected_output,
                        json.dumps(item.assertions), json.dumps(item.tags),
                    )
        return await self.get_dataset(dataset_id)

    async def delete_dataset(self, dataset_id: UUID) -> bool:
        result = await self._database.require_pool().execute(
            "DELETE FROM eval_datasets WHERE id=$1", dataset_id
        )
        return result.endswith("1")

    async def list_definitions(self) -> list[dict[str, Any]]:
        rows = await self._database.require_pool().fetch(
            """
            SELECT d.*, ds.name dataset_name
            FROM eval_definitions d JOIN eval_datasets ds ON ds.id=d.dataset_id
            ORDER BY d.name
            """
        )
        return [self._definition_row(row) for row in rows]

    async def get_definition(self, definition_id: UUID) -> dict[str, Any] | None:
        row = await self._database.require_pool().fetchrow(
            """
            SELECT d.*, ds.name dataset_name
            FROM eval_definitions d JOIN eval_datasets ds ON ds.id=d.dataset_id
            WHERE d.id=$1
            """,
            definition_id,
        )
        return self._definition_row(row) if row else None

    async def save_definition(self, definition: EvalDefinition) -> dict[str, Any]:
        await self._database.require_pool().execute(
            """
            INSERT INTO eval_definitions(
              id,name,description,dataset_id,metrics,thresholds,judge_model_profile,enabled
            ) VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8)
            ON CONFLICT(name) DO UPDATE SET
              description=EXCLUDED.description,
              dataset_id=EXCLUDED.dataset_id,
              metrics=EXCLUDED.metrics,
              thresholds=EXCLUDED.thresholds,
              judge_model_profile=EXCLUDED.judge_model_profile,
              enabled=EXCLUDED.enabled,
              updated_at=now()
            """,
            definition.id, definition.name, definition.description,
            definition.dataset_id, json.dumps(definition.metrics),
            json.dumps(definition.thresholds), definition.judge_model_profile,
            definition.enabled,
        )
        row = await self._database.require_pool().fetchrow(
            "SELECT id FROM eval_definitions WHERE name=$1", definition.name
        )
        return await self.get_definition(row["id"])

    async def delete_definition(self, definition_id: UUID) -> bool:
        result = await self._database.require_pool().execute(
            "DELETE FROM eval_definitions WHERE id=$1", definition_id
        )
        return result.endswith("1")

    async def create_run(
        self, *, run_id: UUID, definition: dict[str, Any],
        baseline_run_id: UUID | None, configuration_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        dataset = await self.get_dataset(definition["datasetId"])
        await self._database.require_pool().execute(
            """
            INSERT INTO eval_runs(
              id,definition_id,baseline_run_id,dataset_version,
              configuration_snapshot,total_cases
            ) VALUES($1,$2,$3,$4,$5::jsonb,$6)
            """,
            run_id, definition["id"], baseline_run_id,
            dataset["version"], json.dumps(configuration_snapshot),
            len(dataset["items"]),
        )
        return await self.get_run(run_id)

    async def claim_next_run(self) -> dict[str, Any] | None:
        pool = self._database.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT * FROM eval_runs
                    WHERE status='PENDING'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED LIMIT 1
                    """
                )
                if not row:
                    return None
                await conn.execute(
                    "UPDATE eval_runs SET status='RUNNING',started_at=now() WHERE id=$1",
                    row["id"],
                )
        return await self.get_run(row["id"])

    async def save_result(self, *, run_id: UUID, item_id: UUID,
                          execution_id: UUID | None, status: str,
                          output: str | None, scores: dict[str, float],
                          checks: list[dict[str, Any]], passed: bool,
                          token_usage: dict[str, Any], cost_usd: float,
                          latency_ms: int, error: dict[str, Any] | None) -> None:
        from uuid import uuid4
        await self._database.require_pool().execute(
            """
            INSERT INTO eval_results(
              id,run_id,dataset_item_id,execution_id,status,output,scores,checks,
              passed,token_usage,cost_usd,latency_ms,error
            ) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10::jsonb,$11,$12,$13::jsonb)
            ON CONFLICT(run_id,dataset_item_id) DO UPDATE SET
              execution_id=EXCLUDED.execution_id,status=EXCLUDED.status,
              output=EXCLUDED.output,scores=EXCLUDED.scores,checks=EXCLUDED.checks,
              passed=EXCLUDED.passed,token_usage=EXCLUDED.token_usage,
              cost_usd=EXCLUDED.cost_usd,latency_ms=EXCLUDED.latency_ms,error=EXCLUDED.error
            """,
            uuid4(), run_id, item_id, execution_id, status, output,
            json.dumps(scores), json.dumps(checks), passed, json.dumps(token_usage),
            cost_usd, latency_ms, json.dumps(error) if error else None,
        )

    async def complete_run(self, run_id: UUID, *, aggregate_scores: dict[str, float],
                           regression: dict[str, Any], passed_cases: int,
                           failed_cases: int, total_tokens: int,
                           total_cost_usd: float) -> None:
        await self._database.require_pool().execute(
            """
            UPDATE eval_runs SET status='COMPLETED',aggregate_scores=$2::jsonb,
              regression=$3::jsonb,passed_cases=$4,failed_cases=$5,total_tokens=$6,
              total_cost_usd=$7,completed_at=now()
            WHERE id=$1
            """,
            run_id, json.dumps(aggregate_scores), json.dumps(regression),
            passed_cases, failed_cases, total_tokens, total_cost_usd,
        )

    async def fail_run(self, run_id: UUID, error: dict[str, Any]) -> None:
        await self._database.require_pool().execute(
            "UPDATE eval_runs SET status='FAILED',error=$2::jsonb,completed_at=now() WHERE id=$1",
            run_id, json.dumps(error),
        )

    async def list_runs(self, definition_id: UUID | None = None) -> list[dict[str, Any]]:
        if definition_id:
            rows = await self._database.require_pool().fetch(
                "SELECT * FROM eval_runs WHERE definition_id=$1 ORDER BY created_at DESC",
                definition_id,
            )
        else:
            rows = await self._database.require_pool().fetch(
                "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 200"
            )
        return [await self._run_row(row, include_results=False) for row in rows]

    async def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        row = await self._database.require_pool().fetchrow(
            "SELECT * FROM eval_runs WHERE id=$1", run_id
        )
        return await self._run_row(row, include_results=True) if row else None

    async def _dataset_row(self, row, *, include_items: bool) -> dict[str, Any]:
        result = {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "version": row["version"], "enabled": row["enabled"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }
        if include_items:
            items = await self._database.require_pool().fetch(
                "SELECT * FROM eval_dataset_items WHERE dataset_id=$1 ORDER BY created_at,id",
                row["id"],
            )
            result["items"] = [{
                "id": x["id"], "name": x["name"], "command": x["command"],
                "expectedOutput": x["expected_output"], "assertions": x["assertions"],
                "tags": x["tags"],
            } for x in items]
        return result

    @staticmethod
    def _definition_row(row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "datasetId": row["dataset_id"], "datasetName": row["dataset_name"],
            "metrics": row["metrics"], "thresholds": row["thresholds"],
            "judgeModelProfile": row["judge_model_profile"], "enabled": row["enabled"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    async def _run_row(self, row, *, include_results: bool) -> dict[str, Any]:
        result = {
            "id": row["id"], "definitionId": row["definition_id"],
            "baselineRunId": row["baseline_run_id"], "status": row["status"],
            "datasetVersion": row["dataset_version"],
            "configurationSnapshot": row["configuration_snapshot"],
            "aggregateScores": row["aggregate_scores"], "regression": row["regression"],
            "totalCases": row["total_cases"], "passedCases": row["passed_cases"],
            "failedCases": row["failed_cases"], "totalTokens": row["total_tokens"],
            "totalCostUsd": row["total_cost_usd"], "error": row["error"],
            "createdAt": row["created_at"], "startedAt": row["started_at"],
            "completedAt": row["completed_at"],
        }
        if include_results:
            rows = await self._database.require_pool().fetch(
                """
                SELECT r.*, i.name item_name FROM eval_results r
                JOIN eval_dataset_items i ON i.id=r.dataset_item_id
                WHERE r.run_id=$1 ORDER BY r.created_at
                """,
                row["id"],
            )
            result["results"] = [{
                "id": x["id"], "datasetItemId": x["dataset_item_id"],
                "itemName": x["item_name"], "executionId": x["execution_id"],
                "status": x["status"], "output": x["output"], "scores": x["scores"],
                "checks": x["checks"], "passed": x["passed"],
                "tokenUsage": x["token_usage"], "costUsd": x["cost_usd"],
                "latencyMs": x["latency_ms"], "error": x["error"],
            } for x in rows]
        return result
