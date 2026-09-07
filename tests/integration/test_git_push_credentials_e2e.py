"""Orchestrator-level proof (docs/DECISIONS.md ADR-011): the `integrator`
agent pushes a real commit through the full Mission -> Task -> Gateway ->
Tool pipeline, authenticated via a real local basic-auth-enforcing
git-smart-HTTP server (tests/support/git_http_server.py), and the token
never surfaces anywhere in the persisted DB (tool_calls.params,
audit_log.detail, reviews) -- not just in the tool call in isolation
(tests/unit/test_git_push_credentials.py covers that)."""

import asyncio
import subprocess

from hufiagents.config import Settings
from hufiagents.contracts import State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider
from tests.support.git_http_server import basic_auth_git_server, make_bare_http_repo

TOKEN = "s3cr3t-orchestrator-push-token"
USERNAME = "x-access-token"


def setup(tmp_path, *, github_token="", git_remote_url=""):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/db.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        github_token=github_token,
        git_remote_url=git_remote_url,
        _env_file=None,
        heartbeat_timeout_seconds=0.1,
        heartbeat_interval_seconds=0.02,
    )
    store = Store(settings.database_url)
    return store, Orchestrator(store, settings, {"fake": FakeProvider()})


async def settle(engine, mission_id):
    for _ in range(200):
        await engine.tick()
        if engine.active:
            await asyncio.gather(*engine.active.values(), return_exceptions=True)
        with engine.store.transaction() as tx:
            mission = tx.missions.get(mission_id)
        if mission.status in {State.completed, State.failed, State.cancelled}:
            return mission
        await asyncio.sleep(0.02)
    raise AssertionError("mission did not settle")


async def test_integrator_pushes_through_real_http_auth_and_leaves_no_trace_of_the_token(
    tmp_path,
):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    bare = make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        store, engine = setup(tmp_path, github_token=TOKEN, git_remote_url=remote)
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
                                "params": {"content": "hello"},
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
            audit = tx.audit.list(mission_id=mission.id, limit=1000)
            reviews = tx.reviews.list(task_id=task.id)

    assert settled.status == State.completed, [c.model_dump() for c in calls]
    push_call = next(c for c in calls if c.tool == "git" and c.action == "push")
    assert push_call.result_status == "ok"

    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission"],
        capture_output=True,
        text=True,
    )
    assert log.returncode == 0 and log.stdout.strip() != ""

    # Full audit trail, and nowhere does the token appear.
    kinds = {event.event_type for event in audit}
    assert {
        "mission_created",
        "task_created",
        "tool_call",
        "tool_started",
        "tool_result",
        "review",
        "state_transition",
    } <= kinds
    for event in audit:
        assert TOKEN not in str(event.detail)
    for c in calls:
        assert TOKEN not in str(c.params)
        assert TOKEN not in c.result_summary
    assert reviews and reviews[0].verdict == "approve"
    store.close()


async def test_missing_token_fails_the_mission_closed_not_open(tmp_path):
    project_root = tmp_path / "server-root"
    project_root.mkdir()
    make_bare_http_repo(project_root)
    with basic_auth_git_server(project_root, username=USERNAME, password=TOKEN) as base_url:
        remote = f"{base_url}/repo.git"
        store, engine = setup(tmp_path, github_token="", git_remote_url=remote)
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
                                "params": {"content": "hello"},
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
    assert settled.status == State.failed
    store.close()
