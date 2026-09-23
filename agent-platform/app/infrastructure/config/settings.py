from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "agent-platform"
    service_version: str = "0.9.0-alpha.2"

    database_url: str = "postgresql://agent:agent@postgres:5432/agent_platform"

    nats_url: str = "nats://nats:4222"
    nats_command_subject: str = "platform.commands.execution"
    nats_command_stream: str = "PLATFORM_COMMANDS"
    nats_event_stream: str = "PLATFORM_EVENTS"
    nats_command_consumer: str = "agent-platform-command-consumer"

    litellm_base_url: str = "http://litellm:4000"
    litellm_master_key: str = "sk-local-dev-key"
    router_model_profile: str = "router-fast"
    execution_model_profile: str = "reasoning-default"
    planner_model_profile: str = "planner-default"
    model_timeout_seconds: float = 120.0

    worker_poll_seconds: float = 0.5
    outbox_poll_seconds: float = 0.25
    orchestration_max_steps: int = 12
    execution_lease_seconds: int = 30
    execution_heartbeat_seconds: float = 10.0
    execution_control_poll_seconds: float = 0.5

    bootstrap_skills_dir: str = "/app/bootstrap/skills"
    bootstrap_agents_dir: str = "/app/bootstrap/agents"
    bootstrap_prompts_dir: str = "/app/bootstrap/prompts"
    bootstrap_tools_dir: str = "/app/bootstrap/tools"
    bootstrap_mcp_servers_dir: str = "/app/bootstrap/mcp-servers"
    mcp_timeout_seconds: float = 60.0
    mcp_max_message_bytes: int = 16777216
    max_tool_result_chars_for_model: int = 500000

    knowledge_embedding_provider: str = "hash"
    knowledge_embedding_model: str = "hash-embedding-v1"
    knowledge_embedding_dimensions: int = 768
    knowledge_storage_root: str = "/data/knowledge"
    knowledge_embedding_batch_size: int = 32
    knowledge_worker_poll_seconds: float = 0.5
    knowledge_cleanup_poll_seconds: float = 60.0
    knowledge_top_k: int = 8

    memory_allow_inferred_persistence: bool = True
    memory_min_inferred_confidence: float = 0.80
    memory_max_content_chars: int = 8000
    memory_cleanup_poll_seconds: float = 60.0
    memory_auto_extract_session: bool = True
    memory_extractor_model_profile: str = "router-fast"
    memory_extractor_max_candidates: int = 8
    memory_extractor_max_input_chars: int = 50000

    context_model_window_tokens: int = 200000
    context_reserved_output_tokens: int = 16000
    context_safety_margin_tokens: int = 10000
    context_session_max_entries: int = 24
    context_memory_top_k: int = 8
    context_memory_min_score: float = 0.12
    context_min_compression_tokens: int = 128

    governance_default_projected_completion_tokens: int = 4096
    governance_prompt_estimate_multiplier: float = 1.25
    governance_router_input_usd_per_million: float = 0.0
    governance_router_output_usd_per_million: float = 0.0
    governance_execution_input_usd_per_million: float = 0.0
    governance_execution_output_usd_per_million: float = 0.0
    governance_planner_input_usd_per_million: float = 0.0
    governance_planner_output_usd_per_million: float = 0.0

    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
