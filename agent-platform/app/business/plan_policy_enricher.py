from __future__ import annotations

from dataclasses import replace

from app.domain.orchestration import LogicalPlan, PlanStep
from app.domain.tool import Tool


class PlanPolicyEnricher:
    """Applies deterministic platform policy to an LLM-proposed LogicalPlan."""

    def apply(
        self,
        plan: LogicalPlan,
        *,
        tools: list[Tool],
    ) -> LogicalPlan:
        tools_by_name = {tool.name: tool for tool in tools}
        enriched_steps: list[PlanStep] = []

        for step in plan.steps:
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

            policy = tool.approval_policy.upper()
            planner_requested = step.requires_approval

            if policy == "REQUIRED":
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

            if policy == "NEVER":
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
