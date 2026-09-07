"""Phase 2B project connector (docs/DECISIONS.md ADR-010): clone into an
isolated mission workspace, branch isolation, main/master protection, and
foreign-remote blocking -- against a disposable local "fake external repo"
standing in for a real project like HufManager. No network required; the
real read-only clone of passaondigital/hufmanager is a separate, manual,
documented verification step (docs/CONNECTOR-HUFMANAGER.md), matching this
project's zero-network-dependency test convention (.github/workflows/ci.yml)."""

import subprocess

import pytest

from hufiagents.contracts import Risk, ToolCall
from hufiagents.projects import Project
from hufiagents.tools.git import GitTool
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


def make_fake_external_repo(tmp_path, *, branch="main"):
    """A disposable local "remote" -- stands in for a real project's repo
    (e.g. HufManager) so clone/push tests need no network."""
    repo = tmp_path / "external-repo.git-src"
    subprocess.run(
        ["/usr/bin/git", "init", "-q", f"--initial-branch={branch}", str(repo)], check=True
    )
    (repo / "README.md").write_text("hello from the fake project\n")
    subprocess.run(["/usr/bin/git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["/usr/bin/git", "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
    )
    bare = tmp_path / "external-repo.git"
    subprocess.run(["/usr/bin/git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    return bare


def demo_project(bare, **overrides):
    fields = {
        "id": "demo",
        "repo_url": str(bare),
        "github_repo": "org/demo",
        "default_branch": "main",
        "allowed": True,
        **overrides,
    }
    return Project(**fields)


async def test_clone_pulls_the_registered_project_only_never_a_caller_supplied_url(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare))
    result = await tool.execute(
        call("git", "clone", repo_url="https://evil.example/definitely-not-this.git")
    )
    assert result.exit_code == 0
    assert (workspace.root / "README.md").read_text() == "hello from the fake project\n"
    origin = subprocess.run(
        ["/usr/bin/git", "remote", "get-url", "origin"],
        cwd=workspace.root,
        capture_output=True,
        text=True,
    )
    assert origin.stdout.strip() == str(bare)


async def test_clone_without_a_project_is_refused(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace)
    with pytest.raises(PermissionError, match="no project configured"):
        await tool.execute(call("git", "clone"))


async def test_branch_isolation_a_new_hufi_branch_is_required_for_changes(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare))
    await tool.execute(call("git", "clone"))
    # Still on the cloned default branch: main/master protection blocks add/commit.
    workspace.create("note.md", "changed")
    with pytest.raises(PermissionError, match="hufi/ branch"):
        await tool.execute(call("git", "add", path="note.md"))
    # Creating an isolated hufi/ branch is required before any change lands.
    await tool.execute(call("git", "branch", branch="hufi/mission-42"))
    result = await tool.execute(call("git", "add", path="note.md"))
    assert result.exit_code == 0
    result = await tool.execute(call("git", "commit", message="add note"))
    assert result.exit_code == 0


async def test_default_branch_name_other_than_main_is_also_protected(tmp_path):
    bare = make_fake_external_repo(tmp_path, branch="trunk")
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare, default_branch="trunk"))
    await tool.execute(call("git", "clone"))
    workspace.create("note.md", "changed")
    with pytest.raises(PermissionError, match="hufi/ branch"):
        await tool.execute(call("git", "add", path="note.md"))


async def test_foreign_remote_is_blocked_even_if_origin_is_tampered_with(tmp_path):
    """Even if something outside the tool's own control changes `origin`
    (e.g. a bug elsewhere, or a future code path), push must still refuse to
    send data anywhere but the registered project's repo_url."""
    bare = make_fake_external_repo(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare))
    await tool.execute(call("git", "clone"))
    await tool.execute(call("git", "branch", branch="hufi/mission-1"))
    workspace.create("note.md", "changed")
    await tool.execute(call("git", "add", path="note.md"))
    await tool.execute(call("git", "commit", message="add note"))
    subprocess.run(
        ["/usr/bin/git", "remote", "set-url", "origin", "https://evil.example/other.git"],
        cwd=workspace.root,
        check=True,
    )
    with pytest.raises(PermissionError, match="does not match"):
        await tool.execute(call("git", "push"))


async def test_remote_add_is_rejected_for_a_project_task(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare))
    await tool.execute(call("git", "clone"))
    with pytest.raises(PermissionError, match="set automatically by clone"):
        await tool.execute(call("git", "remote_add"))


async def test_dry_run_push_does_not_reach_the_remote(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    tool = GitTool(workspace, project=demo_project(bare), dry_run=True)
    await tool.execute(call("git", "clone"))
    await tool.execute(call("git", "branch", branch="hufi/mission-1"))
    workspace.create("note.md", "changed")
    await tool.execute(call("git", "add", path="note.md"))
    await tool.execute(call("git", "commit", message="add note"))
    result = await tool.execute(call("git", "push"))
    assert result.result_status == "ok"
    assert "dry-run" in result.result_summary
    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "branch", "--list", "hufi/mission-1"],
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip() == ""  # nothing was actually pushed
