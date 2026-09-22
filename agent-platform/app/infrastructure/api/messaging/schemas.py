from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MessageSource(BaseModel):
    type: str
    name: str
    instance: str | None = None


class CommandMessage(BaseModel):
    name: str | None = None
    intent: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    instructions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NatsExecutionData(BaseModel):
    executionId: UUID | None = None
    sessionId: UUID | None = None
    command: CommandMessage


class NatsExecutionWrapper(BaseModel):
    execution: NatsExecutionData


class ExecutionCommandEnvelope(BaseModel):
    specVersion: str = "1.0"
    messageId: str
    messageType: Literal["execution.command"]
    timestamp: datetime
    correlationId: str
    causationId: str | None = None
    source: MessageSource
    tenantId: str | None = None
    data: NatsExecutionWrapper
