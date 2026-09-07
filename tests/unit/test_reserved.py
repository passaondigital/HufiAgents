"""ReservedTool (SSH/browser/MCP placeholders, architecture §6.5-6.7) is not yet
wired into Orchestrator.tools(), so nothing currently reaches it. It must stay a
hard-closed stub so wiring it in later cannot accidentally grant execution."""

import pytest

from hufiagents.contracts import Risk
from hufiagents.tools.reserved import ReservedTool


async def test_reserved_tool_classifies_r3_and_never_executes():
    tool = ReservedTool("ssh")
    assert await tool.classify("run", {}) == Risk.R3
    with pytest.raises(NotImplementedError):
        await tool.execute(None)
