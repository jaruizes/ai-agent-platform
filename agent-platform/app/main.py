import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.business.execution_service import ExecutionService
from app.business.intent_resolver import IntentResolver
from app.infrastructure.api.messaging.nats_adapter import NatsAdapter
from app.infrastructure.api.rest.router import create_router
from app.infrastructure.config.settings import get_settings
from app.infrastructure.externalservices.litellm.model_gateway import LiteLLMModelGateway
from app.infrastructure.observability.telemetry import configure_telemetry
from app.infrastructure.persistence.postgres.database import Database
from app.infrastructure.persistence.postgres.execution_repository import (
    PostgresExecutionRepository,
)


settings = get_settings()
configure_telemetry(settings)
HTTPXClientInstrumentor().instrument()

database = Database(settings.database_url)
repository = PostgresExecutionRepository(database)
intent_resolver = IntentResolver()
model_gateway = LiteLLMModelGateway(settings)
nats_adapter = NatsAdapter(settings)

execution_service = ExecutionService(
    repository=repository,
    resolver=intent_resolver,
    model_gateway=model_gateway,
    event_publisher=nats_adapter,
    worker_poll_seconds=settings.worker_poll_seconds,
    outbox_poll_seconds=settings.outbox_poll_seconds,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()
    await nats_adapter.connect()
    await nats_adapter.subscribe_commands(execution_service)

    worker = asyncio.create_task(
        execution_service.worker_loop(),
        name="execution-worker",
    )
    outbox = asyncio.create_task(
        execution_service.outbox_loop(),
        name="outbox-publisher",
    )

    try:
        yield
    finally:
        await execution_service.stop()
        for task in (worker, outbox):
            task.cancel()
        await model_gateway.close()
        await nats_adapter.close()
        await database.close()


app = FastAPI(
    title="AI Agent Platform",
    version=settings.service_version,
    lifespan=lifespan,
)
app.include_router(create_router(execution_service))
FastAPIInstrumentor.instrument_app(app)


@app.get("/health/live")
async def live() -> dict:
    return {"status": "UP"}


@app.get("/health/ready")
async def ready() -> dict:
    if database.pool is None or nats_adapter.nc is None or not nats_adapter.nc.is_connected:
        raise HTTPException(status_code=503, detail="Dependencies are not ready")
    return {"status": "UP"}
