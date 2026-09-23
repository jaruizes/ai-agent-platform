from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


SESSION_STATUSES = {"ACTIVE", "CLOSED"}
SESSION_SCOPES = {"USER", "TEAM", "TENANT"}
MEMORY_SCOPE_TYPES = {"SESSION", "USER", "TEAM", "TENANT", "AGENT"}
MEMORY_TYPES = {
    "FACT",
    "PREFERENCE",
    "DECISION",
    "CONSTRAINT",
    "SUMMARY",
    "LEARNED_CONTEXT",
}
MEMORY_STATUSES = {"ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"}
CONTEXT_ENTRY_TYPES = {
    "COMMAND",
    "FACT",
    "STEP_RESULT",
    "TOOL_RESULT",
    "KNOWLEDGE",
    "ARTIFACT",
    "INSTRUCTION",
    "SUMMARY",
    "PLAN",
}


@dataclass(frozen=True)
class Session:
    id: UUID = field(default_factory=uuid4)
    name: str | None = None
    status: str = "ACTIVE"
    scope: str = "TENANT"
    owner_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None


@dataclass(frozen=True)
class WorkingContextEntry:
    execution_id: UUID
    entry_type: str
    content: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    session_id: UUID | None = None
    step_id: str | None = None
    entry_key: str | None = None
    priority: int = 50
    token_estimate: int = 0
    source_type: str = "PLATFORM"
    source_ref: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class MemoryEntry:
    scope_type: str
    scope_id: str
    memory_type: str
    content: str
    id: UUID = field(default_factory=uuid4)
    memory_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    importance: float = 0.5
    explicit: bool = False
    status: str = "ACTIVE"
    policy_decision: dict[str, Any] = field(default_factory=dict)
    source_execution_id: UUID | None = None
    source_step_id: str | None = None
    supersedes_memory_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    embedding: list[float] | None = None


@dataclass(frozen=True)
class MemoryCandidate:
    scope_type: str
    scope_id: str
    memory_type: str
    content: str
    memory_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    importance: float = 0.5
    explicit: bool = False
    source_execution_id: UUID | None = None
    source_step_id: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class MemoryPolicyDecision:
    allowed: bool
    action: str
    reasons: list[str] = field(default_factory=list)
    normalized_scope_type: str | None = None
    normalized_memory_type: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reasons": self.reasons,
            "normalizedScopeType": self.normalized_scope_type,
            "normalizedMemoryType": self.normalized_memory_type,
        }
