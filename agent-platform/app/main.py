import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.business.catalog_service import CatalogService
from app.business.context_engine import ContextEngine
from app.business.execution_service import ExecutionService
from app.business.eval_service import EvalService
from app.business.governance_service import GovernanceService
from app.business.knowledge_service import KnowledgeService
from app.business.memory_candidate_extractor import MemoryCandidateExtractor
from app.business.memory_policy import MemoryPolicyEngine
from app.business.memory_service import MemoryService
from app.business.plan_policy_enricher import PlanPolicyEnricher
from app.business.plan_validator import PlanValidator
from app.business.planner_service import PlannerService
from app.business.prompt_service import PromptService
from app.business.step_executor import StepExecutor
from app.business.tool_service import ToolService
from app.infrastructure.api.messaging.nats_adapter import NatsAdapter
from app.infrastructure.api.rest.admin_router import create_admin_router
from app.infrastructure.api.rest.catalog_router import create_catalog_router
from app.infrastructure.api.rest.governance_router import create_governance_router
from app.infrastructure.api.rest.eval_router import create_eval_router
from app.infrastructure.api.rest.prompt_router import create_prompt_router
from app.infrastructure.api.rest.knowledge_router import create_knowledge_router
from app.infrastructure.api.rest.memory_router import create_memory_router
from app.infrastructure.api.rest.tool_router import create_tool_router
from app.infrastructure.api.rest.router import create_router
from app.infrastructure.bootstrap.markdown_loader import MarkdownCatalogLoader
from app.infrastructure.config.settings import get_settings
from app.infrastructure.externalservices.governed_model_gateway import GovernedModelGateway
from app.infrastructure.externalservices.litellm.model_gateway import LiteLLMModelGateway
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient
from app.infrastructure.externalservices.mcp.tool_executor import InfrastructureToolExecutor
from app.infrastructure.knowledge.embeddings import HashEmbeddingProvider
from app.infrastructure.knowledge.parsers import DocumentParser
from app.infrastructure.orchestration.langgraph_engine import LangGraphOrchestrationEngine
from app.infrastructure.observability.telemetry import configure_telemetry
from app.infrastructure.persistence.postgres.catalog_repository import PostgresCatalogRepository
from app.infrastructure.persistence.postgres.database import Database
from app.infrastructure.persistence.postgres.execution_repository import PostgresExecutionRepository
from app.infrastructure.persistence.postgres.eval_repository import PostgresEvalRepository
from app.infrastructure.persistence.postgres.governance_repository import PostgresGovernanceRepository
from app.infrastructure.persistence.postgres.knowledge_repository import PostgresKnowledgeRepository
from app.infrastructure.persistence.postgres.memory_repository import PostgresMemoryRepository
from app.infrastructure.persistence.postgres.prompt_repository import PostgresPromptRepository
from app.infrastructure.persistence.postgres.tool_repository import PostgresToolRepository


settings = get_settings()
configure_telemetry(settings)
HTTPXClientInstrumentor().instrument()

database = Database(settings.database_url)
execution_repository = PostgresExecutionRepository(database)

if settings.knowledge_embedding_provider.lower() != "hash":
    raise ValueError(
        "Unsupported KNOWLEDGE_EMBEDDING_PROVIDER. "
        "Current portable runtime supports 'hash'; add another EmbeddingProvider adapter for cloud embeddings."
    )
embedding_provider = HashEmbeddingProvider(
    dimensions=settings.knowledge_embedding_dimensions,
    model=settings.knowledge_embedding_model,
)

memory_repository = PostgresMemoryRepository(database)
memory_policy = MemoryPolicyEngine(
    min_inferred_confidence=settings.memory_min_inferred_confidence,
    max_content_chars=settings.memory_max_content_chars,
    allow_inferred_persistence=settings.memory_allow_inferred_persistence,
)
memory_service = MemoryService(
    repository=memory_repository,
    policy=memory_policy,
    embedding_provider=embedding_provider,
    cleanup_poll_seconds=settings.memory_cleanup_poll_seconds,
)
governance_repository = PostgresGovernanceRepository(database)
governance_service = GovernanceService(
    governance_repository,
    pricing={
        settings.router_model_profile: (
            settings.governance_router_input_usd_per_million,
            settings.governance_router_output_usd_per_million,
        ),
        settings.execution_model_profile: (
            settings.governance_execution_input_usd_per_million,
            settings.governance_execution_output_usd_per_million,
        ),
        settings.planner_model_profile: (
            settings.governance_planner_input_usd_per_million,
            settings.governance_planner_output_usd_per_million,
        ),
    },
)
context_engine = ContextEngine(
    memory_service,
    governance_service=governance_service,
    model_window_tokens=settings.context_model_window_tokens,
    reserved_output_tokens=settings.context_reserved_output_tokens,
    safety_margin_tokens=settings.context_safety_margin_tokens,
    max_session_entries=settings.context_session_max_entries,
    memory_top_k=settings.context_memory_top_k,
    memory_min_score=settings.context_memory_min_score,
    min_compression_tokens=settings.context_min_compression_tokens,
)

