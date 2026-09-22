import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response, status
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.config import get_settings
from app.db import Database
from app.intent_resolver import IntentResolver
from app.model_gateway import ModelGateway
from app.models import RestExecutionAccepted, RestExecutionRequest
from app.nats_client import NatsClient
from app.repository import ExecutionRepository
from app.service import ExecutionService
from app.telemetry import configure_telemetry


settings = get_settings()
configure_telemetry(settings)
HTTPXClientInstrumentor().instrument()

database = Database(settings.database_url)
nats_client = NatsClient(settings)
repository = ExecutionRepository(database)
resolver = IntentResolver()
model_gateway = ModelGateway(settings)
service = ExecutionService(settings, repository, resolver, model_gateway, nats_client)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()
    await nats_client.connect()
    await nats_client.subscribe_commands(service.submit_nats)
    worker = asyncio.create_task(service.worker_loop(), name="execution-worker")
    outbox = asyncio.create_task(service.outbox_loop(), name="outbox-publisher")
    try:
        yield
    finally:
        await service.stop()
        for task in (worker, outbox):
            task.cancel()
        await model_gateway.close()
        await nats_client.close()
        await database.close()


app = FastAPI(
    title="AI Agent Platform",
    version=settings.service_version,
    lifespan=lifespan,
)
FastAPIInstrumentor.instrument_app(app)


@app.get("/health/live")
async def live() -> dict:
    return {"status": "UP"}


@app.get("/health/ready")
async def ready() -> dict:
    if database.pool is None or nats_client.nc is None or not nats_client.nc.is_connected:
        raise HTTPException(status_code=503, detail="Dependencies are not ready")
    return {"status": "UP"}


@app.post(
    "/v1/executions",
    response_model=RestExecutionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_execution(request: RestExecutionRequest, response: Response):
    execution_id, correlation_id = await service.submit_rest(
        correlation_id=request.correlationId,
        command=request.command,
    )
    response.headers["Location"] = f"/v1/executions/{execution_id}"
    return RestExecutionAccepted(
        executionId=execution_id,
        correlationId=correlation_id,
    )


@app.get("/v1/executions/{execution_id}")
async def get_execution(execution_id: UUID):
    execution = await repository.get(execution_id)
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
