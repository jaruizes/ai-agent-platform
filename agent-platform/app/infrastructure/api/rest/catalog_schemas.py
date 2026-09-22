from uuid import UUID

from pydantic import BaseModel, Field


class SkillRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str
    enabled: bool = True


class SkillResponse(SkillRequest):
    id: UUID
    source: str


class AgentRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str
    skills: list[str] = Field(default_factory=list)
    enabled: bool = True


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    instructions: str
    enabled: bool
    source: str
    skills: list[SkillResponse]
