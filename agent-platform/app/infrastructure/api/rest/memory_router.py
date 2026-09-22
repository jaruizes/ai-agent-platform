from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.business.memory_service import MemoryService
from app.domain.memory import MemoryCandidate, MemoryEntry, Session, WorkingContextEntry
from app.infrastructure.api.rest.memory_schemas import (
    MemoryCandidateRequest,
    MemoryRequest,
    SessionRequest,
)


def create_memory_router(service: MemoryService) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["context-memory"])

    @router.post("/sessions")
    async def create_session(request: SessionRequest) -> dict[str, Any]:
        try:
            session = await service.create_session(
                name=request.name,
                scope=request.scope,
                owner_key=request.ownerKey,
                metadata=request.metadata,
                expires_at=request.expiresAt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _session(session)

    @router.get("/sessions")
    async def list_sessions(
        status: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        try:
            sessions = await service.list_sessions(status=status, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [_session(item) for item in sessions]

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: UUID) -> dict[str, Any]:
        session = await service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return _session(session)

    @router.put("/sessions/{session_id}")
    async def update_session(
        session_id: UUID,
        request: SessionRequest,
    ) -> dict[str, Any]:
        try:
            session = await service.update_session(
                session_id,
                name=request.name,
                scope=request.scope,
                owner_key=request.ownerKey,
                metadata=request.metadata,
                expires_at=request.expiresAt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not session:
            raise HTTPException(
                status_code=409,
                detail="Session not found or not ACTIVE",
            )
        return _session(session)

    @router.post("/sessions/{session_id}/close")
    async def close_session(session_id: UUID) -> dict[str, Any]:
        session = await service.close_session(session_id)
        if not session:
            raise HTTPException(
                status_code=409,
                detail="Session not found or already closed",
            )
        return _session(session)

    @router.get("/sessions/{session_id}/executions")
    async def session_executions(
        session_id: UUID,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        if not await service.get_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        rows = await service.list_session_executions(session_id, limit=limit)
        return [{**row, "id": str(row["id"])} for row in rows]

    @router.get("/sessions/{session_id}/context")
    async def session_context(
        session_id: UUID,
        limit: int = Query(default=500, ge=1, le=2000),
    ) -> list[dict[str, Any]]:
        if not await service.get_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return [
            _context(entry)
            for entry in await service.session_context(session_id, limit=limit)
        ]

    @router.get("/executions/{execution_id}/context")
    async def execution_context(execution_id: UUID) -> list[dict[str, Any]]:
        return [
            _context(entry)
            for entry in await service.execution_context(execution_id)
        ]

    @router.get("/memories")
    async def list_memories(
        scopeType: str | None = None,
        scopeId: str | None = None,
        memoryType: str | None = None,
        status: str = "ACTIVE",
        q: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        try:
            memories = await service.list_memories(
                scope_type=scopeType,
                scope_id=scopeId,
                memory_type=memoryType,
                status=status,
                query=q,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [_memory(memory) for memory in memories]

    @router.get("/memories/{memory_id}")
    async def get_memory(memory_id: UUID) -> dict[str, Any]:
        memory = await service.get_memory(memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        return _memory(memory)

    @router.post("/memories")
    async def create_explicit_memory(
        request: MemoryRequest,
    ) -> dict[str, Any]:
        candidate = MemoryCandidate(
            scope_type=request.scopeType,
            scope_id=request.scopeId,
            memory_type=request.memoryType,
            memory_key=request.key,
            content=request.content,
            metadata=request.metadata,
            confidence=1.0,
            importance=request.importance,
            explicit=True,
            source_execution_id=request.sourceExecutionId,
            source_step_id=request.sourceStepId,
            expires_at=request.expiresAt,
        )
        memory, decision = await service.create_memory(candidate)
        if not memory:
            raise HTTPException(
                status_code=422,
                detail={"policy": decision.as_dict()},
            )
        return {"memory": _memory(memory), "policy": decision.as_dict()}

    @router.post("/memory-candidates/evaluate")
    async def evaluate_memory_candidate(
        request: MemoryCandidateRequest,
    ) -> dict[str, Any]:
        candidate = MemoryCandidate(
            scope_type=request.scopeType,
            scope_id=request.scopeId,
            memory_type=request.memoryType,
            memory_key=request.key,
            content=request.content,
            metadata=request.metadata,
            confidence=request.confidence,
            importance=request.importance,
            explicit=request.explicit,
            source_execution_id=request.sourceExecutionId,
            source_step_id=request.sourceStepId,
            expires_at=request.expiresAt,
        )
        memory, decision = await service.create_memory(candidate)
        return {
            "persisted": memory is not None,
            "memory": _memory(memory) if memory else None,
            "policy": decision.as_dict(),
        }

    @router.post("/memories/{memory_id}/revoke")
    async def revoke_memory(memory_id: UUID) -> dict[str, Any]:
        memory = await service.revoke_memory(memory_id)
        if not memory:
            raise HTTPException(
                status_code=409,
                detail="Memory not found or not ACTIVE",
            )
        return _memory(memory)

    @router.get("/memory-policy")
    async def memory_policy() -> dict[str, Any]:
        return service.policy_description()

    @router.get("/memory-policy/audit")
    async def memory_policy_audit(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        rows = await service.policy_audit(limit=limit)
        return [
            {
                **row,
                "id": str(row["id"]),
                "memory_id": (
                    str(row["memory_id"])
                    if row.get("memory_id")
                    else None
                ),
                "source_execution_id": (
                    str(row["source_execution_id"])
                    if row.get("source_execution_id")
                    else None
                ),
            }
            for row in rows
        ]

    return router


def _session(item: Session) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "status": item.status,
        "scope": item.scope,
        "ownerKey": item.owner_key,
        "metadata": item.metadata,
        "expiresAt": item.expires_at,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
        "closedAt": item.closed_at,
    }


def _context(item: WorkingContextEntry) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "executionId": str(item.execution_id),
        "sessionId": str(item.session_id) if item.session_id else None,
        "stepId": item.step_id,
        "type": item.entry_type,
        "key": item.entry_key,
        "content": item.content,
        "priority": item.priority,
        "tokenEstimate": item.token_estimate,
        "sourceType": item.source_type,
        "sourceRef": item.source_ref,
        "provenance": item.provenance,
        "createdAt": item.created_at,
    }


def _memory(item: MemoryEntry) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "scopeType": item.scope_type,
        "scopeId": item.scope_id,
        "memoryType": item.memory_type,
        "key": item.memory_key,
        "content": item.content,
        "metadata": item.metadata,
        "confidence": item.confidence,
        "importance": item.importance,
        "explicit": item.explicit,
        "status": item.status,
        "policyDecision": item.policy_decision,
        "sourceExecutionId": (
            str(item.source_execution_id)
            if item.source_execution_id
            else None
        ),
        "sourceStepId": item.source_step_id,
        "supersedesMemoryId": (
            str(item.supersedes_memory_id)
            if item.supersedes_memory_id
            else None
        ),
        "expiresAt": item.expires_at,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
        "revokedAt": item.revoked_at,
    }
