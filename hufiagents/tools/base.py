from typing import Protocol

from hufiagents.contracts import Risk, ToolCall, ToolResult


class Tool(Protocol):
    id: str

    async def classify(self, action: str, params: dict) -> Risk: ...
    async def execute(self, call: ToolCall) -> ToolResult: ...
