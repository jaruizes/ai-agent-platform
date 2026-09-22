import asyncio
import json
from typing import Any
from uuid import UUID

from opentelemetry import trace

from app.business.intent_resolver import IntentResolver
from app.business.ports import EventPublisherPort, ExecutionRepositoryPort, ModelGatewayPort
from app.domain.execution import Command, ExecutionSubmission


tracer = trace.get_tracer(__name__)


class ExecutionService:
    def __init__(
        self,
        repository: ExecutionRepositoryPort,
        resolver: IntentResolver,
        model_gateway: ModelGatewayPort,
        event_publisher: EventPublisherPort,
        *,
        worker_poll_seconds: float,
        outbox_poll_seconds: float,
    ):
        self._repository = repository
        self._resolver = resolver
        self._model_gateway = model_gateway
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
                except Exception:
                    await self._repository.mark_publish_attempt(event["id"])
                    await asyncio.sleep(1)
                    break

    async def stop(self) -> None:
        self._stop.set()

    async def _execute(self, execution: dict[str, Any]) -> None:
        with tracer.start_as_current_span("execution.run") as span:
            span.set_attribute("execution.id", str(execution["id"]))
            span.set_attribute("execution.command_name", execution["command_name"] or "")

            command = Command(
                name=execution["command_name"],
                intent=execution["intent"],
                input=self._as_object(execution["input"]),
                context=self._as_object(execution["context"]),
                instructions=self._as_list(execution["instructions"]),
            )

            try:
                plan = self._resolver.resolve(command)
                result = await self._model_gateway.execute(plan)
                await self._repository.complete(
                    execution,
                    normalized_intent=command.intent.strip(),
                    result=result,
                )
            except Exception as exc:
                error = {
                    "code": "EXECUTION_FAILED",
                    "category": "PLATFORM",
                    "message": "The execution could not be completed.",
                    "retryable": True,
                    "details": {"reason": type(exc).__name__},
                }
                span.record_exception(exc)
                await self._repository.fail(execution, error)

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
