import asyncio
import json
from uuid import UUID, uuid4

from opentelemetry import trace
from pydantic import ValidationError

from app.config import Settings
from app.intent_resolver import IntentResolver
from app.model_gateway import ModelGateway
from app.models import Command, ExecutionCommandEnvelope
from app.nats_client import NatsClient
from app.repository import ExecutionRepository


tracer = trace.get_tracer(__name__)


class ExecutionService:
    def __init__(
        self,
        settings: Settings,
        repository: ExecutionRepository,
        resolver: IntentResolver,
        gateway: ModelGateway,
        nats_client: NatsClient,
    ):
        self._settings = settings
        self._repository = repository
        self._resolver = resolver
        self._gateway = gateway
        self._nats = nats_client
        self._stop = asyncio.Event()

    async def submit_rest(
        self,
        *,
        correlation_id: str | None,
        command: Command,
    ) -> tuple[UUID, str]:
        execution_id = uuid4()
        message_id = str(uuid4())
        correlation_id = correlation_id or str(uuid4())
        await self._repository.create_execution(
            execution_id=execution_id,
            message_id=message_id,
            correlation_id=correlation_id,
            source={"type": "application", "name": "rest-client"},
            command=command,
        )
        return execution_id, correlation_id

    async def submit_nats(self, raw: bytes) -> bool:
        try:
            envelope = ExecutionCommandEnvelope.model_validate_json(raw)
        except ValidationError:
            return False

        execution_id = envelope.data.execution.executionId or uuid4()
        await self._repository.create_execution(
            execution_id=execution_id,
            message_id=envelope.messageId,
            correlation_id=envelope.correlationId,
            source=envelope.source.model_dump(),
            command=envelope.data.execution.command,
        )
        return True

    async def worker_loop(self) -> None:
        while not self._stop.is_set():
            execution = await self._repository.claim_next()
            if not execution:
                await asyncio.sleep(self._settings.worker_poll_seconds)
                continue
            await self._execute(execution)

    async def outbox_loop(self) -> None:
        while not self._stop.is_set():
            events = await self._repository.pending_outbox()
            if not events:
                await asyncio.sleep(self._settings.outbox_poll_seconds)
                continue
            for event in events:
                payload = event["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                try:
                    await self._nats.publish_json(event["subject"], payload)
                    await self._repository.mark_published(event["id"])
                except Exception:
                    await self._repository.mark_publish_attempt(event["id"])
                    await asyncio.sleep(1)
                    break

    async def stop(self) -> None:
        self._stop.set()

    async def _execute(self, execution: dict) -> None:
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
                result = await self._gateway.execute(plan)
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
    def _as_object(value) -> dict:
        if value is None:
            return {}
        if isinstance(value, str):
            return json.loads(value)
        return dict(value)

    @staticmethod
    def _as_list(value) -> list:
        if value is None:
            return []
        if isinstance(value, str):
            return json.loads(value)
        return list(value)
