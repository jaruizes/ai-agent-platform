import json
from typing import Any
from uuid import UUID

from app.domain.events import lifecycle_event, orchestration_event, result_event
from app.domain.execution import ExecutionSubmission
from app.infrastructure.persistence.postgres.database import Database


LIFECYCLE_SUBJECT = "platform.events.execution.lifecycle"
RESULT_SUBJECT = "platform.events.execution.result"
ORCHESTRATION_SUBJECT = "platform.events.execution.orchestration"


class PostgresExecutionRepository:
    def __init__(self, database: Database):
        self._db = database

    async def create_execution(self, submission: ExecutionSubmission) -> tuple[UUID, bool]:
        pool = self._db.require_pool()
        command = submission.command

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
                    submission.execution_id,
                    submission.message_id,
                    submission.correlation_id,
                    json.dumps(submission.source),
                    command.name,
                    command.intent,
                    json.dumps(command.input),
                    json.dumps(command.context),
                    json.dumps(command.instructions),
                )

                if not row:
                    existing = await conn.fetchrow(
                        "SELECT id FROM executions WHERE request_message_id = $1",
                        submission.message_id,
                    )
                    return existing["id"], False

                event = lifecycle_event(
                    execution_id=submission.execution_id,
                    correlation_id=submission.correlation_id,
                    causation_id=submission.message_id,
                    command_name=command.name,
                    status="ACCEPTED",
                    event_type="EXECUTION_ACCEPTED",
                    sequence=1,
                )
                await self._insert_outbox(
                    conn,
                    submission.execution_id,
                    LIFECYCLE_SUBJECT,
                    event,
                )
                return submission.execution_id, True

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
            if not row:
                return None

            data = dict(row)
            for field in ("source", "input", "context", "instructions", "result", "error"):
                if isinstance(data.get(field), str):
                    data[field] = json.loads(data[field])
            return data

    async def save_plan(
        self,
        execution: dict[str, Any],
        *,
        plan: dict[str, Any],
        planner_model: str,
        planner_usage: dict[str, Any],
        validation: dict[str, Any],
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO execution_plans(
                        execution_id,objective,status,planner_model,planner_usage,
                        logical_plan,validation
                    ) VALUES($1,$2,'PLANNED',$3,$4::jsonb,$5::jsonb,$6::jsonb)
                    ON CONFLICT (execution_id) DO UPDATE SET
                        objective=EXCLUDED.objective,
                        status='PLANNED',
                        planner_model=EXCLUDED.planner_model,
                        planner_usage=EXCLUDED.planner_usage,
                        logical_plan=EXCLUDED.logical_plan,
                        validation=EXCLUDED.validation,
                        updated_at=now()
                    """,
                    execution["id"],
                    plan["objective"],
                    planner_model,
                    json.dumps(planner_usage),
                    json.dumps(plan),
                    json.dumps(validation),
                )
                await conn.execute(
                    "DELETE FROM execution_plan_steps WHERE execution_id=$1",
                    execution["id"],
                )
                if plan.get("steps"):
                    await conn.executemany(
                        """
                        INSERT INTO execution_plan_steps(
                            execution_id,step_id,step_type,description,agent_name,
                            tool_name,knowledge_bases,depends_on,status
                        ) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,'PENDING')
                        """,
                        [
                            (
                                execution["id"],
                                step["id"],
                                step["type"],
                                step["description"],
                                step.get("agent"),
                                step.get("tool"),
                                json.dumps(step.get("knowledgeBases") or []),
                                json.dumps(step.get("dependsOn") or []),
                            )
                            for step in plan["steps"]
                        ],
                    )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="PLAN_CREATED",
                    detail={
                        "objective": plan["objective"],
                        "finalStepId": plan["finalStepId"],
                        "steps": [
                            {
                                "id": step["id"],
                                "type": step["type"],
                                "description": step["description"],
                                "agent": step.get("agent"),
                                "tool": step.get("tool"),
                                "dependsOn": step.get("dependsOn") or [],
                            }
                            for step in plan["steps"]
                        ],
                        "plannerUsage": planner_usage,
                    },
                )
                await self._insert_outbox(
                    conn,
                    execution["id"],
                    ORCHESTRATION_SUBJECT,
                    event,
                )

    async def mark_plan_running(self, execution_id: UUID) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE execution_plans
                SET status='RUNNING',started_at=COALESCE(started_at,now()),updated_at=now()
                WHERE execution_id=$1
                """,
                execution_id,
            )

    async def mark_plan_completed(self, execution_id: UUID) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE execution_plans
                SET status='COMPLETED',completed_at=now(),updated_at=now()
                WHERE execution_id=$1
                """,
                execution_id,
            )

    async def mark_plan_failed(self, execution_id: UUID) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE execution_plans
                SET status='FAILED',completed_at=now(),updated_at=now()
                WHERE execution_id=$1
                """,
                execution_id,
            )

    async def mark_step_started(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        detail: dict[str, Any],
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='RUNNING',started_at=now(),error=NULL
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_STARTED",
                    detail={"stepId": step_id, **detail},
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def mark_step_completed(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        output: dict[str, Any],
        usage: dict[str, Any],
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='COMPLETED',output=$3::jsonb,usage=$4::jsonb,
                        completed_at=now()
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                    json.dumps(output),
                    json.dumps(usage),
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_COMPLETED",
                    detail={
                        "stepId": step_id,
                        "usage": usage,
                        "summary": str(output.get("summary", ""))[:1000],
                    },
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def mark_step_failed(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        error: dict[str, Any],
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='FAILED',error=$3::jsonb,completed_at=now()
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                    json.dumps(error),
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_FAILED",
                    detail={"stepId": step_id, "error": error},
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def get_orchestration(self, execution_id: UUID) -> dict[str, Any] | None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            plan = await conn.fetchrow(
                "SELECT * FROM execution_plans WHERE execution_id=$1",
                execution_id,
            )
            if not plan:
                return None
            steps = await conn.fetch(
                """
                SELECT * FROM execution_plan_steps
                WHERE execution_id=$1
                ORDER BY COALESCE(started_at,'infinity'::timestamptz), step_id
                """,
                execution_id,
            )

        plan_data = dict(plan)
        for field in ("planner_usage", "logical_plan", "validation"):
            if isinstance(plan_data.get(field), str):
                plan_data[field] = json.loads(plan_data[field])

        step_data = []
        for row in steps:
            item = dict(row)
            for field in ("knowledge_bases", "depends_on", "usage", "output", "error"):
                if isinstance(item.get(field), str):
                    item[field] = json.loads(item[field])
            step_data.append(item)

        planner_usage = plan_data.get("planner_usage") or {}
        total_usage = self._sum_usage(
            [planner_usage, *[(step.get("usage") or {}) for step in step_data]]
        )
        active_agents = [
            {
                "stepId": step["step_id"],
                "agent": step["agent_name"],
                "activity": step["description"],
                "startedAt": step["started_at"],
            }
            for step in step_data
            if step["status"] == "RUNNING" and step["agent_name"]
        ]
        return {
            "plan": plan_data,
            "steps": step_data,
            "activeAgents": active_agents,
            "usage": total_usage,
        }

    @staticmethod
    def _sum_usage(items: list[dict[str, Any]]) -> dict[str, int]:
        prompt = 0
        completion = 0
        total = 0
        for usage in items:
            prompt += int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            completion += int(
                usage.get("completion_tokens") or usage.get("output_tokens") or 0
            )
            total += int(usage.get("total_tokens") or 0)
        if total == 0:
            total = prompt + completion
        return {
            "promptTokens": prompt,
            "completionTokens": completion,
            "totalTokens": total,
        }

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
                "UPDATE outbox_events SET attempts=attempts+1 WHERE id=$1",
                event_id,
            )

    @staticmethod
    async def _insert_outbox(
        conn,
        execution_id: UUID,
        subject: str,
        payload: dict[str, Any],
    ) -> None:
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
