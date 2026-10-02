from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


ARTIFACT_TYPES = {
    "HUMAN_DOCUMENT",
    "MACHINE_DATA",
    "AGENT_HANDOFF",
    "EVIDENCE_SET",
    "FINAL_DELIVERABLE",
}


@dataclass(frozen=True)
class Artifact:
    id: UUID
    execution_id: UUID
    step_id: str
    scope_key: str
    artifact_type: str
    schema_name: str
    version: int
    title: str
    media_type: str
    summary: str
    content: Any
    checksum: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def ref(self) -> dict[str, Any]:
        return {
            "artifactId": str(self.id),
            "uri": f"artifact://{self.id}",
            "type": self.artifact_type,
            "schema": self.schema_name,
            "version": self.version,
            "title": self.title,
            "mediaType": self.media_type,
            "summary": self.summary,
            "sizeBytes": self.size_bytes,
        }
