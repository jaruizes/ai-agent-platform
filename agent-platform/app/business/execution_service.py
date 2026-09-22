import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from opentelemetry import trace

from app.business.planner_service import PlannerService
from app.business.ports import (
    EventPublisherPort,
    ExecutionRepositoryPort,
    OrchestrationEnginePort,
)
from app.domain.execution import Command, ExecutionSubmission
from app.domain.orchestration import LogicalPlan


tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        repository: ExecutionRepositoryPort,
        planner: PlannerService,
        orchestration_engine: OrchestrationEnginePort,
        event_publisher: EventPublisherPort,
        *,
        worker_poll_seconds: float,
        outbox_poll_seconds: float,
    ):
        self._repository = repository
        self._planner = planner
        self._orchestration_engine = orchestration_engine
        self._event_publisher = event_publisher
        self._worker_poll_seconds = worker_poll_seconds
        self._outbox_poll_seconds = outbox_poll_seconds
        self._stop = asyncio.Event()

    async def submit(self, submission: ExecutionSubmission) -> tuple[UUID, bool]:
        return await self._repository.create_execution(submission)

    async def get_execution(self, execution_id: UUID) -> dict[str, Any] | None:
        return await self._repository.get(execution_id)

    async def get_orchestration(self, execution_id: UUID) -> dict[str, Any] | None:
        return await self._repository.get_orchestration(execution_id)

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
        plan: LogicalPlan | None = None

        with tracer.start_as_current_span("execution.run") as span:
            span.set_attribute("execution.id", str(execution["id"]))
            span.set_attribute(
                "execution.command_name",
                execution["command_name"] or "",
            )

            try:
                command = Command(
                    name=execution["command_name"],
                    intent=execution["intent"],
                    input=self._as_object(execution["input"]),
                    context=self._as_object(execution["context"]),
                    instructions=self._as_list(execution["instructions"]),
                )

                stage = "PLAN"
                plan, validation, planner_detail = await self._planner.plan(command)
                span.set_attribute("execution.plan.steps", len(plan.steps))
                span.set_attribute("execution.plan.final_step", plan.final_step_id)
                await self._repository.save_plan(
                    execution,
                    plan=plan.as_dict(),
                    planner_model=str(
                        planner_detail.get("model")
                        or planner_detail.get("modelProfile")
                        or ""
                    ),
                    planner_usage={
                        **(planner_detail.get("usage") or {}),
                        "planningAttempts": planner_detail.get("planningAttempts", 1),
                    },
                    validation=validation.as_dict(),
                )
                if not validation.valid:
                    raise ValueError(
                        "Planner produced an invalid plan: "
                        + "; ".join(validation.errors)
                    )

                stage = "ORCHESTRATE"
                orchestration = await self._orchestration_engine.execute(
                    execution=execution,
                    command=command,
                    plan=plan,
                )
                final = orchestration["final"]

                result = {
                    "type": (
                        "agent-response"
                        if final.get("agent")
                        else "orchestration-response"
                    ),
                    "summary": final.get("summary")
                    or json.dumps(final.get("output"), ensure_ascii=False),
                    "data": {
                        "strategy": "ORCHESTRATED",
                        "planObjective": plan.objective,
                        "finalStepId": plan.final_step_id,
                        "finalStep": final,
                        "planner": {
                            "model": planner_detail.get("model"),
                            "modelProfile": planner_detail.get("modelProfile"),
                            "usage": planner_detail.get("usage") or {},
                        },
                    },
                    "artifacts": final.get("artifacts") or [],
                }

                stage = "PERSIST_RESULT"
                await self._repository.complete(
                    execution,
                    normalized_intent=command.intent.strip(),
                    result=result,
                )
            except Exception as exc:
                if plan is not None and stage == "PLAN":
                    try:
                        await self._repository.mark_plan_failed(execution)
                    except Exception:
                        logger.exception(
                            "Could not mark orchestration plan failed execution_id=%s",
                            execution["id"],
                        )

                technical_message = self._safe_message(exc)
                error = {
                    "code": "EXECUTION_FAILED",
                    "category": "PLATFORM",
                    "message": "The execution could not be completed.",
                    "retryable": stage not in {"PLAN"},
                    "details": {
                        "stage": stage,
                        "exceptionType": type(exc).__name__,
                        "message": technical_message,
                        "planObjective": getattr(plan, "objective", None),
                        "finalStepId": getattr(plan, "final_step_id", None),
                    },
                }

                logger.exception(
                    "Execution failed execution_id=%s correlation_id=%s "
                    "stage=%s final_step=%s: %s",
                    execution["id"],
                    execution["correlation_id"],
                    stage,
                    getattr(plan, "final_step_id", None),
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
