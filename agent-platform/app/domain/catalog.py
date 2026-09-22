from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Skill:
    id: UUID
    name: str
    description: str
    instructions: str
    enabled: bool = True
    source: str = "USER"


@dataclass(frozen=True)
class Agent:
    id: UUID
    name: str
    description: str
    instructions: str
    skills: list[Skill] = field(default_factory=list)
    enabled: bool = True
    source: str = "USER"
