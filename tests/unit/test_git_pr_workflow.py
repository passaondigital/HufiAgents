"""Phase 2: real `git push` + a scoped draft-PR tool, gated behind the new
`integrator` agent (R2 ceiling) so the shipped `builder` agent's existing R1
boundary is unchanged. Remote/repo/token are always server-configured, never
caller-supplied, so a task can never redirect a push/PR to another
destination -- these tests assert that guarantee directly, not just the
happy path."""

import subprocess
from pathlib import Path

import pytest

from hufiagents.contracts import Agent, Risk, Task, ToolCall
from hufiagents.risk import Policy
from hufiagents.tools.git import GitTool
from hufiagents.tools.github import GitHubTool
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


def make_bare_remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["/usr/bin/git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


async def init_committed_repo(tool, workspace):
    await tool.execute(call("git", "init"))
    workspace.create("note.md", "hello")
    await tool.execute(call("git", "add", path="note.md"))
    await tool.execute(call("git", "commit"))


async def test_push_without_configured_remote_is_refused(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace)  # remote_url defaults to "" (disabled)
    await init_committed_repo(tool, workspace)
    with pytest.raises(PermissionError, match="no git remote configured"):
        await tool.execute(call("git", "push"))


async def test_remote_add_ignores_caller_supplied_url(tmp_path):
    bare = make_bare_remote(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, remote_url=str(bare))
    await tool.execute(call("git", "init"))
    # A task/agent-supplied "url" param must never reach the actual `git
    # remote add` invocation -- only the server-configured remote_url may.
    result = await tool.execute(call("git", "remote_add", url="https://evil.example/x.git"))
    assert result.exit_code == 0
    status = subprocess.run(
        ["/usr/bin/git", "remote", "get-url", "origin"],
        cwd=workspace.root,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == str(bare)


async def test_push_to_configured_remote_succeeds_and_is_verifiable(tmp_path):
    bare = make_bare_remote(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, remote_url=str(bare), push_token="test-token")
    await init_committed_repo(tool, workspace)
    await tool.execute(call("git", "remote_add"))
    result = await tool.execute(call("git", "push"))
    assert result.exit_code == 0
    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission"],
        capture_output=True,
        text=True,
    )
    assert "hello" not in log.stdout  # sanity: log lists commits, not file contents
    assert log.returncode == 0 and log.stdout.strip() != ""


async def test_push_refuses_a_non_hufi_or_detached_branch(tmp_path):
    bare = make_bare_remote(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, remote_url=str(bare))
    await init_committed_repo(tool, workspace)
    await tool.execute(call("git", "remote_add"))
    # Move off the hufi/ branch the tool created, bypassing the tool itself --
    # simulates any state where HEAD is not a hufi/ branch.
    subprocess.run(["/usr/bin/git", "checkout", "-b", "not-hufi"], cwd=workspace.root, check=True)
    with pytest.raises(PermissionError, match="non-hufi"):
        await tool.execute(call("git", "push"))


async def test_github_tool_refuses_when_not_configured(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitHubTool(workspace)
    with pytest.raises(PermissionError, match="not configured"):
        await tool.execute(call("github", "open_pr"))


async def test_github_tool_refuses_non_hufi_branch(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitHubTool(workspace, repo="owner/repo", token="x")
    git = GitTool(workspace)
    await init_committed_repo(git, workspace)
    subprocess.run(["/usr/bin/git", "checkout", "-b", "not-hufi"], cwd=workspace.root, check=True)
    with pytest.raises(PermissionError, match="non-hufi"):
        await tool.execute(call("github", "open_pr"))


async def test_github_tool_only_implements_open_pr(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitHubTool(workspace, repo="owner/repo", token="x")
    assert await tool.classify("merge", {}) == Risk.R3
    assert await tool.classify("open_pr", {}) == Risk.R2
    with pytest.raises(PermissionError, match="only draft PR creation"):
        await tool.execute(call("github", "merge"))


async def test_github_tool_builds_bounded_argv_and_scoped_env(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "workspace")
    git = GitTool(workspace)
    await init_committed_repo(git, workspace)
    tool = GitHubTool(
        workspace, repo="passaondigital/HufiAgents", base_branch="main", token="secret-pat"
    )

    calls = []

    async def fake_run_process(argv, ws, call_, timeout, extra_env=None):
        calls.append((argv, extra_env))
        if argv[:2] == ["/usr/bin/git", "symbolic-ref"]:
            return await real_run_process(argv, ws, call_, timeout, extra_env)
        return call_.model_copy(
            update={"result_status": "ok", "exit_code": 0, "result_summary": "https://pr/1"}
        )

    from hufiagents.tools import github as github_module

    real_run_process = github_module.run_process
    monkeypatch.setattr(github_module, "run_process", fake_run_process)

    result = await tool.execute(
        call("github", "open_pr", title="Add feature", body="Draft, review required.")
    )
    assert result.result_status == "ok"
    pr_call = next(c for c in calls if c[0][:3] == ["/usr/bin/gh", "pr", "create"])
    argv, extra_env = pr_call
    assert "--repo" in argv and "passaondigital/HufiAgents" in argv
    assert "--base" in argv and "main" in argv
    assert "--head" in argv and "hufi/mission" in argv
    assert "--draft" in argv
    assert extra_env["GH_TOKEN"] == "secret-pat"
    assert extra_env["GH_HOST"] == "github.com"
    assert not Path(extra_env["GH_CONFIG_DIR"]).is_relative_to(workspace.root)
    assert not Path(extra_env["GH_CONFIG_DIR"]).exists()
    # The token must never leak into the persisted params/audit trail.
    assert "secret-pat" not in str(argv)


async def test_r2_auto_allow_requires_the_r2_capable_agent(tmp_path):
    import yaml

    policy_path = tmp_path / "risk_policy.yaml"
    policy_path.write_text(yaml.dump({"r2_auto_allow": ["git.push", "github.open_pr"]}))
    policy = Policy(policy_path)
    task = Task(mission_id="m", objective="o", risk_ceiling=Risk.R2, allowed_tools=["git"])

    integrator = Agent(
        id="integrator",
        role="test",
        capabilities={"tools": ["git"]},
        default_risk_ceiling=Risk.R2,
    )
    assert policy.decide(Risk.R2, task, integrator, "git", "push") == "auto_allow"

    builder = Agent(
        id="builder", role="test", capabilities={"tools": ["git"]}, default_risk_ceiling=Risk.R1
    )
    assert policy.decide(Risk.R2, task, builder, "git", "push") == "denied"
