import asyncio

from hufiagents.config import Settings
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider
from hufiagents.workforce.team import HufManagerTeamMission


def test_hufmanager_team_mission_fans_out_uses_local_provider_and_reviews(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
    )
    store = Store(settings.database_url)
    engine = Orchestrator(store, settings, {"fake": FakeProvider()})
    result = asyncio.run(HufManagerTeamMission(engine).run())
    assert result["status"] == "completed"
    assert result["review"].verdict == "approve"
    assert "security" in result["report"] and "product" in result["report"]
    with store.transaction() as tx:
        events = {event.event_type for event in tx.audit.list(limit=200)}
        assert {
            "team_mission_started",
            "task_delegated",
            "team_specialist_model_result",
            "fan_in_completed",
            "team_mission_review",
            "team_mission_completed",
        } <= events
    store.close()
