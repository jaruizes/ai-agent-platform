from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


EVAL_METRICS = {
    "relevance",
    "completeness",
    "groundedness",
    "coherence",
    "instruction_adherence",
}
RUN_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED"}


@dataclass(frozen=True)
class EvalDatasetItem:
    name: str
    command: dict[str, Any]
    expected_output: str | None = None
    assertions: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class EvalDataset:
    name: str
    description: str = ""
    version: int = 1
    enabled: bool = True
    items: list[EvalDatasetItem] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class EvalDefinition:
    name: str
    dataset_id: UUID
    description: str = ""
    metrics: list[str] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)
    judge_model_profile: str | None = None
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)
