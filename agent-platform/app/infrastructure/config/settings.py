from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "agent-platform"
    service_version: str = "0.1.0"

    database_url: str = "postgresql://agent:agent@postgres:5432/agent_platform"

    nats_url: str = "nats://nats:4222"
    nats_command_subject: str = "platform.commands.execution"
    nats_command_stream: str = "PLATFORM_COMMANDS"
    nats_event_stream: str = "PLATFORM_EVENTS"
    nats_command_consumer: str = "agent-platform-command-consumer"

    litellm_base_url: str = "http://litellm:4000"
    litellm_master_key: str = "sk-local-dev-key"
    default_model: str = "platform-default"
    model_timeout_seconds: float = 120.0

    worker_poll_seconds: float = 0.5
    outbox_poll_seconds: float = 0.25

    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
