from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.domain.orchestration import LogicalPlan, PlanStep
from app.domain.tool import Tool


class PlanPolicyEnricher:
    """Applies deterministic platform policy to an LLM-proposed LogicalPlan."""

    def apply(
        self,
        plan: LogicalPlan,
        *,
        tools: list[Tool],
        execution_policy: dict[str, Any] | None = None,
    ) -> LogicalPlan:
        tools_by_name = {tool.name: tool for tool in tools}
        policy = execution_policy or {}
        max_step_attempts = self._positive_int(policy.get("maxStepAttempts"))
        step_timeout_seconds = self._positive_float(
            policy.get("stepTimeoutSeconds")
        )
        enriched_steps: list[PlanStep] = []

        for original in plan.steps:
            step = original
            if max_step_attempts is not None:
                retry_policy = dict(step.retry_policy or {})
                retry_policy["maxAttempts"] = max_step_attempts
                step = replace(step, retry_policy=retry_policy)
            if step_timeout_seconds is not None:
                step = replace(step, timeout_seconds=step_timeout_seconds)

            if step.type != "TOOL" or not step.tool_name:
                enriched_steps.append(
                    replace(
                        step,
                        approval_source=(
                            "PLANNER" if step.requires_approval else None
                        ),
                    )
                )
                continue

            tool = tools_by_name.get(step.tool_name)
            if tool is None:
                enriched_steps.append(step)
                continue

            policy_name = tool.approval_policy.upper()
            planner_requested = step.requires_approval

            if policy_name == "REQUIRED":
                enriched_steps.append(
                    replace(
                        step,
                        requires_approval=True,
                        approval_reason=(
                            step.approval_reason
                            or f"Tool '{tool.name}' requires human approval "
                            f"by deterministic platform policy."
                        ),
                        approval_source="TOOL_POLICY",
                        tool_side_effect=tool.side_effect,
                        tool_approval_policy=tool.approval_policy,
                    )
                )
                continue

            if policy_name == "NEVER":
                enriched_steps.append(
                    replace(
                        step,
                        requires_approval=False,
                        approval_reason=None,
                        approval_source="TOOL_POLICY",
                        tool_side_effect=tool.side_effect,
                        tool_approval_policy=tool.approval_policy,
                    )
                )
                continue

            enriched_steps.append(
                replace(
                    step,
                    approval_source=(
                        "PLANNER" if planner_requested else "TOOL_POLICY"
                    ),
                    tool_side_effect=tool.side_effect,
                    tool_approval_policy=tool.approval_policy,
                )
            )

        return LogicalPlan(
            objective=plan.objective,
            steps=enriched_steps,
            final_step_id=plan.final_step_id,
        )

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        if value is None:
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None

    @staticmethod
    def _positive_float(value: Any) -> float | None:
        if value is None:
            return None
        parsed = float(value)
        return parsed if parsed > 0 else None