catalog_repository = PostgresCatalogRepository(database)
catalog_service = CatalogService(catalog_repository)
prompt_repository = PostgresPromptRepository(database)
prompt_service = PromptService(prompt_repository)
tool_repository = PostgresToolRepository(database)
document_parser = DocumentParser()
mcp_client = McpStdioClient(
    timeout_seconds=settings.mcp_timeout_seconds,
    max_message_bytes=settings.mcp_max_message_bytes,
)
tool_executor = InfrastructureToolExecutor(
    tool_repository,
    mcp_client,
    document_parser,
    mcp_workspace_root=settings.mcp_workspace_root,
)
tool_service = ToolService(tool_repository, tool_executor)
raw_model_gateway = LiteLLMModelGateway(settings)
model_gateway = GovernedModelGateway(
    raw_model_gateway,
    governance_service,
    default_projected_completion_tokens=(
        settings.governance_default_projected_completion_tokens
    ),
    prompt_estimate_multiplier=settings.governance_prompt_estimate_multiplier,
)
if (
    settings.memory_auto_extract_session
    and settings.memory_allow_inferred_persistence
):
    memory_extractor = MemoryCandidateExtractor(
        model_gateway,
        model_profile=settings.memory_extractor_model_profile,
        max_candidates=settings.memory_extractor_max_candidates,
        max_input_chars=settings.memory_extractor_max_input_chars,
    )
else:
    memory_extractor = None
knowledge_repository = PostgresKnowledgeRepository(database)
knowledge_service = KnowledgeService(
    repository=knowledge_repository,
    embedding_provider=embedding_provider,
    tool_service=tool_service,
    parser=document_parser,
    storage_root=settings.knowledge_storage_root,
    embedding_batch_size=settings.knowledge_embedding_batch_size,
    worker_poll_seconds=settings.knowledge_worker_poll_seconds,
    cleanup_poll_seconds=settings.knowledge_cleanup_poll_seconds,
)
plan_validator = PlanValidator(max_steps=settings.orchestration_max_steps)
plan_policy_enricher = PlanPolicyEnricher()
planner_service = PlannerService(
    catalog_repository,
    prompt_service,
    tool_service,
    knowledge_service,
    model_gateway,
    plan_validator,
    plan_policy_enricher,
    planner_model_profile=settings.planner_model_profile,
)
step_executor = StepExecutor(
    catalog=catalog_repository,
    prompt_service=prompt_service,
    tool_service=tool_service,
    knowledge_service=knowledge_service,
    model_gateway=model_gateway,
    execution_repository=execution_repository,
    context_engine=context_engine,
    governance_service=governance_service,
    execution_model_profile=settings.execution_model_profile,
    knowledge_top_k=settings.knowledge_top_k,
    max_context_chars=settings.max_tool_result_chars_for_model,
    control_poll_seconds=settings.execution_control_poll_seconds,
)
orchestration_engine = LangGraphOrchestrationEngine(
    step_executor=step_executor,
    execution_repository=execution_repository,
)
nats_adapter = NatsAdapter(settings)

execution_service = ExecutionService(
    repository=execution_repository,
    planner=planner_service,
    orchestration_engine=orchestration_engine,
    event_publisher=nats_adapter,
    memory_service=memory_service,
    memory_candidate_extractor=memory_extractor,
    governance_service=governance_service,
    execution_model_profile=settings.execution_model_profile,
    worker_poll_seconds=settings.worker_poll_seconds,
    outbox_poll_seconds=settings.outbox_poll_seconds,
    execution_lease_seconds=settings.execution_lease_seconds,
    execution_heartbeat_seconds=settings.execution_heartbeat_seconds,
)

eval_repository = PostgresEvalRepository(database)
eval_service = EvalService(
    eval_repository,
    execution_service,
    governance_service,
    model_gateway,
    worker_poll_seconds=settings.worker_poll_seconds,
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
    knowledge_worker = asyncio.create_task(
        knowledge_service.worker_loop(),
        name="knowledge-worker",
    )
    knowledge_cleanup = asyncio.create_task(
        knowledge_service.cleanup_loop(),
        name="knowledge-cleanup",
    )
    memory_cleanup = asyncio.create_task(
        memory_service.cleanup_loop(),
        name="memory-cleanup",
    )
    eval_worker = asyncio.create_task(
        eval_service.worker_loop(),
        name="eval-worker",
    )

    try:
        yield
    finally:
        await execution_service.stop()
        await knowledge_service.stop()
        await memory_service.stop()
        await eval_service.stop()
        for task in (
            worker,
            outbox,
            knowledge_worker,
            knowledge_cleanup,
            memory_cleanup,
            eval_worker,
        ):
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
app.include_router(create_admin_router(database, nats_adapter, settings))
app.include_router(create_catalog_router(catalog_service))
app.include_router(create_governance_router(governance_service))
app.include_router(create_eval_router(eval_service))
app.include_router(create_prompt_router(prompt_service))
app.include_router(create_knowledge_router(knowledge_service))
app.include_router(create_memory_router(memory_service))
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
