from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.domain.governance import GovernanceBudget, GovernancePolicy
from app.infrastructure.api.rest.governance_schemas import (
    BudgetEvaluateRequest,
    BudgetRequest,
    PolicyEvaluateRequest,
    PolicyRequest,
)


def create_governance_router(service)->APIRouter:
    router=APIRouter(prefix="/v1/governance",tags=["governance"])

    @router.get("/policies")
    async def policies(enabledOnly:bool=False):
        return [_policy(x) for x in await service.list_policies(enabled_only=enabledOnly)]

    @router.post("/policies")
    async def save_policy(request:PolicyRequest):
        try:
            return _policy(await service.save_policy(_policy_domain(request)))
        except ValueError as exc:
            raise HTTPException(status_code=400,detail=str(exc)) from exc

    @router.put("/policies/{policy_id}")
    async def update_policy(policy_id:UUID,request:PolicyRequest):
        try:
            policy=_policy_domain(request)
            policy=GovernancePolicy(**{**policy.__dict__,"id":policy_id})
            return _policy(await service.save_policy(policy))
        except ValueError as exc:
            raise HTTPException(status_code=400,detail=str(exc)) from exc

    @router.delete("/policies/{policy_id}")
    async def delete_policy(policy_id:UUID):
        if not await service.delete_policy(policy_id):
            raise HTTPException(status_code=404,detail="Policy not found")
        return {"deleted":True}

    @router.post("/policies/evaluate")
    async def evaluate_policy(request: PolicyEvaluateRequest):
        try:
            execution_id = UUID(request.executionId)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid executionId") from exc
        decision = await service.evaluate(
            execution_id=execution_id,
            step_id=request.stepId,
            policy_type=request.policyType.upper(),
            resource_type=request.resourceType.upper(),
            resource_name=request.resourceName,
            context=request.context,
            record=False,
        )
        return {
            "effect": decision.effect,
            "reason": decision.reason,
            "policyId": str(decision.policy_id) if decision.policy_id else None,
            "policyName": decision.policy_name,
            "subjectType": decision.subject_type,
            "subjectId": decision.subject_id,
            "resourceType": decision.resource_type,
            "resourceName": decision.resource_name,
        }

    @router.post("/budgets/evaluate")
    async def evaluate_budget(request: BudgetEvaluateRequest):
        try:
            execution_id = UUID(request.executionId)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid executionId") from exc
        evaluation = await service.evaluate_budget(
            execution_id=execution_id,
            step_id=request.stepId,
            model_profile=request.modelProfile,
            projected_prompt_tokens=request.projectedPromptTokens,
            projected_completion_tokens=request.projectedCompletionTokens,
        )
        return {
            "allowed": evaluation.allowed,
            "action": evaluation.action,
            "modelProfile": evaluation.model_profile,
            "budgetName": evaluation.budget_name,
            "reason": evaluation.reason,
            "current": evaluation.current,
            "projected": evaluation.projected,
        }

    @router.get("/decisions")
    async def decisions(
        executionId:UUID|None=None,
        limit:int=Query(default=200,ge=1,le=1000),
    ):
        rows=await service.list_decisions(execution_id=executionId,limit=limit)
        return [_decision(row) for row in rows]

    @router.get("/budgets")
    async def budgets(enabledOnly:bool=False):
        return [_budget(x) for x in await service.list_budgets(enabled_only=enabledOnly)]

    @router.post("/budgets")
    async def save_budget(request:BudgetRequest):
        try:
            return _budget(await service.save_budget(_budget_domain(request)))
        except ValueError as exc:
            raise HTTPException(status_code=400,detail=str(exc)) from exc

    @router.put("/budgets/{budget_id}")
    async def update_budget(budget_id:UUID,request:BudgetRequest):
        try:
            budget=_budget_domain(request)
            budget=GovernanceBudget(**{**budget.__dict__,"id":budget_id})
            return _budget(await service.save_budget(budget))
        except ValueError as exc:
            raise HTTPException(status_code=400,detail=str(exc)) from exc

    @router.delete("/budgets/{budget_id}")
    async def delete_budget(budget_id:UUID):
        if not await service.delete_budget(budget_id):
            raise HTTPException(status_code=404,detail="Budget not found")
        return {"deleted":True}

    @router.get("/budget-decisions")
    async def budget_decisions(
        executionId: UUID | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ):
        rows = await service.list_budget_decisions(
            execution_id=executionId,
            limit=limit,
        )
        return [
            {
                "id": str(row["id"]),
                "executionId": str(row["execution_id"]),
                "stepId": row["step_id"],
                "budgetId": (
                    str(row["budget_id"]) if row["budget_id"] else None
                ),
                "budgetName": row["budget_name"],
                "action": row["action"],
                "allowed": row["allowed"],
                "requestedModelProfile": row["requested_model_profile"],
                "effectiveModelProfile": row["effective_model_profile"],
                "reason": row["reason"],
                "current": row["current_usage"],
                "projected": row["projected_usage"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    @router.get("/executions/{execution_id}/usage")
    async def usage(execution_id:UUID):
        return await service.usage_summary(execution_id)

    return router


def _policy_domain(r:PolicyRequest)->GovernancePolicy:
    return GovernancePolicy(
        name=r.name,description=r.description,
        policy_type=r.policyType.upper(),effect=r.effect.upper(),
        resource_type=r.resourceType.upper(),resource_pattern=r.resourcePattern,
        subject_type=r.subjectType.upper(),subject_pattern=r.subjectPattern,
        conditions=r.conditions,priority=r.priority,enabled=r.enabled,
    )


def _budget_domain(r:BudgetRequest)->GovernanceBudget:
    return GovernanceBudget(
        name=r.name,scope_type=r.scopeType.upper(),scope_id=r.scopeId,
        period=r.period.upper(),max_prompt_tokens=r.maxPromptTokens,
        max_completion_tokens=r.maxCompletionTokens,
        max_total_tokens=r.maxTotalTokens,max_cost_usd=r.maxCostUsd,
        action=r.action.upper(),degrade_model_profile=r.degradeModelProfile,
        enabled=r.enabled,
    )


def _policy(x)->dict[str,Any]:
    return {
        "id":str(x.id),"name":x.name,"description":x.description,
        "policyType":x.policy_type,"effect":x.effect,
        "resourceType":x.resource_type,"resourcePattern":x.resource_pattern,
        "subjectType":x.subject_type,"subjectPattern":x.subject_pattern,
        "conditions":x.conditions,"priority":x.priority,"enabled":x.enabled,
        "source":x.source,"createdAt":x.created_at,"updatedAt":x.updated_at,
    }


def _budget(x)->dict[str,Any]:
    return {
        "id":str(x.id),"name":x.name,"scopeType":x.scope_type,
        "scopeId":x.scope_id,"period":x.period,
        "maxPromptTokens":x.max_prompt_tokens,
        "maxCompletionTokens":x.max_completion_tokens,
        "maxTotalTokens":x.max_total_tokens,"maxCostUsd":x.max_cost_usd,
        "action":x.action,"degradeModelProfile":x.degrade_model_profile,
        "enabled":x.enabled,"createdAt":x.created_at,"updatedAt":x.updated_at,
    }


def _decision(row:dict[str,Any])->dict[str,Any]:
    return {
        "id":str(row["id"]),
        "executionId":str(row["execution_id"]) if row["execution_id"] else None,
        "stepId":row["step_id"],
        "policyId":str(row["policy_id"]) if row["policy_id"] else None,
        "policyName":row["policy_name"],"policyType":row["policy_type"],
        "effect":row["effect"],"resourceType":row["resource_type"],
        "resourceName":row["resource_name"],"subjectType":row["subject_type"],
        "subjectId":row["subject_id"],"reason":row["reason"],
        "context":row["context"],"createdAt":row["created_at"],
    }
