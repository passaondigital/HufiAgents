import asyncio
from datetime import timedelta

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import Risk, State, now
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.persistence.repository import Store
from hufiagents.providers.base import CompletionResult
from hufiagents.providers.fake import FakeProvider
from hufiagents.tools.files import FilesTool


def setup(tmp_path, provider=None, **kwargs):
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
    return store, Orchestrator(store, settings, {"fake": provider or FakeProvider()})


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


class FlakyProvider(FakeProvider):
    def __init__(self):
        self.calls = 0

    async def complete(self, request):
        self.calls += 1
        if self.calls < 2:
            raise ConnectionError("transient failure")
        return await super().complete(request)


async def test_provider_retry(tmp_path):
    provider = FlakyProvider()
    store, engine = setup(tmp_path, provider)
    mission = engine.submit(MissionCreate(outcome="test retries"))
    assert (await settle(engine, mission.id)).status == State.completed
    assert provider.calls == 2
    with store.transaction() as tx:
        assert tx.tasks.list(mission_id=mission.id)[0].retry_count == 1
    store.close()


class RevisableProvider(FakeProvider):
    async def complete(self, request):
        text = "corrected" if "criterion failed" in request.context else "first attempt"
        return CompletionResult(text=text, model="fake")


async def test_review_findings_reach_next_attempt(tmp_path):
    store, engine = setup(tmp_path, RevisableProvider())
    mission = engine.submit(
        MissionCreate(
            outcome="revise",
            steps=[
                TaskSpec(
                    objective="revise",
                    acceptance_criteria=[{"type": "contains", "value": "corrected"}],
                )
            ],
        )
    )
    assert (await settle(engine, mission.id)).status == State.completed
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        assert task.retry_count == 1
        assert [r.verdict for r in tx.reviews.list(task_id=task.id)] == ["revise", "approve"]
    store.close()


class SlowProvider(FakeProvider):
    async def complete(self, request):
        await asyncio.sleep(10)
        return await super().complete(request)


async def test_timeout_is_bounded(tmp_path):
    store, engine = setup(tmp_path, SlowProvider(), model_timeout_seconds=0.01)
    mission = engine.submit(MissionCreate(outcome="timeout"))
    assert (await settle(engine, mission.id)).status == State.failed
    with store.transaction() as tx:
        assert tx.tasks.list(mission_id=mission.id)[0].retry_count == 2
    store.close()


async def test_heartbeat_and_cancel(tmp_path):
    store, engine = setup(tmp_path, SlowProvider())
    mission = engine.submit(MissionCreate(outcome="slow"))
    await engine.tick()
    await asyncio.sleep(0.05)
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        assert (now() - task.heartbeat_at).total_seconds() < 0.04
    engine.recover()
    await engine.cancel(task.id)
    with store.transaction() as tx:
        assert tx.tasks.get(task.id).status == State.cancelled
    await engine.stop()
    store.close()


class ApprovalFiles(FilesTool):
    executions = 0
    level = Risk.R3

    async def classify(self, action, params):
        await super().classify(action, params)
        return self.level

    async def execute(self, call):
        self.executions += 1
        return await super().execute(call)


@pytest.mark.parametrize(
    "resolution,terminal",
    [("approved", State.completed), ("denied", State.cancelled), ("expired", State.failed)],
)
async def test_approval_lifecycle(tmp_path, resolution, terminal):
    store, engine = setup(tmp_path)
    with store.transaction() as tx:
        agent = tx.agents.get("builder")
        agent.default_risk_ceiling = Risk.R4
        tx.agents.save(agent)
    tool = None

    def tools(workspace):
        nonlocal tool
        if tool is None:
            tool = ApprovalFiles(workspace)
        return {"files": tool}

    engine.tools = tools
    mission = engine.submit(MissionCreate(outcome="approval simulation", risk_ceiling=Risk.R4))
    assert (await settle(engine, mission.id)).status == State.waiting_approval
    assert tool.executions == 0
    with store.transaction() as tx:
        approval = tx.approvals.list()[0]
    if resolution == "expired":
        with store.transaction() as tx:
            approval.requested_at = now() - timedelta(days=2)
            tx.approvals.save(approval)
        engine.recover()
    else:
        engine.resolve(approval.id, resolution)
    assert (await settle(engine, mission.id)).status == terminal
    assert tool.executions == (1 if resolution == "approved" else 0)
    with pytest.raises(ValueError):
        engine.resolve(approval.id, "approved")
    store.close()


async def test_r2_preflight_rejects_before_effect(tmp_path):
    store, engine = setup(tmp_path)
    with store.transaction() as tx:
        agent = tx.agents.get("builder")
        agent.default_risk_ceiling = Risk.R2
        tx.agents.save(agent)

    def tools(workspace):
        tool = ApprovalFiles(workspace)
        tool.level = Risk.R2
        return {"files": tool}

    engine.tools = tools
    mission = engine.submit(MissionCreate(outcome="R2 test", risk_ceiling=Risk.R2))
    assert (await settle(engine, mission.id)).status == State.failed
    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        assert tx.reviews.list(task_id=task.id)[0].verdict == "reject"
        assert tx.approvals.list() == []
        assert not tx.tool_calls.list(task_id=task.id)[0].execution_started
    store.close()


async def test_capacity_and_concurrency(tmp_path):
    store, engine = setup(tmp_path, SlowProvider(), max_pending_tasks=2)
    for i in range(2):
        engine.submit(MissionCreate(outcome=str(i)))
    with pytest.raises(OverflowError):
        engine.submit(MissionCreate(outcome="over limit"))
    await engine.tick()
    assert len(engine.active) == 2
    await engine.stop()
    store.close()
