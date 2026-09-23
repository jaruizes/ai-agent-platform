from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GovernanceRuntimeContext:
    execution_id: UUID
    step_id: str | None
    session_scope: str | None
    session_owner_key: str | None
    agent_name: str | None = None


_runtime_context: ContextVar[GovernanceRuntimeContext | None] = ContextVar(
    "governance_runtime_context",
    default=None,
)


def get_governance_context() -> GovernanceRuntimeContext | None:
    return _runtime_context.get()


def set_governance_context(context: GovernanceRuntimeContext):
    return _runtime_context.set(context)


def reset_governance_context(token) -> None:
    _runtime_context.reset(token)
