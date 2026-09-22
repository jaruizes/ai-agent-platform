from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status

from app.business.execution_service import ExecutionService
from app.domain.execution import Command, ExecutionSubmission
from app.infrastructure.api.rest.schemas import (
    ExecutionControlRequest,
    RestExecutionAccepted,
    RestExecutionRequest,
    StepApprovalRequest,
)


def create_router(service: ExecutionService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.post(
        "/executions",
        response_model=RestExecutionAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_execution(
        request: RestExecutionRequest,
        response: Response,
    ) -> RestExecutionAccepted:
        execution_id = uuid4()
        message_id = str(uuid4())
        correlation_id = request.correlationId or str(uuid4())

        command = Command(
            name=request.command.name,
            intent=request.command.intent,
            input=request.command.input,
            context=request.command.context,
            instructions=request.command.instructions,
            metadata=request.command.metadata,
        )
        submission = ExecutionSubmission(
            execution_id=execution_id,
            message_id=message_id,
            correlation_id=correlation_id,
            source={"type": "application", "name": "rest-client"},
            command=command,
        )

        persisted_id, _ = await service.submit(submission)
        response.headers["Location"] = f"/v1/executions/{persisted_id}"
        return RestExecutionAccepted(
            executionId=persisted_id,
            correlationId=correlation_id,
        )

    @router.get("/executions/{execution_id}/orchestration")
    async def get_orchestration(execution_id: UUID) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        orchestration = await service.get_orchestration(execution_id)
        if not orchestration:
            return {
                "executionId": str(execution_id),
                "status": "NOT_PLANNED",
                "plan": None,
                "steps": [],
                "activeAgents": [],
                "waitingApprovals": [],
                "retryingSteps": [],
                "usage": {
                    "promptTokens": 0,
                    "completionTokens": 0,
                    "totalTokens": 0,
                },
            }

        plan = orchestration["plan"]
        return {
            "executionId": str(execution_id),
            "status": plan["status"],
            "plan": {
                "objective": plan["objective"],
                "finalStepId": plan["logical_plan"]["finalStepId"],
                "logicalPlan": plan["logical_plan"],
                "validation": plan["validation"],
                "planner": {
                    "model": plan["planner_model"],
                    "usage": plan["planner_usage"],
                },
                "createdAt": plan["created_at"],
                "startedAt": plan["started_at"],
                "completedAt": plan["completed_at"],
            },
            "steps": [
                {
                    "id": step["step_id"],
                    "type": step["step_type"],
                    "description": step["description"],
                    "agent": step["agent_name"],
                    "tool": step["tool_name"],
                    "knowledgeBases": step["knowledge_bases"],
                    "dependsOn": step["depends_on"],
                    "status": step["status"],
                    "requiresApproval": step.get("requires_approval", False),
                    "approval": {
                        "status": step.get("approval_status"),
                        "reason": step.get("approval_reason"),
                        "actor": step.get("approval_actor"),
                        "comment": step.get("approval_comment"),
                        "updatedAt": step.get("approval_updated_at"),
                    },
                    "attemptCount": step.get("attempt_count", 0),
                    "maxAttempts": step.get("max_attempts", 1),
                    "timeoutSeconds": step.get("timeout_seconds"),
                    "retryPolicy": step.get("retry_policy") or {},
                    "nextRetryAt": step.get("next_retry_at"),
                    "idempotencyKey": step.get("idempotency_key"),
                    "usage": step["usage"],
                    "output": step["output"],
                    "error": step["error"],
                    "startedAt": step["started_at"],
                    "completedAt": step["completed_at"],
                }
                for step in orchestration["steps"]
            ],
            "activeAgents": orchestration["activeAgents"],
            "waitingApprovals": orchestration.get("waitingApprovals", []),
            "retryingSteps": orchestration.get("retryingSteps", []),
            "usage": orchestration["usage"],
        }

    @router.post("/executions/{execution_id}/pause")
    async def pause_execution(
        execution_id: UUID,
        request: ExecutionControlRequest,
    ) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not await service.pause_execution(execution_id, reason=request.reason):
            raise HTTPException(
                status_code=409,
                detail=f"Execution cannot be paused from status {execution['status']}",
            )
        return {
            "executionId": str(execution_id),
            "requestedState": "PAUSED",
            "status": "PAUSING",
        }

    @router.post("/executions/{execution_id}/resume")
    async def resume_execution(execution_id: UUID) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not await service.resume_execution(execution_id):
            raise HTTPException(
                status_code=409,
                detail=f"Execution cannot be resumed from status {execution['status']}",
            )
        return {
            "executionId": str(execution_id),
            "status": "ACCEPTED",
        }

    @router.post("/executions/{execution_id}/cancel")
    async def cancel_execution(
        execution_id: UUID,
        request: ExecutionControlRequest,
    ) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not await service.cancel_execution(execution_id, reason=request.reason):
            raise HTTPException(
                status_code=409,
                detail=f"Execution cannot be cancelled from status {execution['status']}",
            )
        return {
            "executionId": str(execution_id),
            "requestedState": "CANCELLED",
            "status": "CANCELLING",
        }

    @router.post("/executions/{execution_id}/steps/{step_id}/approval")
    async def decide_step_approval(
        execution_id: UUID,
        step_id: str,
        request: StepApprovalRequest,
    ) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not await service.decide_step_approval(
            execution_id,
            step_id,
            approved=request.approved,
            actor=request.actor,
            comment=request.comment,
        ):
            raise HTTPException(
                status_code=409,
                detail="Step is not waiting for approval",
            )
        return {
            "executionId": str(execution_id),
            "stepId": step_id,
            "decision": "APPROVED" if request.approved else "REJECTED",
        }

    @router.get("/executions/{execution_id}")
    async def get_execution(execution_id: UUID) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        orchestration = await service.get_orchestration(execution_id)
        return {
            "executionId": str(execution["id"]),
            "correlationId": execution["correlation_id"],
            "command": {"name": execution["command_name"]},
            "intent": execution["intent"],
            "status": execution["status"],
            "control": {
                "action": execution.get("control_action"),
                "reason": execution.get("control_reason"),
            },
            "lease": {
                "owner": execution.get("lease_owner"),
                "expiresAt": execution.get("lease_expires_at"),
                "lastHeartbeatAt": execution.get("last_heartbeat_at"),
            },
            "result": execution["result"],
            "error": execution["error"],
            "orchestration": {
                "status": orchestration["plan"]["status"],
                "objective": orchestration["plan"]["objective"],
                "activeAgents": orchestration["activeAgents"],
                "waitingApprovals": orchestration.get("waitingApprovals", []),
                "retryingSteps": orchestration.get("retryingSteps", []),
                "usage": orchestration["usage"],
            } if orchestration else None,
            "createdAt": execution["created_at"],
            "updatedAt": execution["updated_at"],
            "completedAt": execution["completed_at"],
        }

    return router
