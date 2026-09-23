from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ContextComponent:
    type: str
    content: str
    priority: int
    mandatory: bool = False
    source_ref: str | None = None
    token_estimate: int = 0
    selected: bool = True
    action: str = "INCLUDE"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectiveContext:
    system_prompt: str
    user_prompt: str
    components: list[ContextComponent]
    budget: dict[str, Any]
    provenance: list[dict[str, Any]]
    prompt_token_estimate: int
    selected_token_estimate: int
    dropped_token_estimate: int
    compressed: bool = False


@dataclass(frozen=True)
class ContextSnapshot:
    execution_id: UUID
    step_id: str
    attempt: int
    model_profile: str
    budget: dict[str, Any]
    components: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
    prompt_token_estimate: int
    selected_token_estimate: int
    dropped_token_estimate: int
    compressed: bool
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
