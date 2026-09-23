from __future__ import annotations

from typing import Any

from app.business.governance_runtime import get_governance_context
from app.domain.execution import ExecutionPlan
from app.domain.governance import GovernanceBudgetExceeded


class GovernedModelGateway:
    """Budget-governed wrapper around the real model gateway."""

    def __init__(
        self,
        delegate,
        governance_service,
        *,
        default_projected_completion_tokens: int,
    ):
        self._delegate=delegate
        self._governance=governance_service
        self._default_projected_completion_tokens=default_projected_completion_tokens

    async def complete(
        self,*,system_prompt:str,user_prompt:str,model_profile:str,
        temperature:float=0.2,
    )->str:
        detail=await self.complete_detailed(
            system_prompt=system_prompt,user_prompt=user_prompt,
            model_profile=model_profile,temperature=temperature,
        )
        return detail["content"]

    async def complete_detailed(
        self,*,system_prompt:str,user_prompt:str,model_profile:str,
        temperature:float=0.2,
    )->dict[str,Any]:
        ctx=get_governance_context()
        effective_profile=model_profile
        budget_detail=None
        if ctx:
            projected_prompt=max(1,(len(system_prompt)+len(user_prompt))//4)
            evaluation=await self._governance.evaluate_budget(
                execution_id=ctx.execution_id,
                model_profile=model_profile,
                projected_prompt_tokens=projected_prompt,
                projected_completion_tokens=self._default_projected_completion_tokens,
            )
            budget_detail={
                "action":evaluation.action,
                "budget":evaluation.budget_name,
                "reason":evaluation.reason,
                "requestedModelProfile":model_profile,
                "effectiveModelProfile":evaluation.model_profile,
                "current":evaluation.current,
                "projected":evaluation.projected,
            }
            if not evaluation.allowed:
                raise GovernanceBudgetExceeded(
                    evaluation.reason or "Governance budget exceeded"
                )
            effective_profile=evaluation.model_profile

        detail=await self._delegate.complete_detailed(
            system_prompt=system_prompt,user_prompt=user_prompt,
            model_profile=effective_profile,temperature=temperature,
        )
        if ctx:
            cost=await self._governance.record_usage(
                execution_id=ctx.execution_id,step_id=ctx.step_id,
                model_profile=effective_profile,usage=detail.get("usage") or {},
            )
            detail["governance"]={
                "budget":budget_detail,
                "estimatedCostUsd":cost,
            }
            detail["requestedModelProfile"]=model_profile
            detail["modelProfile"]=effective_profile
        return detail

    async def execute(self, plan: ExecutionPlan)->dict[str,Any]:
        detail=await self.complete_detailed(
            system_prompt=plan.system_prompt,user_prompt=plan.user_prompt,
            model_profile=plan.model_profile,temperature=0.2,
        )
        return {
            "type":"agent-response" if plan.strategy.startswith("AGENT") else "direct-llm-response",
            "summary":detail["content"],
            "data":{
                "model":detail.get("model"),
                "modelProfile":detail.get("modelProfile"),
                "requestedModelProfile":detail.get("requestedModelProfile"),
                "usage":detail.get("usage") or {},
                "governance":detail.get("governance"),
            },
            "artifacts":[],
        }

    async def close(self)->None:
        await self._delegate.close()
