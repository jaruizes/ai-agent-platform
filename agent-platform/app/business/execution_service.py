import asyncio
import json
import logging
import socket
from typing import Any
from uuid import UUID, uuid4

from opentelemetry import trace

from app.business.memory_candidate_extractor import MemoryCandidateExtractor
from app.business.memory_service import MemoryService
from app.business.planner_service import PlannerService
from app.business.ports import (
    EventPublisherPort,
    ExecutionRepositoryPort,
    OrchestrationEnginePort,
)
from app.domain.execution import Command, ExecutionSubmission
from app.domain.orchestration import (
    LogicalPlan,
    OrchestrationCancelled,
    OrchestrationSuspended,
)


tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        repository: ExecutionRepositoryPort,
        planner: PlannerService,
        orchestration_engine: OrchestrationEnginePort,
        event_publisher: EventPublisherPort,
        memory_service: MemoryService,
        memory_candidate_extractor: MemoryCandidateExtractor | None,
        *,
        worker_poll_seconds: float,
        outbox_poll_seconds: float,
        execution_lease_seconds: int,
        execution_heartbeat_seconds: float,
    ):
        self._repository = repository
        self._planner = planner
        self._orchestration_engine = orchestration_engine
        self._event_publisher = event_publisher
        self._memory_service = memory_service
        self._memory_candidate_extractor = memory_candidate_extractor
        self._worker_poll_seconds = worker_poll_seconds
        self._outbox_poll_seconds = outbox_poll_seconds
        self._execution_lease_seconds = execution_lease_seconds
        self._execution_heartbeat_seconds = execution_heartbeat_seconds
        self._worker_id = f"{socket.gethostname()}:{uuid4()}"
        self._stop = asyncio.Event()

    async def submit(self, submission: ExecutionSubmission) -> tuple[UUID, bool]:
        if submission.session_id:
            await self._memory_service.require_active_session(
                submission.session_id
            )
        return await self._repository.create_execution(submission)

    async def get_execution(self, execution_id: UUID) -> dict[str, Any] | None:
        return await self._repository.get(execution_id)

    async def get_orchestration(self, execution_id: UUID) -> dict[str, Any] | None:
        return await self._repository.get_orchestration(execution_id)

    async def pause_execution(
        self,
        execution_id: UUID,
        *,
        reason: str | None = None,
    ) -> bool:
        return await self._repository.request_pause(
            execution_id,
            reason=reason,
        )

    async def resume_execution(self, execution_id: UUID) -> bool:
        return await self._repository.resume_execution(execution_id)

    async def cancel_execution(
        self,
        execution_id: UUID,
        *,
        reason: str | None = None,
    ) -> bool:
        return await self._repository.request_cancel(
            execution_id,
            reason=reason,
        )

    async def retry_execution(
        self,
        execution_id: UUID,
        *,
        reason: str | None = None,
    ) -> bool:
        return await self._repository.retry_failed_execution(
            execution_id,
            reason=reason,
        )

    async def decide_step_approval(
        self,
        execution_id: UUID,
        step_id: str,
        *,
        approved: bool,
        actor: str,
        comment: str | None = None,
    ) -> bool:
        return await self._repository.decide_step_approval(
            execution_id,
            step_id,
            approved=approved,
            actor=actor,
            comment=comment,
        )

    async def worker_loop(self) -> None:
        while not self._stop.is_set():
            execution = await self._repository.claim_next(
                worker_id=self._worker_id,
                lease_seconds=self._execution_lease_seconds,
            )
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
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(execution["id"], heartbeat_stop),
            name=f"execution-heartbeat-{execution['id']}",
        )

        with tracer.start_as_current_span("execution.run") as span:
            span.set_attribute("execution.id", str(execution["id"]))
            span.set_attribute("execution.worker_id", self._worker_id)
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
                    metadata=self._as_object(
                        execution.get("command_metadata") or {}
                    ),
                )

                await self._honor_control_before_plan(execution)

                existing_orchestration = await self._repository.get_orchestration(
                    execution["id"]
                )
                if existing_orchestration:
                    stage = "RECOVER_PLAN"
                    plan_data = existing_orchestration["plan"]["logical_plan"]
                    plan = LogicalPlan.from_dict(plan_data)
                    planner_detail = {
                        "model": existing_orchestration["plan"]["planner_model"],
                        "modelProfile": "planner-default",
                        "usage": existing_orchestration["plan"]["planner_usage"],
                        "recovered": True,
                    }
                    validation_data = (
                        existing_orchestration["plan"].get("validation") or {}
                    )
                    if not validation_data.get("valid", False):
                        raise ValueError(
                            "Stored execution plan is not valid and cannot be resumed"
                        )
                    span.set_attribute("execution.recovered", True)
                else:
                    stage = "PLAN"
                    plan, validation, planner_detail = await self._planner.plan(command)
                    span.set_attribute("execution.plan.steps", len(plan.steps))
                    span.set_attribute(
                        "execution.plan.final_step",
                        plan.final_step_id,
                    )
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
                            "planningAttempts": planner_detail.get(
                                "planningAttempts",
                                1,
                            ),
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
                            "recovered": planner_detail.get("recovered", False),
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

                if (
                    self._memory_candidate_extractor is not None
                    and execution.get("session_id")
                ):
                    try:
                        candidates = (
                            await self._memory_candidate_extractor.extract_for_session(
                                session_id=execution["session_id"],
                                execution_id=execution["id"],
                                command=command,
                                result=result,
                            )
                        )
                        decisions = await self._memory_service.persist_candidates(
                            candidates
                        )
                        span.set_attribute(
                            "execution.memory.candidates",
                            len(candidates),
                        )
                        span.set_attribute(
                            "execution.memory.persisted",
                            sum(1 for item in decisions if item["persisted"]),
                        )
                    except Exception:
                        logger.exception(
                            "Session memory extraction failed execution_id=%s",
                            execution["id"],
                        )
            except OrchestrationSuspended as exc:
                logger.info(
                    "Execution suspended execution_id=%s status=%s reason=%s",
                    execution["id"],
                    exc.status,
                    exc.reason,
                )
                await self._repository.mark_suspended(
                    execution,
                    status=exc.status,
                    reason=exc.reason,
                )
            except OrchestrationCancelled as exc:
                logger.info(
                    "Execution cancelled execution_id=%s reason=%s",
                    execution["id"],
                    str(exc),
                )
                await self._repository.mark_cancelled(
                    execution,
                    reason=str(exc) or "Cancelled by operator",
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
                    "retryable": stage not in {"PLAN", "RECOVER_PLAN"},
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
            finally:
                heartbeat_stop.set()
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)
                await self._repository.release_lease(
                    execution["id"],
                    worker_id=self._worker_id,
                )

    async def _heartbeat_loop(
        self,
        execution_id: UUID,
        stop: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._execution_heartbeat_seconds,
                )
                return
            except asyncio.TimeoutError:
                renewed = await self._repository.heartbeat(
                    execution_id,
                    worker_id=self._worker_id,
                    lease_seconds=self._execution_lease_seconds,
                )
                if not renewed:
                    logger.warning(
                        "Execution lease could not be renewed execution_id=%s worker_id=%s",
                        execution_id,
                        self._worker_id,
                    )
                    return

    async def _honor_control_before_plan(
        self,
        execution: dict[str, Any],
    ) -> None:
        control = await self._repository.get_control(execution["id"])
        action = control.get("control_action")
        reason = control.get("control_reason") or "Requested by operator"
        if action == "CANCEL":
            raise OrchestrationCancelled(reason)
        if action == "PAUSE":
            raise OrchestrationSuspended("PAUSED", reason)

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
