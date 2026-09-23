from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvalDatasetItemRequest(BaseModel):
    name: str
    command: dict[str, Any]
    expectedOutput: str | None = None
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EvalDatasetRequest(BaseModel):
    name: str
    description: str = ""
    version: int = Field(default=1, ge=1)
    enabled: bool = True
    items: list[EvalDatasetItemRequest] = Field(default_factory=list)


class EvalDefinitionRequest(BaseModel):
    name: str
    description: str = ""
    datasetId: UUID
    metrics: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    judgeModelProfile: str | None = None
    enabled: bool = True


class EvalRunRequest(BaseModel):
    baselineRunId: UUID | None = None
