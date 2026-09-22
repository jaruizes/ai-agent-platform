import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.business.catalog_service import CatalogService
from app.business.execution_service import ExecutionService
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.business.intent_resolver import IntentResolver
from app.infrastructure.api.messaging.nats_adapter import NatsAdapter
from app.infrastructure.api.rest.catalog_router import create_catalog_router
from app.infrastructure.api.rest.prompt_router import create_prompt_router
from app.infrastructure.api.rest.tool_router import create_tool_router
from app.infrastructure.api.rest.router import create_router
from app.infrastructure.bootstrap.markdown_loader import MarkdownCatalogLoader
from app.infrastructure.config.settings import get_settings
from app.infrastructure.externalservices.litellm.model_gateway import LiteLLMModelGateway
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient
from app.infrastructure.externalservices.mcp.tool_executor import InfrastructureToolExecutor
from app.infrastructure.observability.telemetry import configure_telemetry
from app.infrastructure.persistence.postgres.catalog_repository import PostgresCatalogRepository
from app.infrastructure.persistence.postgres.database import Database
from app.infrastructure.persistence.postgres.execution_repository import PostgresExecutionRepository
from app.infrastructure.persistence.postgres.prompt_repository import PostgresPromptRepository
from app.infrastructure.persistence.postgres.tool_repository import PostgresToolRepository


settings = get_settings()
configure_telemetry(settings)
HTTPXClientInstrumentor().instrument()

database = Database(settings.database_url)
execution_repository = PostgresExecutionRepository(database)
catalog_repository = PostgresCatalogRepository(database)
catalog_service = CatalogService(catalog_repository)
prompt_repository = PostgresPromptRepository(database)
prompt_service = PromptService(prompt_repository)
tool_repository = PostgresToolRepository(database)
mcp_client = McpStdioClient(
    timeout_seconds=settings.mcp_timeout_seconds,
    max_message_bytes=settings.mcp_max_message_bytes,
)
tool_executor = InfrastructureToolExecutor(tool_repository, mcp_client)
tool_service = ToolService(tool_repository, tool_executor)
model_gateway = LiteLLMModelGateway(settings)
intent_resolver = IntentResolver(
    catalog_repository,
    prompt_service,
    tool_service,
    model_gateway,
    router_model_profile=settings.router_model_profile,
    execution_model_profile=settings.execution_model_profile,
)
nats_adapter = NatsAdapter(settings)

execution_service = ExecutionService(
    repository=execution_repository,
    resolver=intent_resolver,
    model_gateway=model_gateway,
    tool_service=tool_service,
    event_publisher=nats_adapter,
    worker_poll_seconds=settings.worker_poll_seconds,
    outbox_poll_seconds=settings.outbox_poll_seconds,
)

bootstrap_loader = MarkdownCatalogLoader(
    catalog_service,
    prompt_service,
    tool_service,
    skills_dir=settings.bootstrap_skills_dir,
    agents_dir=settings.bootstrap_agents_dir,
    prompts_dir=settings.bootstrap_prompts_dir,
    tools_dir=settings.bootstrap_tools_dir,
    mcp_servers_dir=settings.bootstrap_mcp_servers_dir,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.connect()
    await bootstrap_loader.load()
    await nats_adapter.connect()
    await nats_adapter.subscribe_commands(execution_service)

    worker = asyncio.create_task(execution_service.worker_loop(), name="execution-worker")
    outbox = asyncio.create_task(execution_service.outbox_loop(), name="outbox-publisher")

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
app.include_router(create_catalog_router(catalog_service))
app.include_router(create_prompt_router(prompt_service))
app.include_router(create_tool_router(tool_service))
FastAPIInstrumentor.instrument_app(app)


@app.get("/health/live")
async def live() -> dict:
    return {"status": "UP"}


@app.get("/health/ready")
async def ready() -> dict:
    if database.pool is None or nats_adapter.nc is None or not nats_adapter.nc.is_connected:
        raise HTTPException(status_code=503, detail="Dependencies are not ready")
    return {"status": "UP"}
