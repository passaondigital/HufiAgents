from typing import Protocol

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    objective: str
    context: str = ""
    max_tokens: int = Field(512, ge=1, le=8192)


class CompletionResult(BaseModel):
    text: str = Field(min_length=1, max_length=64000)
    model: str
    tokens: int = 0


class ProviderHealth(BaseModel):
    available: bool
    reason: str = ""


class ModelProvider(Protocol):
    id: str

    async def complete(self, request: CompletionRequest) -> CompletionResult: ...
    async def health(self) -> ProviderHealth: ...
