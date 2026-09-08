from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings


def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
    )


def test_agent_lifecycle_and_delegation_api(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        lead = {
            "id": "team-lead",
            "role": "lead",
            "capabilities": {"tools": ["files"], "providers": ["fake"]},
            "risk_ceiling": "R1",
        }
        assert client.post("/agents", json=lead).status_code == 201
        child = {
            "id": "researcher",
            "role": "researcher",
            "capabilities": {"tools": ["files"], "providers": ["fake"]},
            "risk_ceiling": "R1",
            "delegator_id": "team-lead",
        }
        assert client.post("/agents", json=child).status_code == 201
        created = client.post(
            "/delegations",
            json={
                "parent_agent_id": "team-lead",
                "child_agent_id": "researcher",
                "objective": "inspect project",
            },
        )
        assert created.status_code == 201
        delegation_id = created.json()["id"]
        messages = client.post("/agents/researcher/messages/receive")
        assert messages.status_code == 200 and messages.json()[0]["content"] == "inspect project"
        assert (
            client.post(
                f"/delegations/{delegation_id}/result",
                json={"agent_id": "researcher", "result": "facts"},
            ).json()["status"]
            == "completed"
        )
        archived = client.post("/agents/researcher/archive")
        assert archived.status_code == 200 and archived.json()["status"] == "archived"
        assert client.get("/agents/researcher").json()["archived_at"] is not None
