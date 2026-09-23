import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import nats
from nats.aio.msg import Msg
from nats.js.errors import NotFoundError
from pydantic import ValidationError

from app.business.execution_service import ExecutionService
from app.domain.execution import Command, ExecutionSubmission
from app.infrastructure.api.messaging.schemas import ExecutionCommandEnvelope
from app.infrastructure.config.settings import Settings


class NatsAdapter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.nc = None
        self.js = None
        self._subscription = None

    async def connect(self) -> None:
        self.nc = await nats.connect(
            self._settings.nats_url,
            name=self._settings.service_name,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        self.js = self.nc.jetstream()
        await self._ensure_streams()

    async def close(self) -> None:
        if self.nc:
            await self.nc.drain()

    async def subscribe_commands(self, service: ExecutionService) -> None:
        async def callback(msg: Msg) -> None:
            try:
                accepted = await self._handle_command(msg.data, service)
                if accepted:
                    await msg.ack()
                else:
                    await msg.term()
            except Exception:
                await msg.nak(delay=2)

        self._subscription = await self.js.subscribe(
            self._settings.nats_command_subject,
            durable=self._settings.nats_command_consumer,
            manual_ack=True,
            cb=callback,
        )

    async def publish_json(self, subject: str, payload: dict[str, Any]) -> None:
        await self.js.publish(subject, json.dumps(payload).encode("utf-8"))

    async def _handle_command(self, raw: bytes, service: ExecutionService) -> bool:
        try:
            envelope = ExecutionCommandEnvelope.model_validate_json(raw)
        except ValidationError:
            return False

        message = envelope.data.execution.command
        submission = ExecutionSubmission(
            execution_id=envelope.data.execution.executionId or uuid4(),
            message_id=envelope.messageId,
            correlation_id=envelope.correlationId,
            source=envelope.source.model_dump(),
            session_id=envelope.data.execution.sessionId,
            command=Command(
                name=message.name,
                intent=message.intent,
                input=message.input,
                context=message.context,
                instructions=message.instructions,
                metadata=message.metadata,
            ),
        )
        try:
            await service.submit(submission)
        except (LookupError, ValueError):
            return False
        return True

    async def _ensure_streams(self) -> None:
        await self._ensure_stream(
            self._settings.nats_command_stream,
            ["platform.commands.>"],
        )
        await self._ensure_stream(
            self._settings.nats_event_stream,
            ["platform.events.>"],
        )

    async def _ensure_stream(self, name: str, subjects: list[str]) -> None:
        try:
            await self.js.stream_info(name)
        except NotFoundError:
            await self.js.add_stream(name=name, subjects=subjects)
