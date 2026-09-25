from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from app.business.context_engine import ContextEngine
from app.business.governance_runtime import (
    get_governance_context,
    reset_governance_context,
    set_governance_context,
)
from app.business.knowledge_service import KnowledgeService
from app.business.ports import (
    CatalogRepositoryPort,
    ExecutionRepositoryPort,
    ModelGatewayPort,
)
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.domain.execution import Command
from app.domain.governance import GovernanceBudgetExceeded, GovernanceDenied
from app.domain.orchestration import (
    OrchestrationCancelled,
    OrchestrationSuspended,
    PlanStep,
)


_PLACEHOLDER = re.compile(r"^\$\{([^}]+)\}$")


class StepExecutor:
    def __init__(
        self,
        *,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        tool_service: ToolService,
        knowledge_service: KnowledgeService,
        model_gateway: ModelGatewayPort,
        execution_repository: ExecutionRepositoryPort,
        context_engine: ContextEngine,
        governance_service,
        execution_model_profile: str,
        knowledge_top_k: int,
        max_context_chars: int,
        control_poll_seconds: float = 0.5,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._knowledge_service = knowledge_service
        self._model_gateway = model_gateway
        self._repository = execution_repository
        self._context_engine = context_engine
        self._governance_service = governance_service
        self._execution_model_profile = execution_model_profile
        self._knowledge_top_k = knowledge_top_k
        self._max_context_chars = max_context_chars
        self._control_poll_seconds = control_poll_seconds

    async def execute(
        self,
        *,
        execution: dict[str, Any],
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        checkpoint = await self._repository.get_step_checkpoint(
            execution["id"],
            step.id,
        )
        if checkpoint and checkpoint["status"] == "COMPLETED":
            return checkpoint["output"]

        await self._check_control(execution)

        effective_requires_approval = step.requires_approval
        effective_reason = (
            step.approval_reason
            or f"Human approval is required before step '{step.id}'."
        )

        governance_approval = await self._governance_service.enforce_step(
            execution,
            step,
            execution_model_profile=self._execution_model_profile,
        )
        if governance_approval is not None:
            effective_requires_approval = True
            effective_reason = governance_approval.reason
            if not checkpoint or not checkpoint.get("requires_approval"):
                await self._repository.enforce_step_approval_policy(
                    execution,
                    step_id=step.id,
                    reason=effective_reason,
                    approval_source="GOVERNANCE_POLICY",
                    tool_side_effect=step.tool_side_effect or "",
                    tool_approval_policy=step.tool_approval_policy or "",
                )
                checkpoint = await self._repository.get_step_checkpoint(
                    execution["id"],
                    step.id,
                )

        if step.type == "TOOL" and step.tool_name:
            tool = await self._tool_service.get_tool_by_name(step.tool_name)
            if not tool or not tool.enabled:
                raise LookupError(
                    f"Tool '{step.tool_name}' not found or disabled"
                )
            if tool.approval_policy.upper() == "REQUIRED":
                effective_requires_approval = True
                effective_reason = (
                    step.approval_reason
                    or f"Tool '{tool.name}' requires human approval "
                    f"by deterministic platform policy."
                )
                if not checkpoint or not checkpoint.get("requires_approval"):
                    await self._repository.enforce_step_approval_policy(
                        execution,
                        step_id=step.id,
                        reason=effective_reason,
                        approval_source="TOOL_POLICY",
                        tool_side_effect=tool.side_effect,
                        tool_approval_policy=tool.approval_policy,
                    )
                    checkpoint = await self._repository.get_step_checkpoint(
                        execution["id"],
                        step.id,
                    )

        if effective_requires_approval:
            approval_status = (
                checkpoint.get("approval_status") if checkpoint else "PENDING"
            )
            if approval_status != "APPROVED":
                await self._repository.mark_step_waiting_approval(
                    execution,
                    step_id=step.id,
                    reason=effective_reason,
                )
                raise OrchestrationSuspended(
                    "WAITING_APPROVAL",
                    effective_reason,
                )

        if checkpoint and checkpoint.get("next_retry_at"):
            await self._wait_until_retry(checkpoint["next_retry_at"], execution)

        retry_policy = {
            "maxAttempts": max(
                1,
                int((step.retry_policy or {}).get("maxAttempts", 3)),
            ),
            "initialBackoffSeconds": max(
                0.0,
                float(
                    (step.retry_policy or {}).get("initialBackoffSeconds", 1.0)
                ),
            ),
            "maxBackoffSeconds": max(
                0.0,
                float((step.retry_policy or {}).get("maxBackoffSeconds", 30.0)),
            ),
            "multiplier": max(
                1.0,
                float((step.retry_policy or {}).get("multiplier", 2.0)),
            ),
        }

        checkpoint = await self._repository.get_step_checkpoint(
            execution["id"],
            step.id,
        )
        attempts_already = int((checkpoint or {}).get("attempt_count") or 0)
        max_attempts = retry_policy["maxAttempts"]

        while attempts_already < max_attempts:
            await self._check_control(execution)
            attempt = await self._repository.mark_step_attempt(
                execution,
                step_id=step.id,
            )
            attempts_already = attempt

            await self._repository.mark_step_started(
                execution,
                step_id=step.id,
                detail={
                    "type": step.type,
                    "description": step.description,
                    "agent": step.agent_name,
                    "tool": step.tool_name,
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "timeoutSeconds": step.timeout_seconds,
                    "idempotencyKey": f"{execution['id']}:{step.id}",
                },
            )

            governance_context = get_governance_context()
            governance_step_token = None
            if governance_context is not None:
                governance_step_token = set_governance_context(
                    replace(
                        governance_context,
                        step_id=step.id,
                        agent_name=step.agent_name,
                    )
                )
            try:
                result = await self._run_with_controls(
                    execution=execution,
                    timeout_seconds=step.timeout_seconds,
                    operation=self._dispatch(
                        execution=execution,
                        attempt=attempt,
                        command=command,
                        step=step,
                        previous_results=previous_results,
                    ),
                )
                result.setdefault(
                    "durability",
                    {
                        "attempt": attempt,
                        "maxAttempts": max_attempts,
                        "idempotencyKey": f"{execution['id']}:{step.id}",
                    },
                )
                await self._repository.mark_step_completed(
                    execution,
                    step_id=step.id,
                    output=result,
                    usage=result.get("usage") or {},
                )
                return result
            except (OrchestrationSuspended, OrchestrationCancelled):
                raise
            except Exception as exc:
                error = {
                    "type": type(exc).__name__,
                    "message": str(exc)[:4000],
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "retryable": self._is_retryable(exc),
                }

                if attempt < max_attempts and error["retryable"]:
                    delay = min(
                        retry_policy["maxBackoffSeconds"],
                        retry_policy["initialBackoffSeconds"]
                        * (retry_policy["multiplier"] ** (attempt - 1)),
                    )
                    await self._repository.mark_step_retrying(
                        execution,
                        step_id=step.id,
                        error=error,
                        delay_seconds=delay,
                    )
                    await self._controlled_sleep(delay, execution)
                    continue

                await self._repository.mark_step_failed(
                    execution,
                    step_id=step.id,
                    error=error,
                )
                raise
            finally:
                if governance_step_token is not None:
                    reset_governance_context(governance_step_token)

        raise RuntimeError(
            f"Step '{step.id}' exhausted its retry attempts without a result"
        )

    async def _dispatch(
        self,
        *,
        execution: dict[str, Any],
        attempt: int,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        if step.type == "TOOL":
            return await self._tool_step(command, step, previous_results)
        if step.type == "KNOWLEDGE":
            return await self._knowledge_step(command, step, previous_results)
        if step.type == "AGENT":
            return await self._agent_step(
                execution, attempt, command, step, previous_results
            )
        if step.type == "VALIDATE":
            return await self._validation_step(
                execution, attempt, command, step, previous_results
            )
        return await self._model_step(
            execution, attempt, command, step, previous_results
        )

    async def _run_with_controls(
        self,
        *,
        execution: dict[str, Any],
        timeout_seconds: float,
        operation,
    ) -> dict[str, Any]:
        task = asyncio.create_task(operation)
        deadline = time.monotonic() + max(0.1, timeout_seconds)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise TimeoutError(
                        f"Step timed out after {timeout_seconds} seconds"
                    )

                done, _ = await asyncio.wait(
                    {task},
                    timeout=min(self._control_poll_seconds, remaining),
                )
                if task in done:
                    return task.result()

                await self._check_control(execution)
        except (OrchestrationSuspended, OrchestrationCancelled):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise

    async def _check_control(self, execution: dict[str, Any]) -> None:
        control = await self._repository.get_control(execution["id"])
        action = control.get("control_action")
        reason = control.get("control_reason") or "Requested by operator"
        if action == "CANCEL" or control.get("status") == "CANCELLING":
            raise OrchestrationCancelled(reason)
        if action == "PAUSE" or control.get("status") == "PAUSING":
            raise OrchestrationSuspended("PAUSED", reason)

    async def _controlled_sleep(
        self,
        seconds: float,
        execution: dict[str, Any],
    ) -> None:
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(self._control_poll_seconds, remaining))
            await self._check_control(execution)

    async def _wait_until_retry(
        self,
        retry_at: datetime,
        execution: dict[str, Any],
    ) -> None:
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
        if seconds > 0:
            await self._controlled_sleep(seconds, execution)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        return not isinstance(
            exc,
            (ValueError, LookupError, GovernanceDenied, GovernanceBudgetExceeded),
        )

    async def _tool_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = self._resolve_value(
            step.tool_arguments,
            command=command,
            previous_results=previous_results,
        )
        output = await self._tool_service.execute(step.tool_name, arguments)
        return {
            "summary": f"Tool '{step.tool_name}' completed.",
            "output": output,
            "usage": {},
            "agent": None,
            "tool": step.tool_name,
        }

    async def _knowledge_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        query = self._retrieval_input(command, step, previous_results)
        hits = await self._knowledge_service.retrieve(
            query=query,
            knowledge_base_names=step.knowledge_base_names,
            top_k=self._knowledge_top_k,
        )
        return {
            "summary": f"Retrieved {len(hits)} knowledge chunks.",
            "output": {
                "knowledgeBases": step.knowledge_base_names,
                "usageMode": step.knowledge_usage_mode,
                "hits": [
                    {
                        "chunkId": str(hit.chunk_id),
                        "documentId": str(hit.document_id),
                        "documentName": hit.document_name,
                        "score": hit.score,
                        "metadata": hit.metadata,
                        "content": hit.content,
                    }
                    for hit in hits
                ],
            },
            "usage": {},
            "agent": None,
            "tool": None,
        }

    async def _agent_step(
        self,
        execution: dict[str, Any],
        attempt: int,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        agent = await self._catalog.get_agent_by_name(step.agent_name)
        if not agent or not agent.enabled:
            raise LookupError(f"Agent '{step.agent_name}' not found or disabled")

        knowledge_context = ""
        if step.knowledge_base_names:
            hits = await self._knowledge_service.retrieve(
                query=self._retrieval_input(command, step, previous_results),
                knowledge_base_names=step.knowledge_base_names,
                top_k=self._knowledge_top_k,
            )
            knowledge_context = (
                "\n\nManaged knowledge:\n"
                + self._knowledge_service.format_context(hits)
            )

        prompt = await self._prompt_service.get_by_name(
            "agent-knowledge-executor"
            if step.knowledge_base_names
            else "agent-executor"
        )
        system_prompt = prompt.content.format(
            agent_name=agent.name,
            agent_description=agent.description,
            agent_instructions=agent.instructions,
            skills=self._skills_text(agent),
        )
        effective = await self._context_engine.build(
            execution=execution,
            command=command,
            step=step,
            previous_results=previous_results,
            system_prompt=system_prompt,
            model_profile=self._execution_model_profile,
            attempt=attempt,
            additional_memory_scopes=[
                ("AGENT", agent.name),
                ("AGENT", str(agent.id)),
            ],
            knowledge_context=knowledge_context,
            knowledge_provenance=(
                [
                    {
                        "type": "KNOWLEDGE",
                        "chunkId": str(hit.chunk_id),
                        "documentId": str(hit.document_id),
                        "documentName": hit.document_name,
                        "score": hit.score,
                    }
                    for hit in hits
                ]
                if step.knowledge_base_names
                else []
            ),
        )
        detail = await self._model_gateway.complete_detailed(
            system_prompt=effective.system_prompt,
            user_prompt=effective.user_prompt,
            model_profile=self._execution_model_profile,
            temperature=0.2,
            timeout_seconds=step.timeout_seconds,
        )
        return {
            "summary": detail["content"],
            "output": {"content": detail["content"]},
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "requestedModelProfile": detail.get("requestedModelProfile"),
            "governance": detail.get("governance"),
            "agent": agent.name,
            "tool": None,
            "context": {
                "promptTokenEstimate": effective.prompt_token_estimate,
                "selectedTokenEstimate": effective.selected_token_estimate,
                "droppedTokenEstimate": effective.dropped_token_estimate,
                "compressed": effective.compressed,
            },
        }

    async def _model_step(
        self,
        execution: dict[str, Any],
        attempt: int,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = await self._prompt_service.get_by_name("direct-executor")
        effective = await self._context_engine.build(
            execution=execution,
            command=command,
            step=step,
            previous_results=previous_results,
            system_prompt=prompt.content,
            model_profile=self._execution_model_profile,
            attempt=attempt,
        )
        detail = await self._model_gateway.complete_detailed(
            system_prompt=effective.system_prompt,
            user_prompt=effective.user_prompt,
            model_profile=self._execution_model_profile,
            temperature=0.2,
            timeout_seconds=step.timeout_seconds,
        )
        return {
            "summary": detail["content"],
            "output": {"content": detail["content"]},
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "requestedModelProfile": detail.get("requestedModelProfile"),
            "governance": detail.get("governance"),
            "agent": None,
            "tool": None,
            "context": {
                "promptTokenEstimate": effective.prompt_token_estimate,
                "selectedTokenEstimate": effective.selected_token_estimate,
                "droppedTokenEstimate": effective.dropped_token_estimate,
                "compressed": effective.compressed,
            },
        }

    async def _validation_step(
        self,
        execution: dict[str, Any],
        attempt: int,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        hits = await self._knowledge_service.retrieve(
            query=self._retrieval_input(command, step, previous_results),
            knowledge_base_names=step.knowledge_base_names,
            top_k=self._knowledge_top_k,
        )
        prompt = await self._prompt_service.get_by_name("validation-executor")
        knowledge_context = (
            "Knowledge usage mode: "
            + step.knowledge_usage_mode
            + "\n\n"
            + self._knowledge_service.format_context(hits)
        )
        effective = await self._context_engine.build(
            execution=execution,
            command=command,
            step=step,
            previous_results=previous_results,
            system_prompt=prompt.content,
            model_profile=self._execution_model_profile,
            attempt=attempt,
            knowledge_context=knowledge_context,
            knowledge_provenance=[
                {
                    "type": "KNOWLEDGE",
                    "chunkId": str(hit.chunk_id),
                    "documentId": str(hit.document_id),
                    "documentName": hit.document_name,
                    "score": hit.score,
                }
                for hit in hits
            ],
        )
        detail = await self._model_gateway.complete_detailed(
            system_prompt=effective.system_prompt,
            user_prompt=effective.user_prompt,
            model_profile=self._execution_model_profile,
            temperature=0.0,
            timeout_seconds=step.timeout_seconds,
        )
        return {
            "summary": detail["content"],
            "output": {
                "content": detail["content"],
                "knowledgeBases": step.knowledge_base_names,
                "knowledgeHits": [
                    {
                        "chunkId": str(hit.chunk_id),
                        "documentId": str(hit.document_id),
                        "documentName": hit.document_name,
                        "score": hit.score,
                    }
                    for hit in hits
                ],
            },
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "requestedModelProfile": detail.get("requestedModelProfile"),
            "governance": detail.get("governance"),
            "agent": None,
            "tool": None,
            "context": {
                "promptTokenEstimate": effective.prompt_token_estimate,
                "selectedTokenEstimate": effective.selected_token_estimate,
                "droppedTokenEstimate": effective.dropped_token_estimate,
                "compressed": effective.compressed,
            },
        }

    def _retrieval_input(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> str:
        dependencies: dict[str, Any] = {}
        for dependency in step.depends_on:
            value = previous_results.get(dependency)
            if isinstance(value, dict):
                dependencies[dependency] = (
                    value.get("summary")
                    or (value.get("output") or {}).get("content")
                    or str(value)
                )
            elif value is not None:
                dependencies[dependency] = str(value)

        payload = {
            "task": step.description,
            "intent": command.intent,
            "input": command.input,
            "context": command.context,
            "dependencySummaries": dependencies,
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )
        # Retrieval queries are intentionally compact. Large source material belongs
        # to Knowledge/Artifacts and is selected later by ContextEngine.
        return serialized[: min(self._max_context_chars, 8000)]

    def _resolve_value(
        self,
        value: Any,
        *,
        command: Command,
        previous_results: dict[str, Any],
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: self._resolve_value(
                    item,
                    command=command,
                    previous_results=previous_results,
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve_value(
                    item,
                    command=command,
                    previous_results=previous_results,
                )
                for item in value
            ]
        if not isinstance(value, str):
            return value

        match = _PLACEHOLDER.match(value)
        if not match:
            return value

        path = match.group(1).split(".")
        root: Any = {
            "command": {
                "input": command.input,
                "context": command.context,
                "intent": command.intent,
            },
            "steps": previous_results,
        }
        for part in path:
            if isinstance(root, list):
                root = root[int(part)]
            elif isinstance(root, dict) and part in root:
                root = root[part]
            else:
                raise ValueError(f"Cannot resolve plan placeholder '{value}'")
        return root

    @staticmethod
    def _skills_text(agent) -> str:
        value = "\n\n".join(
            f"### Skill: {skill.name}\n{skill.description}\n\n{skill.instructions}"
            for skill in agent.skills
            if skill.enabled
        )
        return value or "No skills assigned."
