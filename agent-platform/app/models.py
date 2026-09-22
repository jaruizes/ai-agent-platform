from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Command(BaseModel):
    name: str | None = None
    intent: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    instructions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestExecutionRequest(BaseModel):
    correlationId: str | None = None
    command: Command


class RestExecutionAccepted(BaseModel):
    executionId: UUID
    correlationId: str
    status: Literal["ACCEPTED"] = "ACCEPTED"


class MessageSource(BaseModel):
    type: str
    name: str
    instance: str | None = None


class NatsExecutionData(BaseModel):
    executionId: UUID | None = None
    command: Command


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


class ExecutionPlan(BaseModel):
    strategy: Literal["DIRECT_LLM"] = "DIRECT_LLM"
    system_prompt: str
    user_prompt: str
