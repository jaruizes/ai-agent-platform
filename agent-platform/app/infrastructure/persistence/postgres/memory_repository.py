from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.memory import MemoryEntry, Session, WorkingContextEntry
from app.infrastructure.persistence.postgres.database import Database


class PostgresMemoryRepository:
    def __init__(self, database: Database):
        self._db = database

    async def create_session(self, session: Session) -> Session:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions(
                    id,name,status,scope,owner_key,metadata,expires_at
                ) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7)
                RETURNING *
                """,
                session.id,
                session.name,
                session.status,
                session.scope,
                session.owner_key,
                json.dumps(session.metadata),
                session.expires_at,
            )
        return self._session(row)

    async def get_session(self, session_id: UUID) -> Session | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM sessions WHERE id=$1", session_id)
        return self._session(row) if row else None

    async def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Session]:
        async with self._db.require_pool().acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE status=$1
                    ORDER BY updated_at DESC
                    LIMIT $2
                    """,
                    status,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT $1",
                    limit,
                )
        return [self._session(row) for row in rows]

    async def update_session(
        self,
        session_id: UUID,
        *,
        name: str | None,
        scope: str,
        owner_key: str | None,
        metadata: dict[str, Any],
        expires_at: datetime | None,
    ) -> Session | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE sessions
                SET name=$2,scope=$3,owner_key=$4,metadata=$5::jsonb,
                    expires_at=$6,updated_at=now()
                WHERE id=$1 AND status='ACTIVE'
                RETURNING *
                """,
                session_id,
                name,
                scope,
                owner_key,
                json.dumps(metadata),
                expires_at,
            )
        return self._session(row) if row else None

    async def close_session(self, session_id: UUID) -> Session | None:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE sessions
                    SET status='CLOSED',closed_at=now(),updated_at=now()
                    WHERE id=$1 AND status='ACTIVE'
                    RETURNING *
                    """,
                    session_id,
                )
                if not row:
                    return None
                await conn.execute(
                    """
                    UPDATE memory_entries
                    SET status='EXPIRED',updated_at=now()
                    WHERE scope_type='SESSION'
                      AND scope_id=$1
                      AND status='ACTIVE'
                    """,
                    str(session_id),
                )
        return self._session(row)

    async def list_session_executions(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id,correlation_id,command_name,intent,status,result,error,
                       created_at,updated_at,completed_at
                FROM executions
                WHERE session_id=$1
                ORDER BY created_at
                LIMIT $2
                """,
                session_id,
                limit,
            )
        return [dict(row) for row in rows]

    async def add_context_entry(
        self,
        entry: WorkingContextEntry,
    ) -> WorkingContextEntry:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO execution_context_entries(
                    id,execution_id,session_id,step_id,entry_type,entry_key,
                    content,priority,token_estimate,source_type,source_ref,provenance
                ) VALUES(
                    $1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12::jsonb
                )
                RETURNING *
                """,
                entry.id,
                entry.execution_id,
                entry.session_id,
                entry.step_id,
                entry.entry_type,
                entry.entry_key,
                json.dumps(entry.content),
                entry.priority,
                entry.token_estimate,
                entry.source_type,
                entry.source_ref,
                json.dumps(entry.provenance),
            )
        return self._context(row)

    async def list_execution_context(
        self,
        execution_id: UUID,
    ) -> list[WorkingContextEntry]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM execution_context_entries
                WHERE execution_id=$1
                ORDER BY created_at,id
                """,
                execution_id,
            )
        return [self._context(row) for row in rows]

    async def list_session_context(
        self,
        session_id: UUID,
        *,
        limit: int = 500,
    ) -> list[WorkingContextEntry]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM execution_context_entries
                WHERE session_id=$1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                session_id,
                limit,
            )
        return [self._context(row) for row in reversed(rows)]

    async def create_memory(self, memory: MemoryEntry) -> MemoryEntry:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                superseded_id = None
                if memory.memory_key:
                    existing = await conn.fetchrow(
                        """
                        SELECT id FROM memory_entries
                        WHERE scope_type=$1 AND scope_id=$2 AND memory_key=$3
                          AND status='ACTIVE'
                        FOR UPDATE
                        """,
                        memory.scope_type,
                        memory.scope_id,
                        memory.memory_key,
                    )
                    if existing:
                        superseded_id = existing["id"]
                        await conn.execute(
                            """
                            UPDATE memory_entries
                            SET status='SUPERSEDED',updated_at=now()
                            WHERE id=$1
                            """,
                            superseded_id,
                        )

                row = await conn.fetchrow(
                    """
                    INSERT INTO memory_entries(
                        id,scope_type,scope_id,memory_type,memory_key,content,
                        metadata,confidence,importance,explicit,status,
                        policy_decision,source_execution_id,source_step_id,
                        supersedes_memory_id,expires_at
                    ) VALUES(
                        $1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,'ACTIVE',
                        $11::jsonb,$12,$13,$14,$15
                    )
                    RETURNING *
                    """,
                    memory.id,
                    memory.scope_type,
                    memory.scope_id,
                    memory.memory_type,
                    memory.memory_key,
                    memory.content,
                    json.dumps(memory.metadata),
                    memory.confidence,
                    memory.importance,
                    memory.explicit,
                    json.dumps(memory.policy_decision),
                    memory.source_execution_id,
                    memory.source_step_id,
                    superseded_id,
                    memory.expires_at,
                )
        return self._memory(row)

    async def get_memory(self, memory_id: UUID) -> MemoryEntry | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memory_entries WHERE id=$1",
                memory_id,
            )
        return self._memory(row) if row else None

    async def list_memories(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        memory_type: str | None = None,
        status: str = "ACTIVE",
        query: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        clauses = ["status=$1"]
        values: list[Any] = [status]
        if scope_type:
            values.append(scope_type)
            clauses.append(f"scope_type=${len(values)}")
        if scope_id:
            values.append(scope_id)
            clauses.append(f"scope_id=${len(values)}")
        if memory_type:
            values.append(memory_type)
            clauses.append(f"memory_type=${len(values)}")
        if query:
            values.append(f"%{query}%")
            clauses.append(f"content ILIKE ${len(values)}")
        values.append(limit)
        limit_param = f"${len(values)}"
        sql = (
            "SELECT * FROM memory_entries WHERE "
            + " AND ".join(clauses)
            + f" ORDER BY importance DESC,updated_at DESC LIMIT {limit_param}"
        )
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(sql, *values)
        return [self._memory(row) for row in rows]

    async def revoke_memory(self, memory_id: UUID) -> MemoryEntry | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE memory_entries
                SET status='REVOKED',revoked_at=now(),updated_at=now()
                WHERE id=$1 AND status='ACTIVE'
                RETURNING *
                """,
                memory_id,
            )
        return self._memory(row) if row else None

    async def record_policy_audit(
        self,
        *,
        candidate: dict[str, Any],
        decision: dict[str, Any],
        memory_id: UUID | None,
        source_execution_id: UUID | None,
        audit_id: UUID,
    ) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_policy_audit(
                    id,memory_id,candidate,decision,source_execution_id
                ) VALUES($1,$2,$3::jsonb,$4::jsonb,$5)
                """,
                audit_id,
                memory_id,
                json.dumps(candidate),
                json.dumps(decision),
                source_execution_id,
            )

    async def list_policy_audit(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id,memory_id,candidate,decision,source_execution_id,created_at
                FROM memory_policy_audit
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["candidate"] = self._decode(item["candidate"]) or {}
            item["decision"] = self._decode(item["decision"]) or {}
            result.append(item)
        return result

    async def expire_sessions(self) -> int:
        pool = self._db.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    UPDATE sessions
                    SET status='CLOSED',closed_at=now(),updated_at=now()
                    WHERE status='ACTIVE'
                      AND expires_at IS NOT NULL
                      AND expires_at <= now()
                    RETURNING id
                    """
                )
                for row in rows:
                    await conn.execute(
                        """
                        UPDATE memory_entries
                        SET status='EXPIRED',updated_at=now()
                        WHERE scope_type='SESSION'
                          AND scope_id=$1
                          AND status='ACTIVE'
                        """,
                        str(row["id"]),
                    )
        return len(rows)

    async def expire_memories(self) -> int:
        async with self._db.require_pool().acquire() as conn:
            result = await conn.execute(
                """
                UPDATE memory_entries
                SET status='EXPIRED',updated_at=now()
                WHERE status='ACTIVE'
                  AND expires_at IS NOT NULL
                  AND expires_at <= now()
                """
            )
        return int(result.split()[-1])

    @staticmethod
    def _decode(value):
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _session(cls, row) -> Session:
        return Session(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            scope=row["scope"],
            owner_key=row["owner_key"],
            metadata=dict(cls._decode(row["metadata"]) or {}),
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
        )

    @classmethod
    def _context(cls, row) -> WorkingContextEntry:
        return WorkingContextEntry(
            id=row["id"],
            execution_id=row["execution_id"],
            session_id=row["session_id"],
            step_id=row["step_id"],
            entry_type=row["entry_type"],
            entry_key=row["entry_key"],
            content=dict(cls._decode(row["content"]) or {}),
            priority=row["priority"],
            token_estimate=row["token_estimate"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            provenance=dict(cls._decode(row["provenance"]) or {}),
            created_at=row["created_at"],
        )

    @classmethod
    def _memory(cls, row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            scope_type=row["scope_type"],
            scope_id=row["scope_id"],
            memory_type=row["memory_type"],
            memory_key=row["memory_key"],
            content=row["content"],
            metadata=dict(cls._decode(row["metadata"]) or {}),
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            explicit=row["explicit"],
            status=row["status"],
            policy_decision=dict(cls._decode(row["policy_decision"]) or {}),
            source_execution_id=row["source_execution_id"],
            source_step_id=row["source_step_id"],
            supersedes_memory_id=row["supersedes_memory_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )
