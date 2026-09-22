import json
from collections.abc import Awaitable, Callable

import nats
from nats.aio.msg import Msg
from nats.js.errors import NotFoundError

from app.config import Settings


CommandHandler = Callable[[bytes], Awaitable[bool]]


class NatsClient:
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

    async def subscribe_commands(self, handler: CommandHandler) -> None:
        async def callback(msg: Msg) -> None:
            try:
                accepted = await handler(msg.data)
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

    async def publish_json(self, subject: str, payload: dict) -> None:
        await self.js.publish(subject, json.dumps(payload).encode("utf-8"))

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
