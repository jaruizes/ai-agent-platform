from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


StepType = Literal["AGENT", "TOOL", "KNOWLEDGE", "MODEL", "VALIDATE"]


@dataclass(frozen=True)
class PlanStep:
    id: str
    type: StepType
    description: str
    depends_on: list[str] = field(default_factory=list)
    agent_name: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    knowledge_base_names: list[str] = field(default_factory=list)
    knowledge_usage_mode: str = "REFERENCE"
    instructions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "dependsOn": self.depends_on,
            "agent": self.agent_name,
            "tool": self.tool_name,
            "toolArguments": self.tool_arguments,
            "knowledgeBases": self.knowledge_base_names,
            "knowledgeUsageMode": self.knowledge_usage_mode,
            "instructions": self.instructions,
        }


@dataclass(frozen=True)
class LogicalPlan:
    objective: str
    steps: list[PlanStep]
    final_step_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "steps": [step.as_dict() for step in self.steps],
            "finalStepId": self.final_step_id,
        }


@dataclass(frozen=True)
class PlanValidation:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }
