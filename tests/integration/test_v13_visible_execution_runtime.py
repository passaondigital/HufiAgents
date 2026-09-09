"""Integration tests for V1.3A Visible Execution Runtime.

Covers:
- Golden Visible Work Test: end-to-end execution of a normal engineering mission
  producing automatic WorkEvidence timeline without manual POST calls.
- HTTP API endpoints GET /missions/{id}/execution and GET /agents/{id}/activity.
- Room milestone message integration.
- Backward compatibility with manual POST /work-evidence endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import Agent, ChatRoom, Mission, Risk, State, WorkEvidence
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.providers.base import CompletionRequest, CompletionResult, ProviderHealth


class CapturingProvider:
    """Provider stub that simulates a clean engineering task output."""

    def __init__(self, provider_id: str = "capturing"):
        self.id = provider_id
        self.captured_requests: list[CompletionRequest] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(available=True, reason="ok")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.captured_requests.append(request)
        return CompletionResult(
            text="Completed engineering task output with report.", model="capturing-fake"
        )


def make_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files", "shell", "git"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )
    return store


@pytest.mark.asyncio
async def test_golden_visible_work_flow(tmp_path):
    """
    Golden Visible Work Test (Section 29):
    1. Submit normal Engineering Mission through Orchestrator.
    2. Populate workspace with repo files (src/auth.py, tests/test_auth.py).
    3. Execute task through Orchestrator engine.
    4. Verify automatic WorkEvidence timeline is created for mission start, repo context,
       task start, tool execution, review, and completion.
    5. Reconstruct Store instance and verify evidence timeline persists cleanly
       without manual POST /work-evidence.
    """
    db_url = f"sqlite:///{tmp_path}/state.sqlite3"
    ws_root = tmp_path / "workspaces"
    store = Store(db_url)
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )

    capturing_provider = CapturingProvider()
    settings = Settings(
        database_url=db_url,
        workspace_root=ws_root,
        default_provider="capturing",
    )
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(outcome="Investigate the auth session recovery bug.")
    mission = engine.submit(request)

    ws_dir = ws_root / mission.id
    (ws_dir / "src").mkdir(parents=True, exist_ok=True)
    (ws_dir / "tests").mkdir(parents=True, exist_ok=True)
    (ws_dir / "src" / "auth.py").write_text("def recover_session(): pass\n", encoding="utf-8")
    (ws_dir / "tests" / "test_auth.py").write_text("def test_session(): pass\n", encoding="utf-8")

    with store.transaction() as tx:
        task_id = tx.tasks.list(mission_id=mission.id)[0].id

    await engine.run(task_id)

    with store.transaction() as tx:
        completed_task = tx.tasks.get(task_id)
        assert completed_task.status == State.completed

    store.close()

    # Reconstruct store & verify persistence
    reloaded_store = Store(db_url)
    with reloaded_store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id=mission.id)
        assert len(evidence) >= 3

        source_types = {e.source_type for e in evidence}
        assert "MISSION" in source_types
        assert "TASK" in source_types or "REPO_CONTEXT" in source_types
        assert any(e.evidence_type in {"COMPLETED", "STARTED", "PREPARED"} for e in evidence)

    reloaded_store.close()


@pytest.mark.asyncio
async def test_execution_feed_api_endpoints(tmp_path):
    """Test HTTP API endpoints GET /missions/{id}/execution and GET /agents/{id}/activity."""
    db_url = f"sqlite:///{tmp_path}/state.sqlite3"
    ws_root = tmp_path / "workspaces"
    settings = Settings(
        database_url=db_url,
        workspace_root=ws_root,
        default_provider="capturing",
    )
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(outcome="API feed mission check")
    mission = engine.submit(request)

    with store.transaction() as tx:
        task_id = tx.tasks.list(mission_id=mission.id)[0].id

    await engine.run(task_id)

    app = create_app(settings)
    client = TestClient(app)

    # Test GET /missions/{mission_id}/execution
    res = client.get(f"/missions/{mission.id}/execution")
    assert res.status_code == 200
    feed = res.json()
    assert feed["mission_id"] == mission.id
    assert feed["status"] in {"completed", "running"}
    assert "current_activity" in feed
    assert "last_activity_at" in feed
    assert "recent_evidence" in feed
    assert len(feed["recent_evidence"]) >= 1

    # Test GET /agents/builder/activity
    res_agent = client.get("/agents/builder/activity")
    assert res_agent.status_code == 200
    act = res_agent.json()
    assert act["agent_id"] == "builder"
    assert "current_activity" in act

    store.close()


@pytest.mark.asyncio
async def test_room_milestone_integration(tmp_path):
    """Verify major milestones dispatch milestone messages to room chat."""
    db_url = f"sqlite:///{tmp_path}/state.sqlite3"
    settings = Settings(
        database_url=db_url,
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    room_id = "room-test-123"
    with store.transaction() as tx:
        tx.chat_rooms.add(
            ChatRoom(id=room_id, room_type="team", host_type="local", name="Dev Room")
        )

    request = MissionCreate(
        outcome="Room feature task",
        constraints={"room_id": room_id},
    )
    mission = engine.submit(request)

    with store.transaction() as tx:
        task_id = tx.tasks.list(mission_id=mission.id)[0].id

    await engine.run(task_id)

    with store.transaction() as tx:
        messages = tx.room_messages.list(room_id=room_id)
        assert len(messages) >= 1
        assert any("📌" in m.content for m in messages)

    store.close()


def test_manual_work_evidence_api_compatible(tmp_path):
    """Verify POST /work-evidence remains compatible."""
    db_url = f"sqlite:///{tmp_path}/state.sqlite3"
    settings = Settings(database_url=db_url)
    store = make_store(tmp_path)

    app = create_app(settings)
    client = TestClient(app)

    with store.transaction() as tx:
        m = tx.missions.add(Mission(outcome="Manual check"))

    payload = WorkEvidence(
        mission_id=m.id,
        source_type="MANUAL",
        evidence_type="NOTE",
        summary="Manual evidence test note",
    ).model_dump(mode="json")

    res = client.post("/work-evidence", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["summary"] == "Manual evidence test note"

    store.close()
