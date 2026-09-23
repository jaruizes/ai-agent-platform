from typing import Any

from pydantic import BaseModel, Field


class PolicyRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    policyType: str
    effect: str
    resourceType: str
    resourcePattern: str = "*"
    subjectType: str = "GLOBAL"
    subjectPattern: str = "*"
    conditions: dict[str,Any] = Field(default_factory=dict)
    priority: int = 100
    enabled: bool = True


class BudgetRequest(BaseModel):
    name: str = Field(min_length=1)
    scopeType: str
    scopeId: str
    period: str = "EXECUTION"
    maxPromptTokens: int | None = Field(default=None,ge=1)
    maxCompletionTokens: int | None = Field(default=None,ge=1)
    maxTotalTokens: int | None = Field(default=None,ge=1)
    maxCostUsd: float | None = Field(default=None,gt=0)
    action: str = "DENY"
    degradeModelProfile: str | None = None
    enabled: bool = True
