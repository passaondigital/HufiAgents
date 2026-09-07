"""End-to-end proof that the `integrator` agent (R2 ceiling) can push a real
commit through the full Mission -> Task -> Gateway -> Tool pipeline against a
configured remote, while the shipped `builder` agent's R1 ceiling still
blocks the same operations -- exercised through the real Orchestrator/DB, not
just the tool in isolation (see tests/unit/test_git_pr_workflow.py for that)."""

import asyncio
import subprocess

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider


def make_bare_remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["/usr/bin/git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


def setup(tmp_path, **kwargs):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/db.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
        heartbeat_timeout_seconds=0.1,
        heartbeat_interval_seconds=0.02,
        **kwargs,
    )
    store = Store(settings.database_url)
    return store, Orchestrator(store, settings, {"fake": FakeProvider()})


async def settle(engine, mission_id):
    for _ in range(100):
        await engine.tick()
        if engine.active:
            await asyncio.gather(*engine.active.values())
        with engine.store.transaction() as tx:
            mission = tx.missions.get(mission_id)
            if mission.status in {
                State.completed,
                State.failed,
                State.cancelled,
                State.waiting_approval,
            }:
                return mission
    raise AssertionError("mission did not settle")


async def test_integrator_agent_pushes_a_real_commit_end_to_end(tmp_path):
    bare = make_bare_remote(tmp_path)
    store, engine = setup(tmp_path, git_remote_url=str(bare), github_token="test-token")
    mission = engine.submit(
        MissionCreate(
            outcome="ship it",
            risk_ceiling="R2",
            steps=[
                TaskSpec(
                    objective="push a note",
                    agent_id="integrator",
                    allowed_tools=["files", "git"],
                    operations=[
                        {"tool": "git", "action": "init"},
                        {
                            "tool": "files",
                            "action": "write_file",
                            "target": "note.md",
                            "params": {"content": "hello from HufiAgents"},
                        },
                        {"tool": "git", "action": "add", "params": {"path": "note.md"}},
                        {"tool": "git", "action": "commit", "params": {"message": "add note"}},
                        {"tool": "git", "action": "remote_add"},
                        {"tool": "git", "action": "push"},
                    ],
                )
            ],
        )
    )
    settled = await settle(engine, mission.id)
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        calls = tx.tool_calls.list(task_id=task.id)
    assert settled.status == State.completed, [c.model_dump() for c in calls]
    assert task.assigned_agent_id == "integrator"
    push_call = next(c for c in calls if c.tool == "git" and c.action == "push")
    assert push_call.result_status == "ok"
    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission"],
        capture_output=True,
        text=True,
    )
    assert log.returncode == 0 and log.stdout.strip() != ""
    store.close()


async def test_builder_agent_cannot_push_even_with_remote_configured(tmp_path):
    """Least-privilege guard: configuring HUFI_GIT_REMOTE_URL alone must not
    grant push capability to the default `builder` agent -- only explicitly
    requesting the `integrator` agent does."""
    bare = make_bare_remote(tmp_path)
    store, engine = setup(tmp_path, git_remote_url=str(bare))
    mission = engine.submit(
        MissionCreate(
            outcome="ship it",
            risk_ceiling="R2",
            steps=[
                TaskSpec(
                    objective="push a note",
                    allowed_tools=["files", "git"],
                    operations=[
                        {"tool": "git", "action": "init"},
                        {
                            "tool": "files",
                            "action": "write_file",
                            "target": "note.md",
                            "params": {"content": "hello"},
                        },
                        {"tool": "git", "action": "add", "params": {"path": "note.md"}},
                        {"tool": "git", "action": "commit"},
                        {"tool": "git", "action": "remote_add"},
                        {"tool": "git", "action": "push"},
                    ],
                )
            ],
        )
    )
    settled = await settle(engine, mission.id)
    assert settled.status == State.failed
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        calls = tx.tool_calls.list(task_id=task.id)
    # Local git config (init/add/commit/remote_add) has no external effect and
    # stays R1, so it succeeds even for the R1-capped builder; only the actual
    # outbound push is R2 and is denied by the agent's ceiling before it runs.
    push_call = next(c for c in calls if c.tool == "git" and c.action == "push")
    assert push_call.result_status == "blocked"  # never executed: denied pre-effect
    remote_added = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission"],
        capture_output=True,
        text=True,
    )
    assert remote_added.stdout.strip() == ""  # nothing ever reached the remote
    store.close()


async def test_unknown_agent_id_is_rejected_at_submit_time(tmp_path):
    store, engine = setup(tmp_path)
    with pytest.raises(KeyError):
        engine.submit(
            MissionCreate(outcome="x", steps=[TaskSpec(objective="x", agent_id="does-not-exist")])
        )
    store.close()


async def test_omitting_agent_id_still_defaults_to_builder(tmp_path):
    store, engine = setup(tmp_path)
    mission = engine.submit(MissionCreate(outcome="default routing"))
    assert (await settle(engine, mission.id)).status == State.completed
    with store.transaction() as tx:
        assert tx.tasks.list(mission_id=mission.id)[0].assigned_agent_id == "builder"
    store.close()
