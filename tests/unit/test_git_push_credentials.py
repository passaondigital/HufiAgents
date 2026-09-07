"""GitTool.push's real HTTPS credential path (docs/DECISIONS.md ADR-011):
a static, secret-free GIT_ASKPASS helper, HUFI_GITHUB_TOKEN only reaching one
subprocess's env. Uses a real local basic-auth-enforcing git-smart-HTTP
server (tests/support/git_http_server.py, wraps the real `git http-backend`)
so "correct token pushes for real" and "wrong token fails without leaking
it" are proven against real HTTP auth, not simulated. `builder` remaining
blocked is already covered by
tests/integration/test_git_pr_workflow_e2e.py::test_builder_agent_cannot_push_even_with_remote_configured
(ceiling denial happens before GitTool.execute is ever reached, so it does
not need the credential machinery this file focuses on); foreign-remote
blocking is already covered by
tests/unit/test_git_connector.py::test_foreign_remote_is_blocked_even_if_origin_is_tampered_with."""

import os
import subprocess

import pytest

from hufiagents.contracts import Risk, ToolCall
from hufiagents.tools.git import ASKPASS_SCRIPT, GitTool
from hufiagents.tools.workspace import Workspace
from tests.support.git_http_server import basic_auth_git_server, make_bare_http_repo

TOKEN = "s3cr3t-push-token-do-not-leak"
WRONG_TOKEN = "totally-wrong-token"
USERNAME = "x-access-token"


def call(action, target="workspace", **params):
    return ToolCall(
        task_id="test",
        tool="git",
        action=action,
        target=target,
        params=params,
        risk_class=Risk.R1,
        policy_decision="auto_allow",
        idempotency_key="test",
    )


async def committed_workspace(tmp_path, remote_url, *, push_token=""):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, remote_url=remote_url, push_token=push_token)
    await tool.execute(call("init"))
    workspace.create("note.md", "hello")
    await tool.execute(call("add", path="note.md"))
    await tool.execute(call("commit", message="add note"))
    await tool.execute(call("remote_add"))
    return workspace, tool


async def test_missing_token_blocks_push_before_any_subprocess(tmp_path, monkeypatch):
    bare = tmp_path / "remote.git"
    subprocess.run(["/usr/bin/git", "init", "--bare", "-q", str(bare)], check=True)
    workspace, tool = await committed_workspace(tmp_path, str(bare), push_token="")

    spawned = []
    real_exec = __import__("asyncio").create_subprocess_exec

    async def spy(*args, **kwargs):
        spawned.append(args)
        return await real_exec(*args, **kwargs)

    monkeypatch.setattr("asyncio.create_subprocess_exec", spy)
    with pytest.raises(PermissionError, match="no push credential configured"):
        await tool.execute(call("push"))
    assert not any(a[:1] == ("/usr/bin/git",) and "push" in a for a in spawned)


async def test_wrong_token_fails_without_leaking_it(tmp_path):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        workspace, tool = await committed_workspace(tmp_path, remote, push_token=WRONG_TOKEN)
        result = await tool.execute(call("push"))
    assert result.result_status == "error"
    assert TOKEN not in result.result_summary
    assert WRONG_TOKEN not in result.result_summary
    assert "Authentication failed" in result.result_summary


async def test_correct_token_pushes_for_real_through_git_askpass(tmp_path):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    bare = make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        workspace, tool = await committed_workspace(tmp_path, remote, push_token=TOKEN)
        result = await tool.execute(call("push"))
    assert result.result_status == "ok" and result.exit_code == 0
    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission"],
        capture_output=True,
        text=True,
    )
    assert log.returncode == 0 and log.stdout.strip() != ""


async def test_token_never_appears_in_argv_config_or_remote_url(tmp_path, monkeypatch):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    make_bare_http_repo(project_root)
    captured_argv = []
    real_exec = __import__("asyncio").create_subprocess_exec

    async def spy(*args, **kwargs):
        captured_argv.append(args)
        return await real_exec(*args, **kwargs)

    monkeypatch.setattr("asyncio.create_subprocess_exec", spy)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        workspace, tool = await committed_workspace(tmp_path, remote, push_token=TOKEN)
        await tool.execute(call("push"))

    flat_argv = str(captured_argv)
    assert TOKEN not in flat_argv
    remote_check = subprocess.run(
        ["/usr/bin/git", "remote", "get-url", "origin"],
        cwd=workspace.root,
        capture_output=True,
        text=True,
    )
    assert TOKEN not in remote_check.stdout
    config_text = (workspace.root / ".git" / "config").read_text()
    assert TOKEN not in config_text
    assert "credential" not in config_text.lower()


async def test_no_credential_file_or_helper_left_behind_after_push(tmp_path):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        workspace, tool = await committed_workspace(tmp_path, remote, push_token=TOKEN)
        await tool.execute(call("push"))
    # The askpass helper is the one, static, checked-in, secret-free file --
    # nothing ephemeral was ever written for this specific push.
    assert ASKPASS_SCRIPT.exists()
    assert os.access(ASKPASS_SCRIPT, os.X_OK)
    assert TOKEN not in ASKPASS_SCRIPT.read_text()
    for path in workspace.root.rglob("*"):
        if path.is_file():
            assert TOKEN not in path.read_text(errors="ignore")


async def test_dry_run_push_needs_no_token_at_all(tmp_path):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        workspace = Workspace(tmp_path / "workspace")
        tool = GitTool(workspace, remote_url=remote, push_token="", dry_run=True)
        await tool.execute(call("init"))
        workspace.create("note.md", "hello")
        await tool.execute(call("add", path="note.md"))
        await tool.execute(call("commit", message="add note"))
        await tool.execute(call("remote_add"))
        result = await tool.execute(call("push"))
    assert result.result_status == "ok"
    assert "dry-run" in result.result_summary
