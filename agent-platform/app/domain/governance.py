from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


POLICY_EFFECTS = {"ALLOW", "DENY", "REQUIRE_APPROVAL"}
POLICY_TYPES = {
    "RESOURCE_ACCESS",
    "SIDE_EFFECT",
    "MODEL_ACCESS",
    "KNOWLEDGE_ACCESS",
    "MEMORY_ACCESS",
}
RESOURCE_TYPES = {
    "TOOL",
    "AGENT",
    "KNOWLEDGE",
    "MODEL",
    "MEMORY_SCOPE",
    "EXECUTION",
}
SUBJECT_TYPES = {"GLOBAL", "TENANT", "TEAM", "USER", "AGENT"}
BUDGET_PERIODS = {"EXECUTION", "DAILY", "MONTHLY"}
BUDGET_ACTIONS = {"DENY", "DEGRADE"}


@dataclass(frozen=True)
class GovernancePolicy:
    name: str
    policy_type: str
    effect: str
    resource_type: str
    resource_pattern: str = "*"
    subject_type: str = "GLOBAL"
    subject_pattern: str = "*"
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    enabled: bool = True
    description: str = ""
    source: str = "API"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class GovernanceDecision:
    effect: str
    reason: str
    resource_type: str
    resource_name: str
    subject_type: str
    subject_id: str
    policy_type: str
    policy_id: UUID | None = None
    policy_name: str | None = None
    execution_id: UUID | None = None
    step_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None


@dataclass(frozen=True)
class GovernanceBudget:
    name: str
    scope_type: str
    scope_id: str
    period: str = "EXECUTION"
    max_prompt_tokens: int | None = None
    max_completion_tokens: int | None = None
    max_total_tokens: int | None = None
    max_cost_usd: float | None = None
    action: str = "DENY"
    degrade_model_profile: str | None = None
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class BudgetEvaluation:
    allowed: bool
    action: str
    model_profile: str
    reason: str | None
    budget_name: str | None
    current: dict[str, float]
    projected: dict[str, float]


class GovernanceDenied(RuntimeError):
    pass


class GovernanceBudgetExceeded(RuntimeError):
    pass
