from __future__ import annotations

from dataclasses import replace
from fnmatch import fnmatchcase
from typing import Any
from uuid import UUID

from app.domain.governance import (
    BUDGET_ACTIONS,
    BUDGET_PERIODS,
    POLICY_EFFECTS,
    POLICY_TYPES,
    RESOURCE_TYPES,
    SUBJECT_TYPES,
    BudgetEvaluation,
    GovernanceBudget,
    GovernanceDecision,
    GovernanceDenied,
    GovernancePolicy,
)
from app.domain.orchestration import LogicalPlan


class GovernanceService:
    def __init__(
        self,
        repository,
        *,
        pricing: dict[str, tuple[float, float]],
    ):
        self._repository = repository
        self._pricing = pricing

    async def list_policies(self, *, enabled_only: bool = False):
        return await self._repository.list_policies(enabled_only=enabled_only)

    async def save_policy(self, policy: GovernancePolicy):
        self._validate_policy(policy)
        return await self._repository.save_policy(policy)

    async def update_policy(
        self,
        policy_id: UUID,
        policy: GovernancePolicy,
    ):
        self._validate_policy(policy)
        return await self._repository.update_policy(policy_id, policy)

    async def delete_policy(self, policy_id: UUID):
        return await self._repository.delete_policy(policy_id)

    async def list_budgets(self, *, enabled_only: bool = False):
        return await self._repository.list_budgets(enabled_only=enabled_only)

    async def save_budget(self, budget: GovernanceBudget):
        self._validate_budget(budget)
        return await self._repository.save_budget(budget)

    async def update_budget(
        self,
        budget_id: UUID,
        budget: GovernanceBudget,
    ):
        self._validate_budget(budget)
        return await self._repository.update_budget(budget_id, budget)

    async def delete_budget(self, budget_id: UUID):
        return await self._repository.delete_budget(budget_id)

    async def list_decisions(
        self,
        *,
        execution_id: UUID | None = None,
        limit: int = 200,
    ):
        return await self._repository.list_decisions(
            execution_id=execution_id,
            limit=limit,
        )

    async def usage_summary(self, execution_id: UUID):
        return await self._repository.usage_summary(execution_id)

    async def list_budget_decisions(
        self,
        *,
        execution_id: UUID | None = None,
        limit: int = 200,
    ):
        return await self._repository.list_budget_decisions(
            execution_id=execution_id,
            limit=limit,
        )

    async def evaluate(
        self,
        *,
        execution_id: UUID,
        step_id: str | None,
        policy_type: str,
        resource_type: str,
        resource_name: str,
        context: dict[str, Any] | None = None,
        extra_subjects: list[tuple[str, str]] | None = None,
        record: bool = True,
    ) -> GovernanceDecision:
        policies = await self._repository.list_policies(enabled_only=True)
        subjects = await self._repository.execution_subjects(execution_id)
        subjects.extend(extra_subjects or [])
        subjects = list(dict.fromkeys(subjects))
        ctx = context or {}

        matches: list[GovernancePolicy] = []
        for policy in policies:
            if policy.policy_type not in {policy_type, "RESOURCE_ACCESS"}:
                continue
            if policy.resource_type != resource_type:
                continue
            if not fnmatchcase(resource_name, policy.resource_pattern):
                continue
            if not self._subject_matches(policy, subjects):
                continue
            if not self._conditions_match(policy.conditions, ctx):
                continue
            matches.append(policy)

        if not matches:
            decision = GovernanceDecision(
                execution_id=execution_id,
                step_id=step_id,
                policy_type=policy_type,
                effect="ALLOW",
                resource_type=resource_type,
                resource_name=resource_name,
                subject_type="GLOBAL",
                subject_id="*",
                reason=(
                    "No matching governance policy; "
                    "backward-compatible default ALLOW."
                ),
                context=ctx,
            )
        else:
            precedence = {"DENY": 3, "REQUIRE_APPROVAL": 2, "ALLOW": 1}
            matches.sort(
                key=lambda policy: (
                    policy.priority,
                    precedence[policy.effect],
                ),
                reverse=True,
            )
            policy = matches[0]
            subject = self._matched_subject(policy, subjects)
            decision = GovernanceDecision(
                execution_id=execution_id,
                step_id=step_id,
                policy_id=policy.id,
                policy_name=policy.name,
                policy_type=policy.policy_type,
                effect=policy.effect,
                resource_type=resource_type,
                resource_name=resource_name,
                subject_type=subject[0],
                subject_id=subject[1],
                reason=f"Matched policy '{policy.name}' ({policy.effect}).",
                context=ctx,
            )

        if record and matches:
            await self._repository.record_decision(decision)
        return decision

    async def apply_plan(
        self,
        execution: dict[str, Any],
        plan: LogicalPlan,
        *,
        execution_model_profile: str,
    ) -> LogicalPlan:
        enriched_steps = []
        for step in plan.steps:
            decisions: list[GovernanceDecision] = []
            agent_subjects = (
                [("AGENT", step.agent_name)]
                if step.agent_name
                else []
            )

            if step.agent_name:
                decisions.append(
                    await self.evaluate(
                        execution_id=execution["id"],
                        step_id=step.id,
                        policy_type="RESOURCE_ACCESS",
                        resource_type="AGENT",
                        resource_name=step.agent_name,
                        context={"stepType": step.type, "phase": "PLAN"},
                        extra_subjects=agent_subjects,
                    )
                )

            if step.tool_name:
                decisions.append(
                    await self.evaluate(
                        execution_id=execution["id"],
                        step_id=step.id,
                        policy_type="SIDE_EFFECT",
                        resource_type="TOOL",
                        resource_name=step.tool_name,
                        context={
                            "stepType": step.type,
                            "sideEffect": step.tool_side_effect,
                            "phase": "PLAN",
                        },
                        extra_subjects=agent_subjects,
                    )
                )

            if step.type in {"AGENT", "MODEL", "VALIDATE"}:
                decisions.append(
                    await self.evaluate(
                        execution_id=execution["id"],
                        step_id=step.id,
                        policy_type="MODEL_ACCESS",
                        resource_type="MODEL",
                        resource_name=execution_model_profile,
                        context={"stepType": step.type, "phase": "PLAN"},
                        extra_subjects=agent_subjects,
                    )
                )

            for kb_name in step.knowledge_base_names:
                decisions.append(
                    await self.evaluate(
                        execution_id=execution["id"],
                        step_id=step.id,
                        policy_type="KNOWLEDGE_ACCESS",
                        resource_type="KNOWLEDGE",
                        resource_name=kb_name,
                        context={
                            "usageMode": step.knowledge_usage_mode,
                            "stepType": step.type,
                            "phase": "PLAN",
                        },
                        extra_subjects=agent_subjects,
                    )
                )

            denied = [decision for decision in decisions if decision.effect == "DENY"]
            if denied:
                raise GovernanceDenied(denied[0].reason)

            approvals = [
                decision
                for decision in decisions
                if decision.effect == "REQUIRE_APPROVAL"
            ]
            if approvals:
                enriched_steps.append(
                    replace(
                        step,
                        requires_approval=True,
                        approval_reason="; ".join(
                            decision.reason for decision in approvals
                        ),
                        approval_source="GOVERNANCE_POLICY",
                    )
                )
            else:
                enriched_steps.append(step)

        return LogicalPlan(
            objective=plan.objective,
            steps=enriched_steps,
            final_step_id=plan.final_step_id,
        )

    async def enforce_step(
        self,
        execution: dict[str, Any],
        step,
        *,
        execution_model_profile: str,
    ) -> GovernanceDecision | None:
        resources: list[
            tuple[str, str, str, dict[str, Any]]
        ] = []

        if step.agent_name:
            resources.append(
                (
                    "RESOURCE_ACCESS",
                    "AGENT",
                    step.agent_name,
                    {"stepType": step.type, "phase": "RUNTIME"},
                )
            )
        if step.tool_name:
            resources.append(
                (
                    "SIDE_EFFECT",
                    "TOOL",
                    step.tool_name,
                    {
                        "stepType": step.type,
                        "sideEffect": step.tool_side_effect,
                        "phase": "RUNTIME",
                    },
                )
            )
        if step.type in {"AGENT", "MODEL", "VALIDATE"}:
            resources.append(
                (
                    "MODEL_ACCESS",
                    "MODEL",
                    execution_model_profile,
                    {"stepType": step.type, "phase": "RUNTIME"},
                )
            )
        for kb_name in step.knowledge_base_names:
            resources.append(
                (
                    "KNOWLEDGE_ACCESS",
                    "KNOWLEDGE",
                    kb_name,
                    {
                        "usageMode": step.knowledge_usage_mode,
                        "stepType": step.type,
                        "phase": "RUNTIME",
                    },
                )
            )

        approval: GovernanceDecision | None = None
        extra_subjects = (
            [("AGENT", step.agent_name)]
            if step.agent_name
            else []
        )
        for policy_type, resource_type, resource_name, context in resources:
            decision = await self.evaluate(
                execution_id=execution["id"],
                step_id=step.id,
                policy_type=policy_type,
                resource_type=resource_type,
                resource_name=resource_name,
                context=context,
                extra_subjects=extra_subjects,
            )
            if decision.effect == "DENY":
                raise GovernanceDenied(decision.reason)
            if decision.effect == "REQUIRE_APPROVAL":
                approval = decision

        return approval

    async def filter_memory_scopes(
        self,
        *,
        execution_id: UUID,
        step_id: str,
        scopes: list[tuple[str, str]],
        extra_subjects: list[tuple[str, str]] | None = None,
    ) -> list[tuple[str, str]]:
        allowed: list[tuple[str, str]] = []
        for scope_type, scope_id in scopes:
            decision = await self.evaluate(
                execution_id=execution_id,
                step_id=step_id,
                policy_type="MEMORY_ACCESS",
                resource_type="MEMORY_SCOPE",
                resource_name=f"{scope_type}:{scope_id}",
                context={
                    "scopeType": scope_type,
                    "scopeId": scope_id,
                    "phase": "CONTEXT_ENGINE",
                },
                extra_subjects=extra_subjects,
            )
            if decision.effect == "REQUIRE_APPROVAL":
                raise GovernanceDenied(
                    "Memory scope access requires approval, but memory retrieval "
                    "has no independent approval gate. Apply approval to the "
                    "enclosing AGENT/MODEL step instead."
                )
            if decision.effect != "DENY":
                allowed.append((scope_type, scope_id))
        return allowed

    async def evaluate_budget(
        self,
        *,
        execution_id: UUID,
        step_id: str | None,
        model_profile: str,
        projected_prompt_tokens: int,
        projected_completion_tokens: int,
        extra_subjects: list[tuple[str, str]] | None = None,
        record: bool = True,
    ) -> BudgetEvaluation:
        budgets = await self._repository.list_budgets(enabled_only=True)
        subjects = await self._repository.execution_subjects(execution_id)
        subjects.extend(extra_subjects or [])
        subjects = list(dict.fromkeys(subjects))

        applicable = [
            budget
            for budget in budgets
            if (budget.scope_type, budget.scope_id) in subjects
            or (
                budget.scope_type == "GLOBAL"
                and budget.scope_id == "*"
            )
        ]
        if not applicable:
            return BudgetEvaluation(
                allowed=True,
                action="ALLOW",
                model_profile=model_profile,
                reason=None,
                budget_name=None,
                current={},
                projected={},
            )

        effective_profile = model_profile
        applied_budget_names = [budget.name for budget in applicable]
        # Hard DENY constraints are evaluated before optional cost degradation.
        applicable.sort(
            key=lambda budget: (
                0 if budget.action == "DENY" else 1,
                budget.name,
            )
        )

        for budget in applicable:
            current = await self._repository.aggregate_usage(
                scope_type=budget.scope_type,
                scope_id=budget.scope_id,
                period=budget.period,
                execution_id=execution_id,
            )
            rates = self._pricing.get(effective_profile, (0.0, 0.0))

            if (
                budget.max_cost_usd is not None
                and not any(rate > 0 for rate in rates)
            ):
                evaluation = BudgetEvaluation(
                    allowed=False,
                    action="DENY",
                    model_profile=effective_profile,
                    reason=(
                        f"Budget '{budget.name}' cannot evaluate cost because "
                        f"pricing is not configured for '{effective_profile}'."
                    ),
                    budget_name=budget.name,
                    current=current,
                    projected={},
                )
                if record:
                    await self._repository.record_budget_decision(
                        execution_id=execution_id,
                        step_id=step_id,
                        budget_id=budget.id,
                        budget_name=budget.name,
                        action=evaluation.action,
                        allowed=False,
                        requested_model_profile=model_profile,
                        effective_model_profile=effective_profile,
                        reason=evaluation.reason,
                        current=current,
                        projected={},
                    )
                return evaluation

            projected = self._project_usage(
                current=current,
                prompt_tokens=projected_prompt_tokens,
                completion_tokens=projected_completion_tokens,
                input_rate=rates[0],
                output_rate=rates[1],
            )
            exceeded = self._exceeded_dimensions(budget, projected)

            if not exceeded:
                if record:
                    await self._repository.record_budget_decision(
                        execution_id=execution_id,
                        step_id=step_id,
                        budget_id=budget.id,
                        budget_name=budget.name,
                        action="ALLOW",
                        allowed=True,
                        requested_model_profile=model_profile,
                        effective_model_profile=effective_profile,
                        reason=f"Budget '{budget.name}' remains within limits.",
                        current=current,
                        projected=projected,
                    )
                continue

            if budget.action == "DEGRADE":
                target = budget.degrade_model_profile
                target_rates = self._pricing.get(target or "", (0.0, 0.0))
                degraded_projected = self._project_usage(
                    current=current,
                    prompt_tokens=projected_prompt_tokens,
                    completion_tokens=projected_completion_tokens,
                    input_rate=target_rates[0],
                    output_rate=target_rates[1],
                )
                if (
                    target
                    and not self._exceeded_dimensions(
                        budget,
                        degraded_projected,
                    )
                ):
                    effective_profile = target
                    if record:
                        await self._repository.record_budget_decision(
                            execution_id=execution_id,
                            step_id=step_id,
                            budget_id=budget.id,
                            budget_name=budget.name,
                            action="DEGRADE",
                            allowed=True,
                            requested_model_profile=model_profile,
                            effective_model_profile=effective_profile,
                            reason=(
                                f"Budget '{budget.name}' projected cost limit "
                                "exceeded; degrading model profile to "
                                f"'{effective_profile}'."
                            ),
                            current=current,
                            projected=degraded_projected,
                        )
                    continue

            evaluation = BudgetEvaluation(
                allowed=False,
                action="DENY",
                model_profile=effective_profile,
                reason=(
                    f"Budget '{budget.name}' projected limit exceeded: "
                    + ", ".join(sorted(exceeded))
                ),
                budget_name=budget.name,
                current=current,
                projected=projected,
            )
            if record:
                await self._repository.record_budget_decision(
                    execution_id=execution_id,
                    step_id=step_id,
                    budget_id=budget.id,
                    budget_name=budget.name,
                    action=evaluation.action,
                    allowed=False,
                    requested_model_profile=model_profile,
                    effective_model_profile=effective_profile,
                    reason=evaluation.reason,
                    current=current,
                    projected=projected,
                )
            return evaluation

        return BudgetEvaluation(
            allowed=True,
            action=(
                "DEGRADE"
                if effective_profile != model_profile
                else "ALLOW"
            ),
            model_profile=effective_profile,
            reason=(
                f"Budget policy selected degraded model '{effective_profile}'."
                if effective_profile != model_profile
                else None
            ),
            budget_name=",".join(applied_budget_names),
            current={},
            projected={},
        )

    async def record_usage(
        self,
        *,
        execution_id: UUID | None,
        step_id: str | None,
        model_profile: str,
        usage: dict[str, Any],
        extra_scopes: list[tuple[str, str]] | None = None,
    ) -> float:
        prompt_tokens = int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or 0
        )
        completion_tokens = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or 0
        )
        total_tokens = int(
            usage.get("total_tokens")
            or prompt_tokens + completion_tokens
        )

        input_rate, output_rate = self._pricing.get(
            model_profile,
            (0.0, 0.0),
        )
        cost = (
            prompt_tokens / 1_000_000
        ) * input_rate + (
            completion_tokens / 1_000_000
        ) * output_rate

        if execution_id:
            scopes = await self._repository.execution_subjects(
                execution_id
            )
            scopes.extend(extra_scopes or [])
            scopes = list(dict.fromkeys(scopes))
            await self._repository.record_usage(
                execution_id=execution_id,
                step_id=step_id,
                scopes=scopes,
                model_profile=model_profile,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
            )
        return cost

    @staticmethod
    def _project_usage(
        *,
        current: dict[str, float],
        prompt_tokens: int,
        completion_tokens: int,
        input_rate: float,
        output_rate: float,
    ) -> dict[str, float]:
        incremental_cost = (
            prompt_tokens / 1_000_000
        ) * input_rate + (
            completion_tokens / 1_000_000
        ) * output_rate
        return {
            "prompt_tokens": current["prompt_tokens"] + prompt_tokens,
            "completion_tokens": (
                current["completion_tokens"] + completion_tokens
            ),
            "total_tokens": (
                current["total_tokens"] + prompt_tokens + completion_tokens
            ),
            "estimated_cost_usd": (
                current["estimated_cost_usd"] + incremental_cost
            ),
        }

    @staticmethod
    def _exceeded_dimensions(
        budget: GovernanceBudget,
        projected: dict[str, float],
    ) -> set[str]:
        checks = (
            (budget.max_prompt_tokens, "prompt_tokens"),
            (budget.max_completion_tokens, "completion_tokens"),
            (budget.max_total_tokens, "total_tokens"),
            (budget.max_cost_usd, "estimated_cost_usd"),
        )
        return {
            key
            for limit, key in checks
            if limit is not None and projected[key] > limit
        }

    @staticmethod
    def _conditions_match(
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        return all(
            context.get(key) == value
            for key, value in conditions.items()
        )

    @staticmethod
    def _subject_matches(
        policy: GovernancePolicy,
        subjects: list[tuple[str, str]],
    ) -> bool:
        if policy.subject_type == "GLOBAL":
            return True
        return any(
            subject_type == policy.subject_type
            and fnmatchcase(subject_id, policy.subject_pattern)
            for subject_type, subject_id in subjects
        )

    @staticmethod
    def _matched_subject(
        policy: GovernancePolicy,
        subjects: list[tuple[str, str]],
    ) -> tuple[str, str]:
        if policy.subject_type == "GLOBAL":
            return ("GLOBAL", "*")
        for subject in subjects:
            if (
                subject[0] == policy.subject_type
                and fnmatchcase(subject[1], policy.subject_pattern)
            ):
                return subject
        return ("GLOBAL", "*")

    @staticmethod
    def _validate_policy(policy: GovernancePolicy) -> None:
        if policy.policy_type not in POLICY_TYPES:
            raise ValueError("Invalid policyType")
        if policy.effect not in POLICY_EFFECTS:
            raise ValueError("Invalid effect")
        if policy.resource_type not in RESOURCE_TYPES:
            raise ValueError("Invalid resourceType")
        if policy.subject_type not in SUBJECT_TYPES:
            raise ValueError("Invalid subjectType")

    def _validate_budget(self, budget: GovernanceBudget) -> None:
        if budget.period not in BUDGET_PERIODS:
            raise ValueError("Invalid budget period")
        if budget.action not in BUDGET_ACTIONS:
            raise ValueError("Invalid budget action")
        if budget.scope_type not in SUBJECT_TYPES | {"EXECUTION"}:
            raise ValueError("Invalid budget scopeType")
        if budget.action == "DEGRADE" and not budget.degrade_model_profile:
            raise ValueError(
                "DEGRADE budget requires degradeModelProfile"
            )
        if budget.action == "DEGRADE" and any(
            value is not None
            for value in (
                budget.max_prompt_tokens,
                budget.max_completion_tokens,
                budget.max_total_tokens,
            )
        ):
            raise ValueError(
                "DEGRADE is supported only for cost-only budgets; "
                "token budgets must use DENY"
            )
        if budget.action == "DEGRADE" and budget.degrade_model_profile:
            degrade_rates = self._pricing.get(
                budget.degrade_model_profile,
                (0.0, 0.0),
            )
            if not any(rate > 0 for rate in degrade_rates):
                raise ValueError(
                    "DEGRADE budget requires configured pricing for "
                    f"'{budget.degrade_model_profile}'"
                )
        if budget.max_cost_usd is not None and not any(
            input_rate > 0 or output_rate > 0
            for input_rate, output_rate in self._pricing.values()
        ):
            raise ValueError(
                "Cost budgets require configured model pricing"
            )
        limits = [
            budget.max_prompt_tokens,
            budget.max_completion_tokens,
            budget.max_total_tokens,
            budget.max_cost_usd,
        ]
        if not any(value is not None for value in limits):
            raise ValueError("Budget requires at least one limit")
