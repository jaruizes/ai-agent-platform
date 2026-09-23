from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.infrastructure.api.messaging.nats_adapter import NatsAdapter
from app.infrastructure.config.settings import Settings
from app.infrastructure.persistence.postgres.database import Database


def create_admin_router(
    database: Database,
    nats_adapter: NatsAdapter,
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/v1/admin", tags=["control-plane"])

    @router.get("/executions")
    async def list_executions(
        limit: int = Query(default=100, ge=1, le=500),
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = database.require_pool()
        filters = ""
        values: list[Any] = []
        if status:
            filters = "WHERE e.status=$1"
            values.append(status.upper())
        values.append(limit)
        limit_param = f"${len(values)}"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    e.id,
                    e.correlation_id,
                    e.session_id,
                    e.command_name,
                    e.intent,
                    e.status,
                    e.control_action,
                    e.control_reason,
                    e.created_at,
                    e.updated_at,
                    e.completed_at,
                    e.lease_owner,
                    e.lease_expires_at,
                    ep.objective,
                    ep.status AS plan_status,
                    ep.planner_model,
                    COALESCE(
                        (
                            SELECT COUNT(*)
                            FROM execution_plan_steps s
                            WHERE s.execution_id=e.id
                              AND s.status='WAITING_APPROVAL'
                        ), 0
                    ) AS waiting_approvals,
                    COALESCE(
                        (
                            SELECT COUNT(*)
                            FROM execution_plan_steps s
                            WHERE s.execution_id=e.id
                              AND s.status='RETRYING'
                        ), 0
                    ) AS retrying_steps
                FROM executions e
                LEFT JOIN execution_plans ep ON ep.execution_id=e.id
                {filters}
                ORDER BY e.created_at DESC
                LIMIT {limit_param}
                """,
                *values,
            )
        return [
            {
                "executionId": str(row["id"]),
                "correlationId": row["correlation_id"],
                "sessionId": (
                    str(row["session_id"])
                    if row["session_id"]
                    else None
                ),
                "commandName": row["command_name"],
                "intent": row["intent"],
                "status": row["status"],
                "controlAction": row["control_action"],
                "controlReason": row["control_reason"],
                "objective": row["objective"],
                "planStatus": row["plan_status"],
                "plannerModel": row["planner_model"],
                "waitingApprovals": int(row["waiting_approvals"] or 0),
                "retryingSteps": int(row["retrying_steps"] or 0),
                "leaseOwner": row["lease_owner"],
                "leaseExpiresAt": row["lease_expires_at"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "completedAt": row["completed_at"],
            }
            for row in rows
        ]

    @router.get("/approvals")
    async def list_pending_approvals() -> list[dict[str, Any]]:
        pool = database.require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    e.id AS execution_id,
                    e.command_name,
                    e.intent,
                    e.created_at,
                    s.step_id,
                    s.description,
                    s.agent_name,
                    s.tool_name,
                    s.approval_reason,
                    s.approval_source,
                    s.tool_side_effect,
                    s.tool_approval_policy,
                    s.started_at
                FROM execution_plan_steps s
                JOIN executions e ON e.id=s.execution_id
                WHERE s.status='WAITING_APPROVAL'
                  AND s.approval_status='PENDING'
                ORDER BY COALESCE(s.started_at,e.created_at)
                """
            )
        return [
            {
                "executionId": str(row["execution_id"]),
                "commandName": row["command_name"],
                "intent": row["intent"],
                "executionCreatedAt": row["created_at"],
                "stepId": row["step_id"],
                "description": row["description"],
                "agent": row["agent_name"],
                "tool": row["tool_name"],
                "reason": row["approval_reason"],
                "approvalSource": row["approval_source"],
                "sideEffect": row["tool_side_effect"],
                "approvalPolicy": row["tool_approval_policy"],
                "waitingSince": row["started_at"],
            }
            for row in rows
        ]

    @router.get("/overview")
    async def overview() -> dict[str, Any]:
        pool = database.require_pool()
        async with pool.acquire() as conn:
            status_rows = await conn.fetch(
                "SELECT status,COUNT(*) AS count FROM executions GROUP BY status"
            )
            totals = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM executions) AS executions,
                    (SELECT COUNT(*) FROM agents) AS agents,
                    (SELECT COUNT(*) FROM skills) AS skills,
                    (SELECT COUNT(*) FROM tools) AS tools,
                    (SELECT COUNT(*) FROM mcp_servers) AS mcp_servers,
                    (SELECT COUNT(*) FROM prompts) AS prompts,
                    (SELECT COUNT(*) FROM knowledge_bases) AS knowledge_bases,
                    (SELECT COUNT(*) FROM knowledge_documents) AS documents,
                    (SELECT COUNT(*) FROM sessions WHERE status='ACTIVE') AS sessions,
                    (SELECT COUNT(*) FROM memory_entries WHERE status='ACTIVE') AS memories,
                    (SELECT COUNT(*) FROM context_snapshots) AS context_snapshots,
                    (
                        SELECT COUNT(*) FROM execution_plan_steps
                        WHERE status='WAITING_APPROVAL'
                          AND approval_status='PENDING'
                    ) AS pending_approvals,
                    (
                        SELECT COUNT(*) FROM execution_plan_steps
                        WHERE status='RETRYING'
                    ) AS retrying_steps,
                    (
                        SELECT COUNT(*) FROM outbox_events
                        WHERE published_at IS NULL
                    ) AS outbox_pending
                """
            )
        return {
            "version": settings.service_version,
            "executionsByStatus": {
                row["status"]: int(row["count"]) for row in status_rows
            },
            "totals": {key: int(value or 0) for key, value in dict(totals).items()},
        }

    @router.get("/runtime")
    async def runtime() -> dict[str, Any]:
        postgres_up = False
        try:
            async with database.require_pool().acquire() as conn:
                postgres_up = bool(await conn.fetchval("SELECT true"))
        except Exception:
            postgres_up = False

        nats_up = bool(
            nats_adapter.nc is not None and nats_adapter.nc.is_connected
        )
        return {
            "service": {
                "name": settings.service_name,
                "version": settings.service_version,
            },
            "dependencies": {
                "postgres": {"status": "UP" if postgres_up else "DOWN"},
                "nats": {"status": "UP" if nats_up else "DOWN"},
                "litellm": {
                    "status": "CONFIGURED",
                    "baseUrl": settings.litellm_base_url,
                },
                "otel": {
                    "status": "CONFIGURED",
                    "endpoint": settings.otel_exporter_otlp_endpoint,
                },
            },
            "models": {
                "router": settings.router_model_profile,
                "planner": settings.planner_model_profile,
                "execution": settings.execution_model_profile,
            },
            "contextEngine": {
                "modelWindowTokens": settings.context_model_window_tokens,
                "reservedOutputTokens": settings.context_reserved_output_tokens,
                "safetyMarginTokens": settings.context_safety_margin_tokens,
                "availableInputTokens": (
                    settings.context_model_window_tokens
                    - settings.context_reserved_output_tokens
                    - settings.context_safety_margin_tokens
                ),
                "sessionMaxEntries": settings.context_session_max_entries,
                "memoryTopK": settings.context_memory_top_k,
                "minCompressionTokens": settings.context_min_compression_tokens,
            },
            "memory": {
                "allowInferredPersistence": settings.memory_allow_inferred_persistence,
                "minInferredConfidence": settings.memory_min_inferred_confidence,
                "maxContentChars": settings.memory_max_content_chars,
                "autoExtractSession": settings.memory_auto_extract_session,
                "extractorModelProfile": settings.memory_extractor_model_profile,
                "extractorMaxCandidates": settings.memory_extractor_max_candidates,
            },
            "knowledge": {
                "embeddingProvider": settings.knowledge_embedding_provider,
                "embeddingModel": settings.knowledge_embedding_model,
                "dimensions": settings.knowledge_embedding_dimensions,
                "topK": settings.knowledge_top_k,
            },
            "memory": {
                "allowInferredPersistence": settings.memory_allow_inferred_persistence,
                "minInferredConfidence": settings.memory_min_inferred_confidence,
                "maxContentChars": settings.memory_max_content_chars,
                "cleanupPollSeconds": settings.memory_cleanup_poll_seconds,
            },
            "durability": {
                "leaseSeconds": settings.execution_lease_seconds,
                "heartbeatSeconds": settings.execution_heartbeat_seconds,
                "controlPollSeconds": settings.execution_control_poll_seconds,
                "maxPlanSteps": settings.orchestration_max_steps,
            },
        }

    return router
