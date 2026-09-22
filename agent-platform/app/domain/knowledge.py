from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class KnowledgeBase:
    id: UUID
    name: str
    description: str
    scope: str = "TENANT"
    retention_policy: str = "PERSISTENT"
    expires_at: datetime | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeDocument:
    id: UUID
    knowledge_base_id: UUID
    name: str
    source_type: str
    source_id: str | None = None
    source_uri: str | None = None
    mime_type: str | None = None
    status: str = "PENDING"
    version: int = 1
    checksum: str | None = None
    storage_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class ParsedSegment:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    segments: list[ParsedSegment]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    ordinal: int
    content: str
    token_estimate: int
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    document_name: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
