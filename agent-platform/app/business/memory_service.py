from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.business.memory_policy import MemoryPolicyEngine
from app.business.ports import MemoryRepositoryPort
from app.domain.execution import Command
from app.domain.memory import (
    CONTEXT_ENTRY_TYPES,
    MEMORY_STATUSES,
    SESSION_SCOPES,
    SESSION_STATUSES,
    MemoryCandidate,
    MemoryEntry,
    MemoryPolicyDecision,
    Session,
    WorkingContextEntry,
)

class MemoryService:
    def __init__(
        self,
        repository: MemoryRepositoryPort,
        policy: MemoryPolicyEngine,
        *,
        cleanup_poll_seconds: float,
    ):
        self._repository = repository
        self._policy = policy
        self._cleanup_poll_seconds = cleanup_poll_seconds
        self._stop = asyncio.Event()

    async def create_session(
        self,
        *,
        name: str | None,
        scope: str,
        owner_key: str | None,
        metadata: dict[str, Any],
        expires_at: datetime | None,
    ) -> Session:
        normalized_scope = scope.upper()
        if normalized_scope not in SESSION_SCOPES:
            raise ValueError(
                "Session scope must be one of USER, TEAM or TENANT"
            )
        return await self._repository.create_session(
            Session(
                name=name,
                scope=normalized_scope,
                owner_key=owner_key,
                metadata=metadata,
                expires_at=expires_at,
            )
        )

    async def get_session(self, session_id: UUID) -> Session | None:
        return await self._repository.get_session(session_id)

    async def require_active_session(self, session_id: UUID) -> Session:
        session = await self._repository.get_session(session_id)
        if not session:
            raise LookupError(f"Session '{session_id}' does not exist")
        if session.status != "ACTIVE":
            raise ValueError(f"Session '{session_id}' is not ACTIVE")
        if session.expires_at:
            now = datetime.now(session.expires_at.tzinfo or timezone.utc)
            if session.expires_at <= now:
                raise ValueError(f"Session '{session_id}' has expired")
        return session

    async def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Session]:
        normalized = status.upper() if status else None
        if normalized and normalized not in SESSION_STATUSES:
            raise ValueError(f"Unsupported session status '{status}'")
        return await self._repository.list_sessions(
            status=normalized,
            limit=limit,
        )

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
        normalized_scope = scope.upper()
        if normalized_scope not in SESSION_SCOPES:
            raise ValueError(
                "Session scope must be one of USER, TEAM or TENANT"
            )
        return await self._repository.update_session(
            session_id,
            name=name,
            scope=normalized_scope,
            owner_key=owner_key,
            metadata=metadata,
            expires_at=expires_at,
        )

    async def close_session(self, session_id: UUID) -> Session | None:
        return await self._repository.close_session(session_id)

    async def list_session_executions(
        self,
        session_id: UUID,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._repository.list_session_executions(
            session_id,
            limit=limit,
        )

    async def capture_submission(
        self,
        *,
        execution_id: UUID,
        session_id: UUID | None,
        command: Command,
    ) -> None:
        await self.record_context(
            WorkingContextEntry(
                execution_id=execution_id,
                session_id=session_id,
                entry_type="COMMAND",
                entry_key="command",
                content={
                    "name": command.name,
                    "intent": command.intent,
                    "input": command.input,
                    "context": command.context,
                    "metadata": command.metadata,
                },
                priority=100,
                token_estimate=self._estimate_tokens(
                    {
                        "intent": command.intent,
                        "input": command.input,
                        "context": command.context,
                    }
                ),
                source_type="COMMAND",
            )
        )
        for index, instruction in enumerate(command.instructions):
            await self.record_context(
                WorkingContextEntry(
                    execution_id=execution_id,
                    session_id=session_id,
                    entry_type="INSTRUCTION",
                    entry_key=f"instruction:{index}",
                    content={"text": instruction},
                    priority=100,
                    token_estimate=self._estimate_tokens(instruction),
                    source_type="COMMAND",
                )
            )

    async def record_plan(
        self,
        *,
        execution_id: UUID,
        session_id: UUID | None,
        plan: dict[str, Any],
    ) -> None:
        await self.record_context(
            WorkingContextEntry(
                execution_id=execution_id,
                session_id=session_id,
                entry_type="PLAN",
                entry_key="logical-plan",
                content=plan,
                priority=90,
                token_estimate=self._estimate_tokens(plan),
                source_type="PLANNER",
            )
        )

    async def record_step_result(
        self,
        *,
        execution_id: UUID,
        session_id: UUID | None,
        step_id: str,
        step_type: str,
        output: dict[str, Any],
    ) -> None:
        entry_type = {
            "TOOL": "TOOL_RESULT",
            "KNOWLEDGE": "KNOWLEDGE",
        }.get(step_type, "STEP_RESULT")
        await self.record_context(
            WorkingContextEntry(
                execution_id=execution_id,
                session_id=session_id,
                step_id=step_id,
                entry_type=entry_type,
                entry_key=f"step:{step_id}",
                content=output,
                priority=80,
                token_estimate=self._estimate_tokens(output),
                source_type=step_type,
                source_ref=step_id,
                provenance={"stepId": step_id, "stepType": step_type},
            )
        )

    async def record_context(
        self,
        entry: WorkingContextEntry,
    ) -> WorkingContextEntry:
        if entry.entry_type not in CONTEXT_ENTRY_TYPES:
            raise ValueError(f"Unsupported context entry type '{entry.entry_type}'")
        return await self._repository.add_context_entry(entry)

    async def execution_context(
        self,
        execution_id: UUID,
    ) -> list[WorkingContextEntry]:
        return await self._repository.list_execution_context(execution_id)

    async def session_context(
        self,
        session_id: UUID,
        *,
        limit: int = 500,
    ) -> list[WorkingContextEntry]:
        return await self._repository.list_session_context(
            session_id,
            limit=limit,
        )

    async def create_memory(
        self,
        candidate: MemoryCandidate,
    ) -> tuple[MemoryEntry | None, MemoryPolicyDecision]:
        if candidate.scope_type.upper() == "SESSION":
            try:
                session_id = UUID(candidate.scope_id)
            except ValueError:
                return None, MemoryPolicyDecision(
                    allowed=False,
                    action="REJECT",
                    reasons=["SESSION scopeId must be a UUID"],
                )
            session = await self._repository.get_session(session_id)
            if not session:
                return None, MemoryPolicyDecision(
                    allowed=False,
                    action="REJECT",
                    reasons=["SESSION scopeId does not reference an existing session"],
                )
            if session.status != "ACTIVE":
                return None, MemoryPolicyDecision(
                    allowed=False,
                    action="REJECT",
                    reasons=["SESSION-scoped memory requires an ACTIVE session"],
                )

        decision = self._policy.evaluate(candidate)
        candidate_snapshot = {
            "scopeType": candidate.scope_type,
            "scopeId": candidate.scope_id,
            "memoryType": candidate.memory_type,
            "key": candidate.memory_key,
            "contentLength": len(candidate.content),
            "contentSha256": hashlib.sha256(
                candidate.content.encode("utf-8")
            ).hexdigest(),
            "metadata": candidate.metadata,
            "confidence": candidate.confidence,
            "importance": candidate.importance,
            "explicit": candidate.explicit,
            "sourceExecutionId": (
                str(candidate.source_execution_id)
                if candidate.source_execution_id
                else None
            ),
            "sourceStepId": candidate.source_step_id,
            "expiresAt": (
                candidate.expires_at.isoformat()
                if candidate.expires_at
                else None
            ),
        }
        if not decision.allowed:
            from uuid import uuid4

            await self._repository.record_policy_audit(
                candidate=candidate_snapshot,
                decision=decision.as_dict(),
                memory_id=None,
                source_execution_id=candidate.source_execution_id,
                audit_id=uuid4(),
            )
            return None, decision

        memory = MemoryEntry(
            scope_type=decision.normalized_scope_type or candidate.scope_type,
            scope_id=candidate.scope_id.strip(),
            memory_type=decision.normalized_memory_type or candidate.memory_type,
            memory_key=(
                candidate.memory_key.strip()
                if candidate.memory_key and candidate.memory_key.strip()
                else None
            ),
            content=candidate.content.strip(),
            metadata=candidate.metadata,
            confidence=candidate.confidence,
            importance=candidate.importance,
            explicit=candidate.explicit,
            policy_decision=decision.as_dict(),
            source_execution_id=candidate.source_execution_id,
            source_step_id=candidate.source_step_id,
            expires_at=candidate.expires_at,
        )
        persisted = await self._repository.create_memory(memory)
        from uuid import uuid4

        await self._repository.record_policy_audit(
            candidate=candidate_snapshot,
            decision=decision.as_dict(),
            memory_id=persisted.id,
            source_execution_id=candidate.source_execution_id,
            audit_id=uuid4(),
        )
        return persisted, decision

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
        normalized_status = status.upper()
        if normalized_status not in MEMORY_STATUSES:
            raise ValueError(f"Unsupported memory status '{status}'")
        return await self._repository.list_memories(
            scope_type=scope_type.upper() if scope_type else None,
            scope_id=scope_id,
            memory_type=memory_type.upper() if memory_type else None,
            status=normalized_status,
            query=query,
            limit=limit,
        )

    async def get_memory(self, memory_id: UUID) -> MemoryEntry | None:
        return await self._repository.get_memory(memory_id)

    async def revoke_memory(self, memory_id: UUID) -> MemoryEntry | None:
        return await self._repository.revoke_memory(memory_id)

    def policy_description(self) -> dict[str, Any]:
        return self._policy.describe()

    async def cleanup_loop(self) -> None:
        while not self._stop.is_set():
            await self._repository.expire_sessions()
            await self._repository.expire_memories()
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._cleanup_poll_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _estimate_tokens(value: Any) -> int:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
        return max(1, len(text) // 4)
