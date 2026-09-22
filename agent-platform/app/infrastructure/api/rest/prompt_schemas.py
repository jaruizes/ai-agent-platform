from uuid import UUID

from pydantic import BaseModel


class PromptRequest(BaseModel):
    name: str
    description: str = ""
    content: str
    version: int = 1
    enabled: bool = True


class PromptResponse(PromptRequest):
    id: UUID
    source: str
