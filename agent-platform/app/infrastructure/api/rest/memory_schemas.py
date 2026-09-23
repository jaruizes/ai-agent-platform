from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    name: str | None = None
    scope: str = "TENANT"
    ownerKey: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    expiresAt: datetime | None = None


class MemoryRequest(BaseModel):
    scopeType: str
    scopeId: str
    memoryType: str
    key: str | None = None
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0, le=1)
    expiresAt: datetime | None = None
    sourceExecutionId: UUID | None = None
    sourceStepId: str | None = None


class MemoryCandidateRequest(MemoryRequest):
    confidence: float = Field(default=0.0, ge=0, le=1)
    explicit: bool = False


class MemoryScopeRequest(BaseModel):
    scopeType: str
    scopeId: str


class MemoryRetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    scopes: list[MemoryScopeRequest] = Field(default_factory=list)
    topK: int = Field(default=8, ge=1, le=50)
