from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.governance import (
    GovernanceBudget,
    GovernanceDecision,
    GovernancePolicy,
)
from app.infrastructure.persistence.postgres.database import Database


class PostgresGovernanceRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_policies(self, *, enabled_only: bool = False) -> list[GovernancePolicy]:
        async with self._db.require_pool().acquire() as conn:
            if enabled_only:
                rows = await conn.fetch(
                    "SELECT * FROM governance_policies WHERE enabled=true "
                    "ORDER BY priority DESC,name"
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM governance_policies ORDER BY priority DESC,name"
                )
        return [self._policy(row) for row in rows]

    async def save_policy(self, policy: GovernancePolicy) -> GovernancePolicy:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO governance_policies(
                    id,name,description,policy_type,effect,resource_type,
                    resource_pattern,subject_type,subject_pattern,conditions,
                    priority,enabled,source
                ) VALUES(
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12,$13
                )
                ON CONFLICT(name) DO UPDATE SET
                    description=EXCLUDED.description,
                    policy_type=EXCLUDED.policy_type,
                    effect=EXCLUDED.effect,
                    resource_type=EXCLUDED.resource_type,
                    resource_pattern=EXCLUDED.resource_pattern,
                    subject_type=EXCLUDED.subject_type,
                    subject_pattern=EXCLUDED.subject_pattern,
                    conditions=EXCLUDED.conditions,
                    priority=EXCLUDED.priority,
                    enabled=EXCLUDED.enabled,
                    updated_at=now()
                RETURNING *
                """,
                policy.id, policy.name, policy.description, policy.policy_type,
                policy.effect, policy.resource_type, policy.resource_pattern,
                policy.subject_type, policy.subject_pattern,
                json.dumps(policy.conditions), policy.priority,
                policy.enabled, policy.source,
            )
        return self._policy(row)

    async def update_policy(
        self,
        policy_id: UUID,
        policy: GovernancePolicy,
    ) -> GovernancePolicy | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE governance_policies
                SET name=$2,description=$3,policy_type=$4,effect=$5,
                    resource_type=$6,resource_pattern=$7,subject_type=$8,
                    subject_pattern=$9,conditions=$10::jsonb,priority=$11,
                    enabled=$12,updated_at=now()
                WHERE id=$1
                RETURNING *
                """,
                policy_id,
                policy.name,
                policy.description,
                policy.policy_type,
                policy.effect,
                policy.resource_type,
                policy.resource_pattern,
                policy.subject_type,
                policy.subject_pattern,
                json.dumps(policy.conditions),
                policy.priority,
                policy.enabled,
            )
        return self._policy(row) if row else None

    async def delete_policy(self, policy_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            result = await conn.execute(
                "DELETE FROM governance_policies WHERE id=$1",
                policy_id,
            )
        return result.endswith("1")

    async def record_decision(self, decision: GovernanceDecision) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO governance_policy_decisions(
                    id,execution_id,step_id,policy_id,policy_name,policy_type,
                    effect,resource_type,resource_name,subject_type,subject_id,
                    reason,context
                ) VALUES(
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb
                )
                """,
                decision.id, decision.execution_id, decision.step_id,
                decision.policy_id, decision.policy_name, decision.policy_type,
                decision.effect, decision.resource_type, decision.resource_name,
                decision.subject_type, decision.subject_id, decision.reason,
                json.dumps(decision.context),
            )

    async def list_decisions(
        self,
        *,
        execution_id: UUID | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        async with self._db.require_pool().acquire() as conn:
            if execution_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM governance_policy_decisions
                    WHERE execution_id=$1
                    ORDER BY created_at
                    LIMIT $2
                    """,
                    execution_id, limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM governance_policy_decisions
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
        result=[]
        for row in rows:
            item=dict(row)
            item["context"]=self._decode(item["context"]) or {}
            result.append(item)
        return result

    async def list_budgets(self, *, enabled_only: bool = False) -> list[GovernanceBudget]:
        async with self._db.require_pool().acquire() as conn:
            if enabled_only:
                rows=await conn.fetch(
                    "SELECT * FROM governance_budgets WHERE enabled=true ORDER BY name"
                )
            else:
                rows=await conn.fetch(
                    "SELECT * FROM governance_budgets ORDER BY name"
                )
        return [self._budget(row) for row in rows]

    async def save_budget(self, budget: GovernanceBudget) -> GovernanceBudget:
        async with self._db.require_pool().acquire() as conn:
            row=await conn.fetchrow(
                """
                INSERT INTO governance_budgets(
                    id,name,scope_type,scope_id,period,max_prompt_tokens,
                    max_completion_tokens,max_total_tokens,max_cost_usd,
                    action,degrade_model_profile,enabled
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                ON CONFLICT(name) DO UPDATE SET
                    scope_type=EXCLUDED.scope_type,
                    scope_id=EXCLUDED.scope_id,
                    period=EXCLUDED.period,
                    max_prompt_tokens=EXCLUDED.max_prompt_tokens,
                    max_completion_tokens=EXCLUDED.max_completion_tokens,
                    max_total_tokens=EXCLUDED.max_total_tokens,
                    max_cost_usd=EXCLUDED.max_cost_usd,
                    action=EXCLUDED.action,
                    degrade_model_profile=EXCLUDED.degrade_model_profile,
                    enabled=EXCLUDED.enabled,
                    updated_at=now()
                RETURNING *
                """,
                budget.id,budget.name,budget.scope_type,budget.scope_id,budget.period,
                budget.max_prompt_tokens,budget.max_completion_tokens,
                budget.max_total_tokens,budget.max_cost_usd,budget.action,
                budget.degrade_model_profile,budget.enabled,
            )
        return self._budget(row)

    async def update_budget(
        self,
        budget_id: UUID,
        budget: GovernanceBudget,
    ) -> GovernanceBudget | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE governance_budgets
                SET name=$2,scope_type=$3,scope_id=$4,period=$5,
                    max_prompt_tokens=$6,max_completion_tokens=$7,
                    max_total_tokens=$8,max_cost_usd=$9,action=$10,
                    degrade_model_profile=$11,enabled=$12,updated_at=now()
                WHERE id=$1
                RETURNING *
                """,
                budget_id,
                budget.name,
                budget.scope_type,
                budget.scope_id,
                budget.period,
                budget.max_prompt_tokens,
                budget.max_completion_tokens,
                budget.max_total_tokens,
                budget.max_cost_usd,
                budget.action,
                budget.degrade_model_profile,
                budget.enabled,
            )
        return self._budget(row) if row else None

    async def delete_budget(self, budget_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            result=await conn.execute(
                "DELETE FROM governance_budgets WHERE id=$1",
                budget_id,
            )
        return result.endswith("1")

    async def execution_subjects(self, execution_id: UUID) -> list[tuple[str,str]]:
        async with self._db.require_pool().acquire() as conn:
            row=await conn.fetchrow(
                """
                SELECT e.id,s.scope,s.owner_key
                FROM executions e
                LEFT JOIN sessions s ON s.id=e.session_id
                WHERE e.id=$1
                """,
                execution_id,
            )
        if not row:
            return [("GLOBAL","*"),("EXECUTION",str(execution_id))]
        subjects=[("GLOBAL","*"),("EXECUTION",str(execution_id))]
        if row["scope"] and row["owner_key"]:
            subjects.append((str(row["scope"]).upper(),str(row["owner_key"])))
        return list(dict.fromkeys(subjects))

    async def aggregate_usage(
        self,
        *,
        scope_type: str,
        scope_id: str,
        period: str,
        execution_id: UUID,
    ) -> dict[str,float]:
        clauses=["scope_type=$1","scope_id=$2"]
        values: list[Any] = [scope_type, scope_id]
        if period=="EXECUTION":
            clauses.append("execution_id=$3")
            values.append(execution_id)
        elif period=="DAILY":
            clauses.append("created_at >= date_trunc('day', now())")
        elif period=="MONTHLY":
            clauses.append("created_at >= date_trunc('month', now())")
        sql=(
            "SELECT COALESCE(sum(prompt_tokens),0) prompt_tokens,"
            "COALESCE(sum(completion_tokens),0) completion_tokens,"
            "COALESCE(sum(total_tokens),0) total_tokens,"
            "COALESCE(sum(estimated_cost_usd),0) estimated_cost_usd "
            "FROM governance_usage WHERE "+" AND ".join(clauses)
        )
        async with self._db.require_pool().acquire() as conn:
            row=await conn.fetchrow(sql,*values)
        return {k:float(v or 0) for k,v in dict(row).items()}

    async def record_usage(
        self,
        *,
        execution_id: UUID | None,
        step_id: str | None,
        scopes: list[tuple[str,str]],
        model_profile: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        estimated_cost_usd: float,
    ) -> None:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                for scope_type,scope_id in scopes:
                    await conn.execute(
                        """
                        INSERT INTO governance_usage(
                            id,execution_id,step_id,scope_type,scope_id,
                            model_profile,prompt_tokens,completion_tokens,
                            total_tokens,estimated_cost_usd
                        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        """,
                        uuid4(),execution_id,step_id,scope_type,scope_id,
                        model_profile,prompt_tokens,completion_tokens,
                        total_tokens,estimated_cost_usd,
                    )

    async def record_budget_decision(
        self,
        *,
        execution_id: UUID,
        step_id: str | None,
        budget_id: UUID | None,
        budget_name: str | None,
        action: str,
        allowed: bool,
        requested_model_profile: str,
        effective_model_profile: str,
        reason: str | None,
        current: dict[str, Any],
        projected: dict[str, Any],
    ) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO governance_budget_decisions(
                    id,execution_id,step_id,budget_id,budget_name,action,allowed,
                    requested_model_profile,effective_model_profile,reason,
                    current_usage,projected_usage
                ) VALUES(
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::jsonb
                )
                """,
                uuid4(),
                execution_id,
                step_id,
                budget_id,
                budget_name,
                action,
                allowed,
                requested_model_profile,
                effective_model_profile,
                reason,
                json.dumps(current),
                json.dumps(projected),
            )

    async def list_budget_decisions(
        self,
        *,
        execution_id: UUID | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        async with self._db.require_pool().acquire() as conn:
            if execution_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM governance_budget_decisions
                    WHERE execution_id=$1
                    ORDER BY created_at
                    LIMIT $2
                    """,
                    execution_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM governance_budget_decisions
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["current_usage"] = self._decode(item["current_usage"]) or {}
            item["projected_usage"] = self._decode(item["projected_usage"]) or {}
            result.append(item)
        return result

    async def usage_summary(self, execution_id: UUID) -> dict[str,Any]:
        async with self._db.require_pool().acquire() as conn:
            total=await conn.fetchrow(
                """
                SELECT COALESCE(sum(prompt_tokens),0) prompt_tokens,
                       COALESCE(sum(completion_tokens),0) completion_tokens,
                       COALESCE(sum(total_tokens),0) total_tokens,
                       COALESCE(sum(estimated_cost_usd),0) estimated_cost_usd
                FROM governance_usage
                WHERE execution_id=$1 AND scope_type='EXECUTION'
                """,
                execution_id,
            )
            rows=await conn.fetch(
                """
                SELECT model_profile,
                       sum(prompt_tokens) prompt_tokens,
                       sum(completion_tokens) completion_tokens,
                       sum(total_tokens) total_tokens,
                       sum(estimated_cost_usd) estimated_cost_usd
                FROM governance_usage
                WHERE execution_id=$1 AND scope_type='EXECUTION'
                GROUP BY model_profile
                ORDER BY model_profile
                """,
                execution_id,
            )
        return {
            "total":{k:float(v or 0) for k,v in dict(total).items()},
            "byModel":[{k:(float(v) if k!="model_profile" else v) for k,v in dict(row).items()} for row in rows],
        }

    @staticmethod
    def _decode(value):
        return json.loads(value) if isinstance(value,str) else value

    @classmethod
    def _policy(cls,row)->GovernancePolicy:
        return GovernancePolicy(
            id=row["id"],name=row["name"],description=row["description"],
            policy_type=row["policy_type"],effect=row["effect"],
            resource_type=row["resource_type"],resource_pattern=row["resource_pattern"],
            subject_type=row["subject_type"],subject_pattern=row["subject_pattern"],
            conditions=dict(cls._decode(row["conditions"]) or {}),
            priority=row["priority"],enabled=row["enabled"],source=row["source"],
            created_at=row["created_at"],updated_at=row["updated_at"],
        )

    @classmethod
    def _budget(cls,row)->GovernanceBudget:
        return GovernanceBudget(
            id=row["id"],name=row["name"],scope_type=row["scope_type"],
            scope_id=row["scope_id"],period=row["period"],
            max_prompt_tokens=row["max_prompt_tokens"],
            max_completion_tokens=row["max_completion_tokens"],
            max_total_tokens=row["max_total_tokens"],
            max_cost_usd=float(row["max_cost_usd"]) if row["max_cost_usd"] is not None else None,
            action=row["action"],degrade_model_profile=row["degrade_model_profile"],
            enabled=row["enabled"],created_at=row["created_at"],updated_at=row["updated_at"],
        )
