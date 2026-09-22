from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status

from app.business.execution_service import ExecutionService
from app.domain.execution import Command, ExecutionSubmission
from app.infrastructure.api.rest.schemas import RestExecutionAccepted, RestExecutionRequest


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

    @router.get("/executions/{execution_id}")
    async def get_execution(execution_id: UUID) -> dict:
        execution = await service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        return {
            "executionId": str(execution["id"]),
            "correlationId": execution["correlation_id"],
            "command": {"name": execution["command_name"]},
            "intent": execution["intent"],
            "status": execution["status"],
            "result": execution["result"],
            "error": execution["error"],
            "createdAt": execution["created_at"],
            "updatedAt": execution["updated_at"],
            "completedAt": execution["completed_at"],
        }

    return router
