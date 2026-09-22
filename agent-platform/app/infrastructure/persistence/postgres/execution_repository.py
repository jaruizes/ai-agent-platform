import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

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
                        command_name, intent, input, context, instructions,
                        session_id, status
                    )
                    VALUES (
                        $1,$2,$3,$4::jsonb,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,
                        $10,'ACCEPTED'
                    )
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
                    submission.session_id,
                )

                if not row:
                    existing = await conn.fetchrow(
                        "SELECT id FROM executions WHERE request_message_id = $1",
                        submission.message_id,
                    )
                    return existing["id"], False

                command_content = {
                    "name": command.name,
                    "intent": command.intent,
                    "input": command.input,
                    "context": command.context,
                    "metadata": command.metadata,
                }
                await conn.execute(
                    """
                    INSERT INTO execution_context_entries(
                        id,execution_id,session_id,entry_type,entry_key,content,
                        priority,token_estimate,source_type,provenance
                    ) VALUES(
                        $1,$2,$3,'COMMAND','command',$4::jsonb,
                        100,$5,'COMMAND',$6::jsonb
                    )
                    """,
                    uuid4(),
                    submission.execution_id,
                    submission.session_id,
                    json.dumps(command_content),
                    self._estimate_tokens(command_content),
                    json.dumps(
                        {
                            "messageId": submission.message_id,
                            "correlationId": submission.correlation_id,
                        }
                    ),
                )
                for index, instruction in enumerate(command.instructions):
                    await conn.execute(
                        """
                        INSERT INTO execution_context_entries(
                            id,execution_id,session_id,entry_type,entry_key,content,
                            priority,token_estimate,source_type,provenance
                        ) VALUES(
                            $1,$2,$3,'INSTRUCTION',$4,$5::jsonb,
                            100,$6,'COMMAND',$7::jsonb
                        )
                        """,
                        uuid4(),
                        submission.execution_id,
                        submission.session_id,
                        f"instruction:{index}",
                        json.dumps({"text": instruction}),
                        self._estimate_tokens(instruction),
                        json.dumps({"instructionIndex": index}),
                    )
                if submission.session_id:
                    await conn.execute(
                        "UPDATE sessions SET updated_at=now() WHERE id=$1",
                        submission.session_id,
                    )

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

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM executions
                    WHERE
                        status = 'ACCEPTED'
                        OR (
                            status IN ('RUNNING','RETRYING','PAUSING','CANCELLING')
                            AND (
                                lease_expires_at IS NULL
                                OR lease_expires_at < now()
                            )
                        )
                    ORDER BY
                        CASE WHEN status = 'ACCEPTED' THEN 0 ELSE 1 END,
                        created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                if not row:
                    return None

                recovering = row["status"] in {
                    "RUNNING", "RETRYING", "PAUSING", "CANCELLING"
                }
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='RUNNING',
                        lease_owner=$2,
                        lease_expires_at=now() + ($3::double precision * interval '1 second'),
                        last_heartbeat_at=now(),
                        control_action=CASE
                            WHEN control_action='RESUME' THEN 'NONE'
                            ELSE control_action
                        END,
                        updated_at=now()
                    WHERE id=$1
                    """,
                    row["id"],
                    worker_id,
                    lease_seconds,
                )
                event = lifecycle_event(
                    execution_id=row["id"],
                    correlation_id=row["correlation_id"],
                    causation_id=row["request_message_id"],
                    command_name=row["command_name"],
                    status="RUNNING",
                    event_type=(
                        "EXECUTION_RECOVERED" if recovering else "EXECUTION_STARTED"
                    ),
                    sequence=2,
                    detail={
                        "workerId": worker_id,
                        "recovering": recovering,
                    },
                )
                await self._insert_outbox(
                    conn, row["id"], LIFECYCLE_SUBJECT, event
                )

                data = dict(row)
                data["status"] = "RUNNING"
                data["lease_owner"] = worker_id
                data["control_action"] = (
                    "NONE" if row["control_action"] == "RESUME"
                    else row["control_action"]
                )
                return data

    async def heartbeat(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        async with self._db.require_pool().acquire() as conn:
            result = await conn.execute(
                """
                UPDATE executions
                SET lease_expires_at=now() + ($3::double precision * interval '1 second'),
                    last_heartbeat_at=now(),
                    updated_at=now()
                WHERE id=$1 AND lease_owner=$2
                  AND status IN ('RUNNING','RETRYING','PAUSING','CANCELLING')
                """,
                execution_id,
                worker_id,
                lease_seconds,
            )
            return result == "UPDATE 1"

    async def release_lease(self, execution_id: UUID, *, worker_id: str) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE executions
                SET lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                WHERE id=$1 AND lease_owner=$2
                """,
                execution_id,
                worker_id,
            )

    async def get_control(self, execution_id: UUID) -> dict[str, Any]:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT status,control_action,control_reason,lease_owner,lease_expires_at
                FROM executions WHERE id=$1
                """,
                execution_id,
            )
            return dict(row) if row else {}

    async def request_pause(self, execution_id: UUID, *, reason: str | None) -> bool:
        return await self._request_control(
            execution_id,
            action="PAUSE",
            status="PAUSING",
            reason=reason,
        )

    async def request_cancel(self, execution_id: UUID, *, reason: str | None) -> bool:
        return await self._request_control(
            execution_id,
            action="CANCEL",
            status="CANCELLING",
            reason=reason,
        )

    async def resume_execution(self, execution_id: UUID) -> bool:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT * FROM executions WHERE id=$1 FOR UPDATE",
                    execution_id,
                )
                if not row or row["status"] != "PAUSED":
                    return False
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='ACCEPTED',control_action='RESUME',
                        control_reason=NULL,lease_owner=NULL,lease_expires_at=NULL,
                        resumed_at=now(),updated_at=now()
                    WHERE id=$1
                    """,
                    execution_id,
                )
                event = lifecycle_event(
                    execution_id=execution_id,
                    correlation_id=row["correlation_id"],
                    causation_id=row["request_message_id"],
                    command_name=row["command_name"],
                    status="ACCEPTED",
                    event_type="EXECUTION_RESUMED",
                    sequence=2,
                )
                await self._insert_outbox(
                    conn, execution_id, LIFECYCLE_SUBJECT, event
                )
                return True

    async def retry_failed_execution(
        self,
        execution_id: UUID,
        *,
        reason: str | None,
    ) -> bool:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT * FROM executions
                    WHERE id=$1 AND status='FAILED'
                    FOR UPDATE
                    """,
                    execution_id,
                )
                if not row:
                    return False
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='ACCEPTED',error=NULL,completed_at=NULL,
                        control_action='NONE',control_reason=$2,
                        lease_owner=NULL,lease_expires_at=NULL,
                        resumed_at=now(),updated_at=now()
                    WHERE id=$1
                    """,
                    execution_id,
                    reason,
                )
                await conn.execute(
                    """
                    UPDATE execution_plans
                    SET status='PLANNED',completed_at=NULL,updated_at=now()
                    WHERE execution_id=$1
                    """,
                    execution_id,
                )
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='PENDING',error=NULL,completed_at=NULL,
                        attempt_count=0,next_retry_at=NULL,last_attempt_at=NULL
                    WHERE execution_id=$1 AND status<>'COMPLETED'
                    """,
                    execution_id,
                )
                event = lifecycle_event(
                    execution_id=execution_id,
                    correlation_id=row["correlation_id"],
                    causation_id=row["request_message_id"],
                    command_name=row["command_name"],
                    status="ACCEPTED",
                    event_type="EXECUTION_RETRY_REQUESTED",
                    sequence=2,
                    detail={"reason": reason},
                )
                await self._insert_outbox(
                    conn, execution_id, LIFECYCLE_SUBJECT, event
                )
                return True

    async def mark_suspended(
        self,
        execution: dict[str, Any],
        *,
        status: str,
        reason: str,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE executions
                    SET status=$2,control_action='NONE',control_reason=$3,
                        lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                    status,
                    reason,
                )
                await conn.execute(
                    """
                    UPDATE execution_plans
                    SET status=$2,updated_at=now()
                    WHERE execution_id=$1
                    """,
                    execution["id"],
                    status,
                )
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='PAUSED'
                    WHERE execution_id=$1
                      AND status IN ('RUNNING','RETRYING')
                    """,
                    execution["id"],
                )
                event = lifecycle_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    status=status,
                    event_type=(
                        "EXECUTION_WAITING_APPROVAL"
                        if status == "WAITING_APPROVAL"
                        else "EXECUTION_PAUSED"
                    ),
                    sequence=2,
                    detail={"reason": reason},
                )
                await self._insert_outbox(
                    conn, execution["id"], LIFECYCLE_SUBJECT, event
                )

    async def mark_cancelled(
        self,
        execution: dict[str, Any],
        *,
        reason: str,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='CANCELLED',control_action='NONE',control_reason=$2,
                        cancelled_at=now(),completed_at=now(),
                        lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                    reason,
                )
                await conn.execute(
                    """
                    UPDATE execution_plans
                    SET status='CANCELLED',completed_at=now(),updated_at=now()
                    WHERE execution_id=$1
                    """,
                    execution["id"],
                )
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='CANCELLED',completed_at=COALESCE(completed_at,now())
                    WHERE execution_id=$1
                      AND status NOT IN ('COMPLETED','FAILED','CANCELLED')
                    """,
                    execution["id"],
                )
                event = lifecycle_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    status="CANCELLED",
                    event_type="EXECUTION_CANCELLED",
                    sequence=3,
                    detail={"reason": reason},
                )
                await self._insert_outbox(
                    conn, execution["id"], LIFECYCLE_SUBJECT, event
                )

    async def _request_control(
        self,
        execution_id: UUID,
        *,
        action: str,
        status: str,
        reason: str | None,
    ) -> bool:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT * FROM executions
                    WHERE id=$1
                      AND status IN (
                        'ACCEPTED','RUNNING','RETRYING','PAUSING','CANCELLING',
                        'PAUSED','WAITING_APPROVAL'
                      )
                    FOR UPDATE
                    """,
                    execution_id,
                )
                if not row:
                    return False
                await conn.execute(
                    """
                    UPDATE executions
                    SET control_action=$2,status=$3,control_reason=$4,updated_at=now()
                    WHERE id=$1
                    """,
                    execution_id,
                    action,
                    status,
                    reason,
                )
                event = lifecycle_event(
                    execution_id=execution_id,
                    correlation_id=row["correlation_id"],
                    causation_id=row["request_message_id"],
                    command_name=row["command_name"],
                    status=status,
                    event_type=(
                        "EXECUTION_PAUSE_REQUESTED"
                        if action == "PAUSE"
                        else "EXECUTION_CANCEL_REQUESTED"
                    ),
                    sequence=2,
                    detail={"reason": reason},
                )
                await self._insert_outbox(
                    conn, execution_id, LIFECYCLE_SUBJECT, event
                )
                return True

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
                        control_action='NONE',
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        updated_at=now(),
                        completed_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                    normalized_intent,
                    json.dumps(result),
                )

                await conn.execute(
                    """
                    INSERT INTO execution_context_entries(
                        id,execution_id,session_id,entry_type,entry_key,content,
                        priority,token_estimate,source_type,provenance
                    )
                    SELECT $1,id,session_id,'SUMMARY','execution-result',$2::jsonb,
                           90,$3,'EXECUTION',$4::jsonb
                    FROM executions WHERE id=$5
                    """,
                    uuid4(),
                    json.dumps(result),
                    self._estimate_tokens(result),
                    json.dumps({"status": "COMPLETED"}),
                    execution["id"],
                )
                if execution.get("session_id"):
                    await conn.execute(
                        "UPDATE sessions SET updated_at=now() WHERE id=$1",
                        execution["session_id"],
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
                    SET status='FAILED', error=$2::jsonb,
                        control_action='NONE',
                        lease_owner=NULL,
                        lease_expires_at=NULL,
                        updated_at=now(), completed_at=now()
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
                await conn.execute(
                    """
                    INSERT INTO execution_context_entries(
                        id,execution_id,session_id,entry_type,entry_key,content,
                        priority,token_estimate,source_type,provenance
                    )
                    SELECT $1,id,session_id,'PLAN','logical-plan',$2::jsonb,
                           90,$3,'PLANNER',$4::jsonb
                    FROM executions WHERE id=$5
                    """,
                    uuid4(),
                    json.dumps(plan),
                    self._estimate_tokens(plan),
                    json.dumps(
                        {
                            "plannerModel": planner_model,
                            "validation": validation,
                        }
                    ),
                    execution["id"],
                )
                if plan.get("steps"):
                    await conn.executemany(
                        """
                        INSERT INTO execution_plan_steps(
                            execution_id,step_id,step_type,description,agent_name,
                            tool_name,knowledge_bases,depends_on,status,
                            requires_approval,approval_reason,approval_status,
                            approval_source,tool_side_effect,tool_approval_policy,
                            max_attempts,timeout_seconds,retry_policy,idempotency_key
                        ) VALUES(
                            $1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,'PENDING',
                            $9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb,$18
                        )
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
                                bool(step.get("requiresApproval", False)),
                                step.get("approvalReason"),
                                (
                                    "PENDING"
                                    if step.get("requiresApproval", False)
                                    else "NOT_REQUIRED"
                                ),
                                step.get("approvalSource"),
                                step.get("toolSideEffect"),
                                step.get("toolApprovalPolicy"),
                                int(
                                    (step.get("retryPolicy") or {}).get(
                                        "maxAttempts", 3
                                    )
                                ),
                                float(step.get("timeoutSeconds") or 120.0),
                                json.dumps(step.get("retryPolicy") or {}),
                                f"{execution['id']}:{step['id']}",
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

    async def mark_plan_running(self, execution: dict[str, Any]) -> None:
        await self._update_plan_status(execution, "RUNNING", "PLAN_STARTED")

    async def mark_plan_completed(self, execution: dict[str, Any]) -> None:
        await self._update_plan_status(execution, "COMPLETED", "PLAN_COMPLETED")

    async def mark_plan_failed(self, execution: dict[str, Any]) -> None:
        await self._update_plan_status(execution, "FAILED", "PLAN_FAILED")

    async def _update_plan_status(
        self,
        execution: dict[str, Any],
        status: str,
        event_type: str,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                if status == "RUNNING":
                    await conn.execute(
                        """
                        UPDATE execution_plans
                        SET status=$2,started_at=COALESCE(started_at,now()),updated_at=now()
                        WHERE execution_id=$1
                        """,
                        execution["id"],
                        status,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE execution_plans
                        SET status=$2,completed_at=now(),updated_at=now()
                        WHERE execution_id=$1
                        """,
                        execution["id"],
                        status,
                    )
                    if status == "FAILED":
                        await conn.execute(
                            """
                            UPDATE execution_plan_steps
                            SET status='CANCELLED',
                                completed_at=COALESCE(completed_at,now())
                            WHERE execution_id=$1
                              AND status NOT IN ('COMPLETED','FAILED','CANCELLED')
                            """,
                            execution["id"],
                        )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type=event_type,
                    detail={"status": status},
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
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
                    SET status='RUNNING',started_at=COALESCE(started_at,now()),
                        error=NULL,next_retry_at=NULL
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                )
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='RUNNING',updated_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
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
                step_type = await conn.fetchval(
                    """
                    SELECT step_type FROM execution_plan_steps
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                )
                entry_type = {
                    "TOOL": "TOOL_RESULT",
                    "KNOWLEDGE": "KNOWLEDGE",
                }.get(step_type, "STEP_RESULT")
                await conn.execute(
                    """
                    INSERT INTO execution_context_entries(
                        id,execution_id,session_id,step_id,entry_type,entry_key,
                        content,priority,token_estimate,source_type,source_ref,
                        provenance
                    )
                    SELECT $1,id,session_id,$2,$3,$4,$5::jsonb,80,$6,$7,$2,$8::jsonb
                    FROM executions WHERE id=$9
                    """,
                    uuid4(),
                    step_id,
                    entry_type,
                    f"step:{step_id}",
                    json.dumps(output),
                    self._estimate_tokens(output),
                    step_type or "STEP",
                    json.dumps(
                        {
                            "stepId": step_id,
                            "stepType": step_type,
                            "usage": usage,
                        }
                    ),
                    execution["id"],
                )
                if execution.get("session_id"):
                    await conn.execute(
                        "UPDATE sessions SET updated_at=now() WHERE id=$1",
                        execution["session_id"],
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

    async def get_step_checkpoint(
        self,
        execution_id: UUID,
        step_id: str,
    ) -> dict[str, Any] | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM execution_plan_steps
                WHERE execution_id=$1 AND step_id=$2
                """,
                execution_id,
                step_id,
            )
            if not row:
                return None
            item = dict(row)
            for field in (
                "knowledge_bases","depends_on","usage","output","error","retry_policy"
            ):
                if isinstance(item.get(field), str):
                    item[field] = json.loads(item[field])
            return item

    async def mark_step_attempt(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
    ) -> int:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE execution_plan_steps
                SET attempt_count=attempt_count+1,last_attempt_at=now(),
                    next_retry_at=NULL
                WHERE execution_id=$1 AND step_id=$2
                RETURNING attempt_count
                """,
                execution["id"],
                step_id,
            )
            return int(row["attempt_count"])

    async def mark_step_retrying(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        error: dict[str, Any],
        delay_seconds: float,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='RETRYING',error=$3::jsonb,
                        next_retry_at=now() + ($4::double precision * interval '1 second')
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                    json.dumps(error),
                    delay_seconds,
                )
                await conn.execute(
                    """
                    UPDATE executions
                    SET status='RETRYING',updated_at=now()
                    WHERE id=$1
                    """,
                    execution["id"],
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_RETRYING",
                    detail={
                        "stepId": step_id,
                        "error": error,
                        "delaySeconds": delay_seconds,
                    },
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def enforce_step_approval_policy(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        reason: str,
        approval_source: str,
        tool_side_effect: str,
        tool_approval_policy: str,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT requires_approval,approval_status
                    FROM execution_plan_steps
                    WHERE execution_id=$1 AND step_id=$2
                    FOR UPDATE
                    """,
                    execution["id"],
                    step_id,
                )
                if not row:
                    raise LookupError(
                        f"Execution step '{step_id}' does not exist"
                    )
                if row["requires_approval"]:
                    return

                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET requires_approval=true,
                        approval_reason=COALESCE(approval_reason,$3),
                        approval_source=$4,
                        tool_side_effect=$5,
                        tool_approval_policy=$6,
                        approval_status=CASE
                            WHEN approval_status='NOT_REQUIRED' THEN 'PENDING'
                            ELSE approval_status
                        END
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                    reason,
                    approval_source,
                    tool_side_effect,
                    tool_approval_policy,
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_APPROVAL_POLICY_ENFORCED",
                    detail={
                        "stepId": step_id,
                        "approvalSource": approval_source,
                        "toolSideEffect": tool_side_effect,
                        "toolApprovalPolicy": tool_approval_policy,
                        "reason": reason,
                    },
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def mark_step_waiting_approval(
        self,
        execution: dict[str, Any],
        *,
        step_id: str,
        reason: str,
    ) -> None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET status='WAITING_APPROVAL',approval_status='PENDING',
                        approval_reason=COALESCE(approval_reason,$3)
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution["id"],
                    step_id,
                    reason,
                )
                event = orchestration_event(
                    execution_id=execution["id"],
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type="STEP_WAITING_APPROVAL",
                    detail={"stepId": step_id, "reason": reason},
                )
                await self._insert_outbox(
                    conn, execution["id"], ORCHESTRATION_SUBJECT, event
                )

    async def decide_step_approval(
        self,
        execution_id: UUID,
        step_id: str,
        *,
        approved: bool,
        actor: str,
        comment: str | None,
    ) -> bool:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                execution = await conn.fetchrow(
                    "SELECT * FROM executions WHERE id=$1 FOR UPDATE",
                    execution_id,
                )
                step = await conn.fetchrow(
                    """
                    SELECT * FROM execution_plan_steps
                    WHERE execution_id=$1 AND step_id=$2 FOR UPDATE
                    """,
                    execution_id,
                    step_id,
                )
                if not execution or not step or step["approval_status"] != "PENDING":
                    return False

                approval_status = "APPROVED" if approved else "REJECTED"
                step_status = "PENDING" if approved else "CANCELLED"
                await conn.execute(
                    """
                    UPDATE execution_plan_steps
                    SET approval_status=$3,approval_actor=$4,approval_comment=$5,
                        approval_updated_at=now(),status=$6
                    WHERE execution_id=$1 AND step_id=$2
                    """,
                    execution_id,
                    step_id,
                    approval_status,
                    actor,
                    comment,
                    step_status,
                )
                if approved:
                    await conn.execute(
                        """
                        UPDATE executions
                        SET status='ACCEPTED',control_action='RESUME',
                            control_reason=NULL,lease_owner=NULL,lease_expires_at=NULL,
                            resumed_at=now(),updated_at=now()
                        WHERE id=$1
                        """,
                        execution_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE executions
                        SET status='CANCELLED',control_action='NONE',
                            control_reason=$2,cancelled_at=now(),completed_at=now(),
                            lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                        WHERE id=$1
                        """,
                        execution_id,
                        comment or f"Approval rejected for step {step_id}",
                    )
                    await conn.execute(
                        """
                        UPDATE execution_plans
                        SET status='CANCELLED',completed_at=now(),updated_at=now()
                        WHERE execution_id=$1
                        """,
                        execution_id,
                    )
                    await conn.execute(
                        """
                        UPDATE execution_plan_steps
                        SET status='CANCELLED',
                            completed_at=COALESCE(completed_at,now())
                        WHERE execution_id=$1
                          AND step_id<>$2
                          AND status NOT IN ('COMPLETED','FAILED','CANCELLED')
                        """,
                        execution_id,
                        step_id,
                    )

                event = orchestration_event(
                    execution_id=execution_id,
                    correlation_id=execution["correlation_id"],
                    causation_id=execution["request_message_id"],
                    command_name=execution["command_name"],
                    event_type=(
                        "STEP_APPROVED" if approved else "STEP_REJECTED"
                    ),
                    detail={
                        "stepId": step_id,
                        "actor": actor,
                        "comment": comment,
                    },
                )
                await self._insert_outbox(
                    conn, execution_id, ORCHESTRATION_SUBJECT, event
                )
                if not approved:
                    cancelled = lifecycle_event(
                        execution_id=execution_id,
                        correlation_id=execution["correlation_id"],
                        causation_id=event["messageId"],
                        command_name=execution["command_name"],
                        status="CANCELLED",
                        event_type="EXECUTION_CANCELLED",
                        sequence=3,
                        detail={
                            "reason": comment
                            or f"Approval rejected for step {step_id}"
                        },
                    )
                    await self._insert_outbox(
                        conn, execution_id, LIFECYCLE_SUBJECT, cancelled
                    )
                return True

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
            for field in ("knowledge_bases", "depends_on", "usage", "output", "error", "retry_policy"):
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
        waiting_approvals = [
            {
                "stepId": step["step_id"],
                "description": step["description"],
                "agent": step["agent_name"],
                "reason": step.get("approval_reason"),
            }
            for step in step_data
            if step["status"] == "WAITING_APPROVAL"
        ]
        retrying_steps = [
            {
                "stepId": step["step_id"],
                "attemptCount": step.get("attempt_count", 0),
                "maxAttempts": step.get("max_attempts", 1),
                "nextRetryAt": step.get("next_retry_at"),
                "error": step.get("error"),
            }
            for step in step_data
            if step["status"] == "RETRYING"
        ]
        return {
            "plan": plan_data,
            "steps": step_data,
            "activeAgents": active_agents,
            "waitingApprovals": waiting_approvals,
            "retryingSteps": retrying_steps,
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
    @staticmethod
    def _estimate_tokens(value: Any) -> int:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
        return max(1, len(text) // 4)

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
