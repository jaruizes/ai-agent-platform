import asyncio
import json
import logging
from dataclasses import replace
from typing import Any
from uuid import UUID

from opentelemetry import trace

from app.business.intent_resolver import IntentResolver
from app.business.ports import EventPublisherPort, ExecutionRepositoryPort, ModelGatewayPort
from app.business.tool_service import ToolService
from app.domain.execution import Command, ExecutionSubmission


tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        repository: ExecutionRepositoryPort,
        resolver: IntentResolver,
        model_gateway: ModelGatewayPort,
        tool_service: ToolService,
        event_publisher: EventPublisherPort,
        *,
        worker_poll_seconds: float,
        outbox_poll_seconds: float,
    ):
        self._repository = repository
        self._resolver = resolver
        self._model_gateway = model_gateway
        self._tool_service = tool_service
        self._event_publisher = event_publisher
        self._worker_poll_seconds = worker_poll_seconds
        self._outbox_poll_seconds = outbox_poll_seconds
        self._stop = asyncio.Event()

    async def submit(self, submission: ExecutionSubmission) -> tuple[UUID, bool]:
        return await self._repository.create_execution(submission)

    async def get_execution(self, execution_id: UUID) -> dict[str, Any] | None:
        return await self._repository.get(execution_id)

    async def worker_loop(self) -> None:
        while not self._stop.is_set():
            execution = await self._repository.claim_next()
            if not execution:
                await asyncio.sleep(self._worker_poll_seconds)
                continue
            await self._execute(execution)

    async def outbox_loop(self) -> None:
        while not self._stop.is_set():
            events = await self._repository.pending_outbox()
            if not events:
                await asyncio.sleep(self._outbox_poll_seconds)
                continue
            for event in events:
                payload = event["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                try:
                    await self._event_publisher.publish_json(event["subject"], payload)
                    await self._repository.mark_published(event["id"])
                except Exception as exc:
                    logger.exception(
                        "Outbox publication failed event_id=%s subject=%s: %s",
                        event["id"],
                        event["subject"],
                        exc,
                    )
                    await self._repository.mark_publish_attempt(event["id"])
                    await asyncio.sleep(1)
                    break

    async def stop(self) -> None:
        self._stop.set()

    async def _execute(self, execution: dict[str, Any]) -> None:
        stage = "BUILD_COMMAND"
        plan = None

        with tracer.start_as_current_span("execution.run") as span:
            span.set_attribute("execution.id", str(execution["id"]))
            span.set_attribute("execution.command_name", execution["command_name"] or "")

            try:
                command = Command(
                    name=execution["command_name"],
                    intent=execution["intent"],
                    input=self._as_object(execution["input"]),
                    context=self._as_object(execution["context"]),
                    instructions=self._as_list(execution["instructions"]),
                )

                stage = "RESOLVE_INTENT"
                plan = await self._resolver.resolve(command)
                span.set_attribute("execution.strategy", plan.strategy)
                if plan.agent_name:
                    span.set_attribute("execution.agent", plan.agent_name)
                if plan.tool_name:
                    span.set_attribute("execution.tool", plan.tool_name)

                if plan.strategy == "TOOL":
                    stage = "EXECUTE_TOOL"
                    tool_result = await self._tool_service.execute(plan.tool_name, plan.tool_arguments)
                    result = {
                        "type": "tool-response",
                        "summary": json.dumps(tool_result, ensure_ascii=False),
                        "data": {
                            "strategy": plan.strategy,
                            "tool": plan.tool_name,
                            "toolResult": tool_result,
                        },
                        "artifacts": [],
                    }
                else:
                    execution_plan = plan
                    tool_result = None

                    if plan.strategy in {"TOOL_LLM", "AGENT_TOOL_LLM"}:
                        stage = "EXECUTE_TOOL"
                        tool_result = await self._tool_service.execute(plan.tool_name, plan.tool_arguments)
                        execution_plan = replace(
                            plan,
                            user_prompt=(
                                f"{plan.user_prompt}\n\n"
                                f"Tool result from '{plan.tool_name}':\n"
                                f"{json.dumps(tool_result, ensure_ascii=False)}"
                            ),
                        )

                    stage = "EXECUTE_MODEL"
                    result = await self._model_gateway.execute(execution_plan)
                    result.setdefault("data", {})
                    result["data"]["strategy"] = plan.strategy
                    if plan.agent_name:
                        result["data"]["agent"] = plan.agent_name
                    if plan.tool_name:
                        result["data"]["tool"] = plan.tool_name
                    if tool_result is not None:
                        result["data"]["toolUsed"] = True

                stage = "PERSIST_RESULT"
                await self._repository.complete(
                    execution,
                    normalized_intent=command.intent.strip(),
                    result=result,
                )
            except Exception as exc:
                technical_message = self._safe_message(exc)
                error = {
                    "code": "EXECUTION_FAILED",
                    "category": "PLATFORM",
                    "message": "The execution could not be completed.",
                    "retryable": True,
                    "details": {
                        "stage": stage,
                        "exceptionType": type(exc).__name__,
                        "message": technical_message,
                        "strategy": getattr(plan, "strategy", None),
                        "agent": getattr(plan, "agent_name", None),
                        "tool": getattr(plan, "tool_name", None),
                    },
                }

                logger.exception(
                    "Execution failed execution_id=%s correlation_id=%s stage=%s strategy=%s agent=%s tool=%s: %s",
                    execution["id"],
                    execution["correlation_id"],
                    stage,
                    getattr(plan, "strategy", None),
                    getattr(plan, "agent_name", None),
                    getattr(plan, "tool_name", None),
                    technical_message,
                )

                span.set_attribute("execution.error.stage", stage)
                span.set_attribute("execution.error.type", type(exc).__name__)
                span.set_attribute("execution.error.message", technical_message)
                span.record_exception(exc)

                await self._repository.fail(execution, error)

    @staticmethod
    def _safe_message(exc: Exception, max_length: int = 4000) -> str:
        message = str(exc).strip() or repr(exc)
        return message[:max_length]

    @staticmethod
    def _as_object(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
