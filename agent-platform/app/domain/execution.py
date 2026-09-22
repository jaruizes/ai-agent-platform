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
    session_id: UUID | None = None


@dataclass(frozen=True)
class ExecutionPlan:
    system_prompt: str
    user_prompt: str
    strategy: Literal[
        "DIRECT_LLM",
        "AGENT",
        "TOOL",
        "TOOL_LLM",
        "AGENT_TOOL_LLM",
        "RAG_LLM",
        "AGENT_RAG_LLM",
        "AGENT_TOOL_RAG_LLM",
    ] = "DIRECT_LLM"
    agent_name: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    knowledge_base_names: list[str] = field(default_factory=list)
    knowledge_usage_mode: str = "REFERENCE"
    model_profile: str = "reasoning-default"
