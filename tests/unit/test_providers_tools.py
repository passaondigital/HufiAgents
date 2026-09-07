import json
from pathlib import Path

import httpx
import pytest

from hufiagents.contracts import Agent, Risk, Task, ToolCall
from hufiagents.providers.base import CompletionRequest, ProviderHealth
from hufiagents.providers.fake import FakeProvider
from hufiagents.providers.hufi_local_router import HufiLocalRouter
from hufiagents.providers.ollama import OllamaProvider
from hufiagents.providers.router import select_provider
from hufiagents.risk import Policy
from hufiagents.tools.files import FilesTool
from hufiagents.tools.git import GitTool
from hufiagents.tools.shell import ShellTool
from hufiagents.tools.workspace import Workspace


def call(tool, action, target="result.md", **params):
    return ToolCall(
        task_id="test",
        tool=tool,
        action=action,
        target=target,
        params=params,
        risk_class=Risk.R1,
        policy_decision="auto_allow",
        idempotency_key="test",
    )


async def test_fake_and_http_adapters():
    request = CompletionRequest(objective="hello")
    fake = FakeProvider()
    assert await fake.complete(request) == await fake.complete(request)

    def handler(req):
        if req.url.path == "/router/status":
            return httpx.Response(200, json={"status": "ok"})
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})
        body = json.loads(req.content)
        assert body["stream"] is False
        if req.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": "ollama answer"}})
        assert req.extensions["timeout"]["read"] == 180
        return httpx.Response(200, json={"choices": [{"message": {"content": "router answer"}}]})

    transport = httpx.MockTransport(handler)
    for provider in [
        HufiLocalRouter("http://model/v1", transport=transport),
        OllamaProvider("http://model", transport=transport),
    ]:
        assert (await provider.health()).available
        assert (await provider.complete(request)).text.endswith("answer")


def test_provider_no_silent_fallback():
    task = Task(mission_id="test", objective="test")
    agent = Agent(id="builder", role="test", capabilities={"providers": ["fake"]})
    health = {"fake": ProviderHealth(available=True)}
    assert select_provider(task, agent, health, "fake").provider_id == "fake"
    with pytest.raises(PermissionError):
        select_provider(task, agent, health)
    with pytest.raises(ConnectionError):
        select_provider(task, agent, {}, "fake")


@pytest.mark.parametrize("target", ["../escape", "/etc/passwd", ".git/config", ".env", ".env.prod"])
async def test_workspace_escape(tmp_path, target):
    tool = FilesTool(Workspace(tmp_path / "workspace"))
    with pytest.raises(PermissionError):
        await tool.classify("write_file", {"target": target})


async def test_files_no_overwrite_symlink_or_hardlink(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = FilesTool(workspace)
    await tool.execute(call("files", "write_file", content="first"))
    await tool.execute(call("files", "write_file", content="first"))
    with pytest.raises(FileExistsError):
        await tool.execute(call("files", "write_file", content="second"))
    outside = tmp_path / "outside"
    outside.write_text("protected")
    (workspace.root / "link").symlink_to(outside)
    (workspace.root / "hard").hardlink_to(outside)
    for target in ["link", "hard"]:
        with pytest.raises(PermissionError):
            workspace.read(target)
    assert outside.read_text() == "protected"


async def test_shell_rejects_arbitrary_code(tmp_path):
    tool = ShellTool(Workspace(tmp_path))
    assert await tool.classify("run_command", {"command": "rm -rf /"}) == Risk.R4
    assert await tool.classify("run_command", {"command": "python -c evil"}) == Risk.R3
    with pytest.raises(PermissionError):
        await tool.execute(call("shell", "run_command", command="sh -c touch /tmp/escape"))
    result = await tool.execute(call("shell", "run_command", command="pwd"))
    assert result.exit_code == 0
    assert str(tmp_path) in result.result_summary


async def test_git_workspace_flow(tmp_path):
    workspace = Workspace(tmp_path)
    tool = GitTool(workspace)
    for action, params in [("init", {}), ("branch", {"branch": "hufi/test"})]:
        assert (await tool.execute(call("git", action, **params))).exit_code == 0
    workspace.create("result.md", "test")
    assert (await tool.execute(call("git", "add", path="result.md"))).exit_code == 0
    assert (await tool.execute(call("git", "commit"))).exit_code == 0
    assert (await tool.execute(call("git", "status"))).result_summary == ""
    with pytest.raises(PermissionError):
        await tool.execute(call("git", "force_push"))


@pytest.mark.parametrize(
    "risk,decision",
    [
        (Risk.R0, "auto_allow"),
        (Risk.R1, "auto_allow"),
        (Risk.R2, "reviewer_gate"),
        (Risk.R3, "approval_required"),
        (Risk.R4, "approval_required"),
    ],
)
def test_risk_table(risk, decision):
    policy = Policy(Path("/nonexistent"))
    task = Task(mission_id="test", objective="test", risk_ceiling=Risk.R4)
    agent = Agent(
        id="test", role="test", capabilities={"tools": ["files"]}, default_risk_ceiling=Risk.R4
    )
    assert policy.decide(risk, task, agent, "files", "write_file") == decision
    agent.default_risk_ceiling = Risk.R0
    if risk > Risk.R0:
        assert policy.decide(risk, task, agent, "files", "write_file") == "denied"
