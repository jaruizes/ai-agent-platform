import json
from typing import Any
from uuid import UUID

from app.db import Database
from app.events import lifecycle_event, result_event
from app.models import Command


LIFECYCLE_SUBJECT = "platform.events.execution.lifecycle"
RESULT_SUBJECT = "platform.events.execution.result"


class ExecutionRepository:
    def __init__(self, database: Database):
        self._db = database

    async def create_execution(
        self,
        *,
        execution_id: UUID,
        message_id: str,
        correlation_id: str,
        source: dict[str, Any],
        command: Command,
    ) -> tuple[UUID, bool]:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO executions (
                        id, request_message_id, correlation_id, source,
                        command_name, intent, input, context, instructions, status
                    )
                    VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,'ACCEPTED')
                    ON CONFLICT (request_message_id) DO NOTHING
                    RETURNING id
                    """,
                    execution_id,
                    message_id,
                    correlation_id,
                    json.dumps(source),
                    command.name,
                    command.intent,
                    json.dumps(command.input),
                    json.dumps(command.context),
                    json.dumps(command.instructions),
                )
                if not row:
                    existing = await conn.fetchrow(
                        "SELECT id FROM executions WHERE request_message_id = $1", message_id
                    )
                    return existing["id"], False

                event = lifecycle_event(
                    execution_id=execution_id,
                    correlation_id=correlation_id,
                    causation_id=message_id,
                    command_name=command.name,
                    status="ACCEPTED",
                    event_type="EXECUTION_ACCEPTED",
                    sequence=1,
                )
                await self._insert_outbox(conn, execution_id, LIFECYCLE_SUBJECT, event)
                return execution_id, True

    async def claim_next(self) -> dict[str, Any] | None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM executions
                    WHERE status = 'ACCEPTED'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                if not row:
                    return None

                await conn.execute(
                    "UPDATE executions SET status='RUNNING', updated_at=now() WHERE id=$1",
                    row["id"],
                )
                event = lifecycle_event(
                    execution_id=row["id"],
                    correlation_id=row["correlation_id"],
                    causation_id=row["request_message_id"],
                    command_name=row["command_name"],
                    status="RUNNING",
                    event_type="EXECUTION_STARTED",
                    sequence=2,
                )
                await self._insert_outbox(conn, row["id"], LIFECYCLE_SUBJECT, event)
                data = dict(row)
                data["status"] = "RUNNING"
                return data

    async def complete(
        self,
        execution: dict[str, Any],
        *,
        normalized_intent: str,
        result: dict[str, Any],
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='COMPLETED',
                        normalized_intent=$2,
                        result=$3::jsonb,
                        updated_at=now(),
                        completed_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                    normalized_intent,
                    json.dumps(result),
                )
                output = result_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    result=result,
                )
                await self._insert_outbox(conn, execution["id"], RESULT_SUBJECT, output)

                completed = lifecycle_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=output["messageId"],
                    command_name=execution["command_name"],
                    status="COMPLETED",
                    event_type="EXECUTION_COMPLETED",
                    sequence=3,
                )
                await self._insert_outbox(conn, execution["id"], LIFECYCLE_SUBJECT, completed)

    async def fail(self, execution: dict[str, Any], error: dict[str, Any]) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='FAILED', error=$2::jsonb, updated_at=now(), completed_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                    json.dumps(error),
                )
                failed = lifecycle_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    status="FAILED",
                    event_type="EXECUTION_FAILED",
                    sequence=3,
                    error=error,
                )
                await self._insert_outbox(conn, execution["id"], LIFECYCLE_SUBJECT, failed)

    async def get(self, execution_id: UUID) -> dict[str, Any] | None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM executions WHERE id=$1", execution_id)
            return dict(row) if row else None

    async def pending_outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, subject, payload, attempts
                FROM outbox_events
                WHERE published_at IS NULL
                ORDER BY created_at
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def mark_published(self, event_id: UUID) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE outbox_events SET published_at=now(), attempts=attempts+1 WHERE id=$1",
                event_id,
            )

    async def mark_publish_attempt(self, event_id: UUID) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE outbox_events SET attempts=attempts+1 WHERE id=$1", event_id
            )

    @staticmethod
    async def _insert_outbox(conn, execution_id: UUID, subject: str, payload: dict[str, Any]) -> None:
        await conn.execute(
            """
            INSERT INTO outbox_events (id, execution_id, subject, payload)
            VALUES ($1,$2,$3,$4::jsonb)
            """,
            UUID(payload["messageId"]),
            execution_id,
            subject,
            json.dumps(payload),
        )
