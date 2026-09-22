from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeBaseRequest(BaseModel):
    name: str
    description: str = ""
    scope: str = "TENANT"
    retentionPolicy: str = "PERSISTENT"
    ttlSeconds: int | None = None
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    description: str
    scope: str
    retentionPolicy: str
    expiresAt: datetime | None
    enabled: bool
    metadata: dict[str, Any]


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    knowledgeBaseId: UUID
    name: str
    sourceType: str
    sourceId: str | None
    sourceUri: str | None
    mimeType: str | None
    status: str
    version: int
    checksum: str | None
    metadata: dict[str, Any]
    error: dict[str, Any] | None


class GoogleDocumentRequest(BaseModel):
    sourceType: str
    sourceId: str
    name: str | None = None
    sourceUri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str
    knowledgeBases: list[str]
    topK: int = Field(default=8, ge=1, le=50)


class RetrievalHitResponse(BaseModel):
    chunkId: UUID
    documentId: UUID
    knowledgeBaseId: UUID
    documentName: str
    content: str
    score: float
    metadata: dict[str, Any]


class AgentKnowledgeAssignment(BaseModel):
    name: str
    usageMode: str = "REFERENCE"


class AgentKnowledgeAssignmentsRequest(BaseModel):
    knowledgeBases: list[AgentKnowledgeAssignment] = Field(default_factory=list)
