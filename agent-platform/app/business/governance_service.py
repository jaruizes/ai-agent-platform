from __future__ import annotations

from dataclasses import replace
from fnmatch import fnmatchcase
from typing import Any
from uuid import UUID

from app.domain.governance import (
    BUDGET_ACTIONS, BUDGET_PERIODS, POLICY_EFFECTS, POLICY_TYPES,
    RESOURCE_TYPES, SUBJECT_TYPES, BudgetEvaluation, GovernanceBudget,
    GovernanceDecision, GovernanceDenied, GovernancePolicy,
)
from app.domain.orchestration import LogicalPlan


class GovernanceService:
    def __init__(self, repository, *, pricing: dict[str,tuple[float,float]]):
        self._repository=repository
        self._pricing=pricing

    async def list_policies(self, *, enabled_only: bool=False):
        return await self._repository.list_policies(enabled_only=enabled_only)

    async def save_policy(self, policy: GovernancePolicy):
        self._validate_policy(policy)
        return await self._repository.save_policy(policy)

    async def delete_policy(self, policy_id: UUID):
        return await self._repository.delete_policy(policy_id)

    async def list_budgets(self, *, enabled_only: bool=False):
        return await self._repository.list_budgets(enabled_only=enabled_only)

    async def save_budget(self, budget: GovernanceBudget):
        self._validate_budget(budget)
        return await self._repository.save_budget(budget)

    async def delete_budget(self, budget_id: UUID):
        return await self._repository.delete_budget(budget_id)

    async def list_decisions(self, *, execution_id: UUID|None=None, limit:int=200):
        return await self._repository.list_decisions(execution_id=execution_id,limit=limit)

    async def usage_summary(self, execution_id: UUID):
        return await self._repository.usage_summary(execution_id)

    async def evaluate(
        self,
        *,
        execution_id: UUID,
        step_id: str|None,
        policy_type: str,
        resource_type: str,
        resource_name: str,
        context: dict[str,Any]|None=None,
        extra_subjects: list[tuple[str,str]]|None=None,
        record: bool=True,
    ) -> GovernanceDecision:
        policies=await self._repository.list_policies(enabled_only=True)
        subjects=await self._repository.execution_subjects(execution_id)
        subjects.extend(extra_subjects or [])
        subjects=list(dict.fromkeys(subjects))
        ctx=context or {}
        matches=[]
        for policy in policies:
            if policy.policy_type not in {policy_type,"RESOURCE_ACCESS"}:
                continue
            if policy.resource_type != resource_type:
                continue
            if not fnmatchcase(resource_name,policy.resource_pattern):
                continue
            if not self._subject_matches(policy,subjects):
                continue
            if not self._conditions_match(policy.conditions,ctx):
                continue
            matches.append(policy)

        if not matches:
            decision=GovernanceDecision(
                execution_id=execution_id,step_id=step_id,
                policy_type=policy_type,effect="ALLOW",
                resource_type=resource_type,resource_name=resource_name,
                subject_type="GLOBAL",subject_id="*",
                reason="No matching governance policy; backward-compatible default ALLOW.",
                context=ctx,
            )
        else:
            precedence={"DENY":3,"REQUIRE_APPROVAL":2,"ALLOW":1}
            matches.sort(key=lambda p:(precedence[p.effect],p.priority),reverse=True)
            policy=matches[0]
            subject=self._matched_subject(policy,subjects)
            decision=GovernanceDecision(
                execution_id=execution_id,step_id=step_id,policy_id=policy.id,
                policy_name=policy.name,policy_type=policy.policy_type,
                effect=policy.effect,resource_type=resource_type,
                resource_name=resource_name,subject_type=subject[0],
                subject_id=subject[1],
                reason=f"Matched policy '{policy.name}' ({policy.effect}).",
                context=ctx,
            )
        if record:
            await self._repository.record_decision(decision)
        return decision

    async def apply_plan(self, execution: dict[str,Any], plan: LogicalPlan) -> LogicalPlan:
        steps=[]
        for step in plan.steps:
            decisions=[]
            if step.agent_name:
                decisions.append(await self.evaluate(
                    execution_id=execution["id"],step_id=step.id,
                    policy_type="RESOURCE_ACCESS",resource_type="AGENT",
                    resource_name=step.agent_name,
                    context={"stepType":step.type},
                ))
            if step.tool_name:
                decisions.append(await self.evaluate(
                    execution_id=execution["id"],step_id=step.id,
                    policy_type="SIDE_EFFECT",resource_type="TOOL",
                    resource_name=step.tool_name,
                    context={"stepType":step.type,"sideEffect":step.tool_side_effect},
                ))
            for kb in step.knowledge_base_names:
                decisions.append(await self.evaluate(
                    execution_id=execution["id"],step_id=step.id,
                    policy_type="KNOWLEDGE_ACCESS",resource_type="KNOWLEDGE",
                    resource_name=kb,context={"usageMode":step.knowledge_usage_mode},
                ))
            denied=[d for d in decisions if d.effect=="DENY"]
            if denied:
                raise GovernanceDenied(denied[0].reason)
            approvals=[d for d in decisions if d.effect=="REQUIRE_APPROVAL"]
            if approvals:
                reason="; ".join(d.reason for d in approvals)
                step=replace(
                    step,requires_approval=True,
                    approval_reason=reason,
                    approval_source="GOVERNANCE_POLICY",
                )
            steps.append(step)
        return LogicalPlan(objective=plan.objective,steps=steps,final_step_id=plan.final_step_id)

    async def enforce_step(self, execution:dict[str,Any], step) -> GovernanceDecision|None:
        resources=[]
        if step.agent_name:
            resources.append(("RESOURCE_ACCESS","AGENT",step.agent_name,{}))
        if step.tool_name:
            resources.append(("SIDE_EFFECT","TOOL",step.tool_name,{"sideEffect":step.tool_side_effect}))
        for kb in step.knowledge_base_names:
            resources.append(("KNOWLEDGE_ACCESS","KNOWLEDGE",kb,{"usageMode":step.knowledge_usage_mode}))
        approval=None
        for ptype,rtype,rname,ctx in resources:
            decision=await self.evaluate(
                execution_id=execution["id"],step_id=step.id,
                policy_type=ptype,resource_type=rtype,resource_name=rname,context=ctx,
            )
            if decision.effect=="DENY":
                raise GovernanceDenied(decision.reason)
            if decision.effect=="REQUIRE_APPROVAL":
                approval=decision
        return approval

    async def filter_memory_scopes(
        self,
        *,
        execution_id:UUID,
        step_id:str,
        scopes:list[tuple[str,str]],
    )->list[tuple[str,str]]:
        allowed=[]
        for stype,sid in scopes:
            decision=await self.evaluate(
                execution_id=execution_id,step_id=step_id,
                policy_type="MEMORY_ACCESS",resource_type="MEMORY_SCOPE",
                resource_name=f"{stype}:{sid}",
                context={"scopeType":stype,"scopeId":sid},
            )
            if decision.effect=="DENY":
                continue
            allowed.append((stype,sid))
        return allowed

    async def evaluate_budget(
        self,
        *,
        execution_id:UUID,
        model_profile:str,
        projected_prompt_tokens:int,
        projected_completion_tokens:int,
    )->BudgetEvaluation:
        budgets=await self._repository.list_budgets(enabled_only=True)
        subjects=await self._repository.execution_subjects(execution_id)
        applicable=[
            budget for budget in budgets
            if (budget.scope_type,budget.scope_id) in subjects
            or (budget.scope_type=="GLOBAL" and budget.scope_id=="*")
        ]
        if not applicable:
            return BudgetEvaluation(
                allowed=True,action="ALLOW",model_profile=model_profile,
                reason=None,budget_name=None,current={},projected={},
            )
        in_rate,out_rate=self._pricing.get(model_profile,(0.0,0.0))
        projected_cost=(projected_prompt_tokens/1_000_000)*in_rate + (projected_completion_tokens/1_000_000)*out_rate
        for budget in applicable:
            current=await self._repository.aggregate_usage(
                scope_type=budget.scope_type,scope_id=budget.scope_id,
                period=budget.period,execution_id=execution_id,
            )
            projected={
                "prompt_tokens":current["prompt_tokens"]+projected_prompt_tokens,
                "completion_tokens":current["completion_tokens"]+projected_completion_tokens,
                "total_tokens":current["total_tokens"]+projected_prompt_tokens+projected_completion_tokens,
                "estimated_cost_usd":current["estimated_cost_usd"]+projected_cost,
            }
            exceeded=self._budget_exceeded(budget,projected)
            if not exceeded:
                continue
            if budget.action=="DEGRADE" and budget.degrade_model_profile and budget.degrade_model_profile!=model_profile:
                return BudgetEvaluation(
                    allowed=True,action="DEGRADE",
                    model_profile=budget.degrade_model_profile,
                    reason=f"Budget '{budget.name}' projected limit exceeded; degrading model profile.",
                    budget_name=budget.name,current=current,projected=projected,
                )
            return BudgetEvaluation(
                allowed=False,action="DENY",model_profile=model_profile,
                reason=f"Budget '{budget.name}' projected limit exceeded.",
                budget_name=budget.name,current=current,projected=projected,
            )
        return BudgetEvaluation(
            allowed=True,action="ALLOW",model_profile=model_profile,
            reason=None,budget_name=None,current={},projected={},
        )

    async def record_usage(
        self,*,execution_id:UUID|None,step_id:str|None,model_profile:str,
        usage:dict[str,Any],
    )->float:
        prompt=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total=int(usage.get("total_tokens") or prompt+completion)
        in_rate,out_rate=self._pricing.get(model_profile,(0.0,0.0))
        cost=(prompt/1_000_000)*in_rate+(completion/1_000_000)*out_rate
        if execution_id:
            scopes=await self._repository.execution_subjects(execution_id)
            await self._repository.record_usage(
                execution_id=execution_id,step_id=step_id,scopes=scopes,
                model_profile=model_profile,prompt_tokens=prompt,
                completion_tokens=completion,total_tokens=total,
                estimated_cost_usd=cost,
            )
        return cost

    @staticmethod
    def _budget_exceeded(budget, projected):
        checks=(
            (budget.max_prompt_tokens,"prompt_tokens"),
            (budget.max_completion_tokens,"completion_tokens"),
            (budget.max_total_tokens,"total_tokens"),
            (budget.max_cost_usd,"estimated_cost_usd"),
        )
        return any(limit is not None and projected[key]>limit for limit,key in checks)

    @staticmethod
    def _conditions_match(conditions:dict[str,Any],context:dict[str,Any])->bool:
        return all(context.get(key)==value for key,value in conditions.items())

    @staticmethod
    def _subject_matches(policy,subjects):
        if policy.subject_type=="GLOBAL":
            return True
        return any(
            stype==policy.subject_type and fnmatchcase(sid,policy.subject_pattern)
            for stype,sid in subjects
        )

    @staticmethod
    def _matched_subject(policy,subjects):
        if policy.subject_type=="GLOBAL":
            return ("GLOBAL","*")
        for subject in subjects:
            if subject[0]==policy.subject_type and fnmatchcase(subject[1],policy.subject_pattern):
                return subject
        return ("GLOBAL","*")

    @staticmethod
    def _validate_policy(policy):
        if policy.policy_type not in POLICY_TYPES: raise ValueError("Invalid policyType")
        if policy.effect not in POLICY_EFFECTS: raise ValueError("Invalid effect")
        if policy.resource_type not in RESOURCE_TYPES: raise ValueError("Invalid resourceType")
        if policy.subject_type not in SUBJECT_TYPES: raise ValueError("Invalid subjectType")

    @staticmethod
    def _validate_budget(budget):
        if budget.period not in BUDGET_PERIODS: raise ValueError("Invalid budget period")
        if budget.action not in BUDGET_ACTIONS: raise ValueError("Invalid budget action")
        if budget.scope_type not in SUBJECT_TYPES|{"EXECUTION"}: raise ValueError("Invalid budget scopeType")
        limits=[budget.max_prompt_tokens,budget.max_completion_tokens,budget.max_total_tokens,budget.max_cost_usd]
        if not any(v is not None for v in limits): raise ValueError("Budget requires at least one limit")
