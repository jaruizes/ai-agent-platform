from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.business.embeddings import EmbeddingProvider
from app.business.memory_policy import MemoryPolicyEngine
from app.business.ports import MemoryRepositoryPort
from app.domain.context import ContextSnapshot
from app.domain.memory import (
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
        embedding_provider: EmbeddingProvider,
        *,
        cleanup_poll_seconds: float,
    ):
        self._repository = repository
        self._policy = policy
        self._embedding_provider = embedding_provider
        self._cleanup_poll_seconds = cleanup_poll_seconds
        self._stop = asyncio.Event()

    @staticmethod
    def _validate_session_definition(
        *,
        scope: str,
        owner_key: str | None,
        expires_at: datetime | None,
    ) -> tuple[str, datetime | None]:
        normalized_scope = scope.upper()
        if normalized_scope not in SESSION_SCOPES:
            raise ValueError(
                "Session scope must be one of USER, TEAM or TENANT"
            )
        if normalized_scope in {"USER", "TEAM"} and not (
            owner_key and owner_key.strip()
        ):
            raise ValueError(
                f"ownerKey is required for {normalized_scope} sessions"
            )
        normalized_expiry = MemoryService._normalize_datetime(expires_at)
        if normalized_expiry and normalized_expiry <= datetime.now(timezone.utc):
            raise ValueError("expiresAt must be in the future")
        return normalized_scope, normalized_expiry

    async def create_session(
        self,
        *,
        name: str | None,
        scope: str,
        owner_key: str | None,
        metadata: dict[str, Any],
        expires_at: datetime | None,
    ) -> Session:
        normalized_scope, normalized_expiry = self._validate_session_definition(
            scope=scope,
            owner_key=owner_key,
            expires_at=expires_at,
        )
        return await self._repository.create_session(
            Session(
                name=name,
                scope=normalized_scope,
                owner_key=owner_key,
                metadata=metadata,
                expires_at=normalized_expiry,
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
        normalized_scope, normalized_expiry = self._validate_session_definition(
            scope=scope,
            owner_key=owner_key,
            expires_at=expires_at,
        )
        return await self._repository.update_session(
            session_id,
            name=name,
            scope=normalized_scope,
            owner_key=owner_key,
            metadata=metadata,
            expires_at=normalized_expiry,
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
        candidate_snapshot = self._candidate_snapshot(candidate)
        decision = self._policy.evaluate(candidate)

        if decision.allowed and candidate.scope_type.upper() == "SESSION":
            try:
                session_id = UUID(candidate.scope_id)
            except ValueError:
                decision = MemoryPolicyDecision(
                    allowed=False,
                    action="REJECT",
                    reasons=["SESSION scopeId must be a UUID"],
                    normalized_scope_type="SESSION",
                    normalized_memory_type=decision.normalized_memory_type,
                )
            else:
                session = await self._repository.get_session(session_id)
                if not session:
                    decision = MemoryPolicyDecision(
                        allowed=False,
                        action="REJECT",
                        reasons=[
                            "SESSION scopeId does not reference an existing session"
                        ],
                        normalized_scope_type="SESSION",
                        normalized_memory_type=decision.normalized_memory_type,
                    )
                elif session.status != "ACTIVE":
                    decision = MemoryPolicyDecision(
                        allowed=False,
                        action="REJECT",
                        reasons=[
                            "SESSION-scoped memory requires an ACTIVE session"
                        ],
                        normalized_scope_type="SESSION",
                        normalized_memory_type=decision.normalized_memory_type,
                    )
                elif session.expires_at and session.expires_at <= datetime.now(
                    session.expires_at.tzinfo or timezone.utc
                ):
                    decision = MemoryPolicyDecision(
                        allowed=False,
                        action="REJECT",
                        reasons=["SESSION-scoped memory cannot target an expired session"],
                        normalized_scope_type="SESSION",
                        normalized_memory_type=decision.normalized_memory_type,
                    )

        if not decision.allowed:
            await self._repository.record_policy_audit(
                candidate=candidate_snapshot,
                decision=decision.as_dict(),
                memory_id=None,
                source_execution_id=candidate.source_execution_id,
                audit_id=uuid4(),
            )
            return None, decision

        embedding_result = await self._embedding_provider.embed(
            [candidate.content.strip()[:8000]]
        )
        if not embedding_result.vectors or len(embedding_result.vectors[0]) != 768:
            raise RuntimeError(
                "Persistent Memory storage expects 768-dimensional embeddings"
            )

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
            metadata={
                **candidate.metadata,
                "embeddingProvider": self._embedding_provider.provider_key,
                "embeddingModel": self._embedding_provider.model,
                "embeddingDimensions": self._embedding_provider.dimensions,
            },
            confidence=candidate.confidence,
            importance=candidate.importance,
            explicit=candidate.explicit,
            policy_decision=decision.as_dict(),
            source_execution_id=candidate.source_execution_id,
            source_step_id=candidate.source_step_id,
            expires_at=self._normalize_datetime(candidate.expires_at),
            embedding=embedding_result.vectors[0],
        )
        persisted = await self._repository.create_memory(
            memory,
            audit_candidate=candidate_snapshot,
            audit_decision=decision.as_dict(),
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

    async def persist_candidates(
        self,
        candidates: list[MemoryCandidate],
    ) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        for candidate in candidates:
            memory, decision = await self.create_memory(candidate)
            decisions.append(
                {
                    "persisted": memory is not None,
                    "memoryId": str(memory.id) if memory else None,
                    "policy": decision.as_dict(),
                }
            )
        return decisions

    async def retrieve_relevant(
        self,
        *,
        query: str,
        scopes: list[tuple[str, str]],
        limit: int = 8,
    ) -> list[MemoryEntry]:
        normalized_scopes = list(
            dict.fromkeys(
                (
                    scope_type.upper().strip(),
                    scope_id.strip(),
                )
                for scope_type, scope_id in scopes
                if scope_type and scope_id
            )
        )
        if not query.strip() or not normalized_scopes:
            return []
        embedding_result = await self._embedding_provider.embed(
            [query.strip()[:1600]]
        )
        vector = embedding_result.vectors[0]
        if len(vector) != 768:
            raise RuntimeError(
                "Persistent Memory storage expects 768-dimensional embeddings"
            )
        return await self._repository.retrieve_memories(
            scopes=normalized_scopes,
            query=query.strip()[:1600],
            query_embedding=vector,
            limit=max(1, min(limit, 50)),
        )

    async def save_context_snapshot(
        self,
        snapshot: ContextSnapshot,
    ) -> ContextSnapshot:
        return await self._repository.save_context_snapshot(snapshot)

    async def context_snapshots(
        self,
        execution_id: UUID,
        *,
        step_id: str | None = None,
    ) -> list[ContextSnapshot]:
        return await self._repository.list_context_snapshots(
            execution_id,
            step_id=step_id,
        )

    async def get_memory(self, memory_id: UUID) -> MemoryEntry | None:
        return await self._repository.get_memory(memory_id)

    async def revoke_memory(self, memory_id: UUID) -> MemoryEntry | None:
        return await self._repository.revoke_memory(memory_id)

    def policy_description(self) -> dict[str, Any]:
        return self._policy.describe()

    async def policy_audit(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._repository.list_policy_audit(limit=limit)

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
    def _candidate_snapshot(candidate: MemoryCandidate) -> dict[str, Any]:
        return {
            "scopeType": candidate.scope_type,
            "scopeId": candidate.scope_id,
            "memoryType": candidate.memory_type,
            "key": candidate.memory_key,
            "contentLength": len(candidate.content),
            "contentSha256": hashlib.sha256(
                candidate.content.encode("utf-8")
            ).hexdigest(),
            "metadataKeys": sorted(candidate.metadata.keys()),
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

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
