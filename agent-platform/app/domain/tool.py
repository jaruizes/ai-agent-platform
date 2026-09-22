from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Tool:
    id: UUID
    name: str
    description: str
    instructions: str
    implementation_type: str
    configuration: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    source: str = "USER"


@dataclass(frozen=True)
class McpServer:
    id: UUID
    name: str
    description: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    environment: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    source: str = "USER"
