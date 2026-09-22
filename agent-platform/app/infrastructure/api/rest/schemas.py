from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    name: str | None = None
    intent: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    instructions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestExecutionRequest(BaseModel):
    correlationId: str | None = None
    command: CommandRequest


class RestExecutionAccepted(BaseModel):
    executionId: UUID
    correlationId: str
    status: Literal["ACCEPTED"] = "ACCEPTED"



class ExecutionControlRequest(BaseModel):
    reason: str | None = None


class StepApprovalRequest(BaseModel):
    approved: bool
    actor: str = Field(min_length=1)
    comment: str | None = None
