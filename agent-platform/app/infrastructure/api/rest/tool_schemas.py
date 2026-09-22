from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    implementationType: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ToolResponse(ToolRequest):
    id: UUID
    source: str


class McpServerRequest(BaseModel):
    name: str
    description: str = ""
    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class McpServerResponse(McpServerRequest):
    id: UUID
    source: str
