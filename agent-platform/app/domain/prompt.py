from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Prompt:
    id: UUID
    name: str
    description: str
    content: str
    version: int = 1
    enabled: bool = True
    source: str = "USER"
