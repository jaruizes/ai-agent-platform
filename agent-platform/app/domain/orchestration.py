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
    requires_approval: bool = False
    approval_reason: str | None = None
    timeout_seconds: float = 120.0
    retry_policy: dict[str, Any] = field(
        default_factory=lambda: {
            "maxAttempts": 3,
            "initialBackoffSeconds": 1.0,
            "maxBackoffSeconds": 30.0,
            "multiplier": 2.0,
        }
    )

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
            "requiresApproval": self.requires_approval,
            "approvalReason": self.approval_reason,
            "timeoutSeconds": self.timeout_seconds,
            "retryPolicy": self.retry_policy,
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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LogicalPlan":
        return cls(
            objective=str(payload.get("objective") or "Fulfil the requested intent"),
            steps=[
                PlanStep(
                    id=str(item["id"]),
                    type=str(item["type"]).upper(),
                    description=str(item.get("description") or "Execute planned step"),
                    depends_on=[str(v) for v in (item.get("dependsOn") or [])],
                    agent_name=item.get("agent"),
                    tool_name=item.get("tool"),
                    tool_arguments=item.get("toolArguments") or {},
                    knowledge_base_names=[
                        str(v) for v in (item.get("knowledgeBases") or [])
                    ],
                    knowledge_usage_mode=str(
                        item.get("knowledgeUsageMode") or "REFERENCE"
                    ).upper(),
                    instructions=[
                        str(v) for v in (item.get("instructions") or [])
                    ],
                    requires_approval=bool(item.get("requiresApproval", False)),
                    approval_reason=item.get("approvalReason"),
                    timeout_seconds=float(item.get("timeoutSeconds") or 120.0),
                    retry_policy=item.get("retryPolicy") or {
                        "maxAttempts": 3,
                        "initialBackoffSeconds": 1.0,
                        "maxBackoffSeconds": 30.0,
                        "multiplier": 2.0,
                    },
                )
                for item in (payload.get("steps") or [])
            ],
            final_step_id=str(payload.get("finalStepId") or ""),
        )


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



class OrchestrationSuspended(RuntimeError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


class OrchestrationCancelled(RuntimeError):
    pass
