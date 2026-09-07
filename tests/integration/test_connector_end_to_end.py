"""End-to-end proof that the Phase 2B project connector (docs/DECISIONS.md
ADR-010) wires clone -> branch -> edit -> test -> commit -> push -> PR
together through the real Mission -> Task -> Gateway -> Tool pipeline, with a
full audit trail, and survives a simulated process restart -- against a
disposable local "fake external repo" so no network is required (the real
read-only clone of passaondigital/hufmanager is a separate, manual,
documented verification step, docs/CONNECTOR-HUFMANAGER.md)."""

import asyncio
import subprocess

import yaml

from hufiagents.config import Settings
from hufiagents.contracts import State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider


def make_fake_external_repo(tmp_path):
    repo = tmp_path / "external-repo.git-src"
    subprocess.run(["/usr/bin/git", "init", "-q", "--initial-branch=main", str(repo)], check=True)
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


def write_projects_yaml(tmp_path, bare):
    path = tmp_path / "projects.yaml"
    path.write_text(
        yaml.dump(
            {
                "projects": {
                    "demo": {
                        "repo_url": str(bare),
                        "github_repo": "org/demo",
                        "default_branch": "main",
                        "allowed": True,
                        "test_command": ["/bin/echo", "tests-ran"],
                    }
                }
            }
        )
    )
    return path


def setup(tmp_path, bare, provider=None, **kwargs):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/db.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        projects_path=write_projects_yaml(tmp_path, bare),
        _env_file=None,
        heartbeat_timeout_seconds=0.1,
        heartbeat_interval_seconds=0.02,
        **kwargs,
    )
    store = Store(settings.database_url)
    return store, Orchestrator(store, settings, {"fake": provider or FakeProvider()})


class SlowProvider(FakeProvider):
    """Blocks the model call so a task is deterministically caught in
    `running` (not yet touching any tool) for the restart test below --
    matches tests/integration/test_reliability.py's own pattern."""

    async def complete(self, request):
        await asyncio.sleep(10)
        return await super().complete(request)


async def settle(engine, mission_id):
    for _ in range(200):
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


def pipeline_steps(*, dry_run, include_open_pr):
    operations = [
        {"tool": "git", "action": "clone"},
        {"tool": "git", "action": "branch", "params": {"branch": "hufi/mission-1"}},
        {
            "tool": "files",
            "action": "write_file",
            "target": "note.md",
            "params": {"content": "hello"},
        },
        {"tool": "shell", "action": "run_tests"},
        {"tool": "git", "action": "add", "params": {"path": "note.md"}},
        {"tool": "git", "action": "commit", "params": {"message": "add note"}},
        {"tool": "git", "action": "push"},
    ]
    tools = ["files", "shell", "git"]
    if include_open_pr:
        operations.append(
            {
                "tool": "github",
                "action": "open_pr",
                "params": {"title": "Add note", "body": "Draft, review required."},
            }
        )
        tools.append("github")
    return TaskSpec(
        objective="ship a small documented change",
        agent_id="integrator",
        project_id="demo",
        dry_run=dry_run,
        allowed_tools=tools,
        budget_seconds=60,
        operations=operations,
    )


async def test_full_pipeline_dry_run_wires_every_tool_together_with_full_audit(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    store, engine = setup(tmp_path, bare)
    mission = engine.submit(
        MissionCreate(
            outcome="ship it",
            risk_ceiling="R2",
            steps=[pipeline_steps(dry_run=True, include_open_pr=True)],
        )
    )
    settled = await settle(engine, mission.id)
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        calls = tx.tool_calls.list(task_id=task.id)
        audit = tx.audit.list(mission_id=mission.id)
    assert settled.status == State.completed, [c.model_dump() for c in calls]
    actions_run = {(c.tool, c.action) for c in calls}
    assert {
        ("git", "clone"),
        ("git", "branch"),
        ("files", "write_file"),
        ("shell", "run_tests"),
        ("git", "add"),
        ("git", "commit"),
        ("git", "push"),
        ("github", "open_pr"),
    } <= actions_run
    push_call = next(c for c in calls if c.tool == "git" and c.action == "push")
    pr_call = next(c for c in calls if c.tool == "github" and c.action == "open_pr")
    assert "dry-run" in push_call.result_summary
    assert "dry-run" in pr_call.result_summary
    kinds = {event.event_type for event in audit}
    assert {
        "mission_created",
        "task_created",
        "project_bound",
        "model_call",
        "model_result",
        "tool_call",
        "tool_started",
        "tool_result",
        "review",
        "state_transition",
    } <= kinds
    project_bound = next(e for e in audit if e.event_type == "project_bound")
    assert project_bound.detail["project_id"] == "demo"
    assert project_bound.detail["repo_url"] == str(bare)
    store.close()


async def test_real_push_through_orchestrator_via_a_cloned_project(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    store, engine = setup(tmp_path, bare)
    mission = engine.submit(
        MissionCreate(
            outcome="ship it",
            risk_ceiling="R2",
            steps=[pipeline_steps(dry_run=False, include_open_pr=False)],
        )
    )
    settled = await settle(engine, mission.id)
    assert settled.status == State.completed
    log = subprocess.run(
        ["/usr/bin/git", "--git-dir", str(bare), "log", "--oneline", "hufi/mission-1"],
        capture_output=True,
        text=True,
    )
    assert log.returncode == 0 and "add note" in log.stdout
    store.close()


async def test_project_task_survives_a_simulated_restart(tmp_path):
    bare = make_fake_external_repo(tmp_path)
    # SlowProvider deterministically catches the task in `running`, blocked on
    # the model call, before it ever reaches a tool -- avoids racing real
    # (fast) local git operations to get a reliable "process died mid-task".
    store, engine = setup(tmp_path, bare, provider=SlowProvider())
    mission = engine.submit(
        MissionCreate(
            outcome="ship it",
            risk_ceiling="R2",
            steps=[pipeline_steps(dry_run=True, include_open_pr=False)],
        )
    )
    await engine.tick()
    await asyncio.sleep(0.03)
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        assert task.status == State.running
    # Simulate an interrupted process: cancel the in-flight runner (as
    # Orchestrator.stop() would on shutdown, leaving a durable checkpoint --
    # see run()'s CancelledError handler) without letting it reach a
    # terminal state, then stand up a *new* Orchestrator against the same
    # on-disk store, as a restart would.
    for runner in engine.active.values():
        runner.cancel()
    await asyncio.gather(*engine.active.values(), return_exceptions=True)
    engine.active.clear()
    await asyncio.sleep(0.15)  # let the heartbeat go stale
    store.close()
    store2 = Store(f"sqlite:///{tmp_path}/db.sqlite3")
    engine2 = Orchestrator(
        store2,
        Settings(
            database_url=f"sqlite:///{tmp_path}/db.sqlite3",
            workspace_root=tmp_path / "workspaces",
            default_provider="fake",
            projects_path=tmp_path / "projects.yaml",
            _env_file=None,
            heartbeat_timeout_seconds=0.1,
            heartbeat_interval_seconds=0.02,
        ),
        {"fake": FakeProvider()},
    )
    engine2.recover()
    settled = await settle(engine2, mission.id)
    assert settled.status == State.completed
    with store2.transaction() as tx:
        audit = tx.audit.list(mission_id=mission.id)
    kinds = {event.event_type for event in audit}
    assert "recovery" in kinds
    assert any(e.event_type == "project_bound" for e in audit)
    await engine2.stop()
    store2.close()
