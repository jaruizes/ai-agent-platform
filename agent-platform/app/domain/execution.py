from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID


@dataclass(frozen=True)
class Command:
    intent: str
    name: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    instructions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionSubmission:
    execution_id: UUID
    message_id: str
    correlation_id: str
    source: dict[str, Any]
    command: Command


@dataclass(frozen=True)
class ExecutionPlan:
    system_prompt: str
    user_prompt: str
    strategy: Literal["DIRECT_LLM", "AGENT"] = "DIRECT_LLM"
    agent_name: str | None = None
