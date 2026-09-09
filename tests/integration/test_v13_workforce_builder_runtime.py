"""Integration tests — V1.3 Workforce Builder API.

Tests use the real FastAPI app with an in-memory SQLite database.
All tests are self-contained: no external services, no mocks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings


@pytest.fixture()
def client():
    settings = Settings(database_url="sqlite:///:memory:")
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _create_caller_agent(client: TestClient, agent_id: str = "caller-001") -> dict:
    """Create a caller agent with broad permissions for provisioning tests."""
    resp = client.post(
        "/agents",
        json={
            "id": agent_id,
            "role": "orchestrator",
            "capabilities": {
                "providers": ["local", "hufi-local-router"],
                "tools": ["files", "shell"],
            },
            "risk_ceiling": "R2",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Provision endpoint
# ---------------------------------------------------------------------------


class TestProvisionEndpoint:
    def test_golden_provisioning(self, client):
        _create_caller_agent(client)
        resp = client.post(
            "/workforce/provision",
            json={
                "display_name": "Pascal the Planner",
                "role": "planner",
                "description": "Plans missions end-to-end",
                "capabilities": {
                    "providers": ["local"],
                    "tools": ["files"],
                },
                "risk_ceiling": "R1",
                "model_preference": "local",
                "source": "test",
            },
            headers={"x-caller-agent-id": "caller-001"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["role"] == "planner"
        assert body["name"] == "Pascal the Planner"
        assert body["status"] == "active"

    def test_secret_rejection_api_key(self, client):
        _create_caller_agent(client)
        resp = client.post(
            "/workforce/provision",
            json={
                "display_name": "SecretBot",
                "role": "bot",
                "capabilities": {"api_key": "sk-supersecret"},
            },
            headers={"x-caller-agent-id": "caller-001"},
        )
        assert resp.status_code == 422, resp.text

    def test_capability_escalation_blocked(self, client):
        # Create caller with limited caps
        client.post(
            "/agents",
            json={
                "id": "limited-caller",
                "role": "limited",
                "capabilities": {"providers": ["local"]},
                "risk_ceiling": "R1",
            },
        )
        resp = client.post(
            "/workforce/provision",
            json={
                "display_name": "EscalatorBot",
                "role": "hacker",
                "capabilities": {"providers": ["local", "openai-external"]},
                "risk_ceiling": "R1",
            },
            headers={"x-caller-agent-id": "limited-caller"},
        )
        assert resp.status_code == 403, resp.text
        assert "capabilities" in resp.json()["detail"]

    def test_risk_escalation_blocked(self, client):
        # Caller is R1; request is R3
        _create_caller_agent(client)
        resp = client.post(
            "/workforce/provision",
            json={
                "display_name": "HighRiskBot",
                "role": "admin",
                "capabilities": {},
                "risk_ceiling": "R3",
            },
            headers={"x-caller-agent-id": "caller-001"},
        )
        assert resp.status_code == 403, resp.text
        assert "risk ceiling" in resp.json()["detail"]

    def test_idempotent_provisioning(self, client):
        _create_caller_agent(client)
        payload = {
            "display_name": "Idempotent Worker",
            "role": "worker",
            "capabilities": {},
            "idempotency_key": "idempotent-test-42",
        }
        resp1 = client.post(
            "/workforce/provision", json=payload, headers={"x-caller-agent-id": "caller-001"}
        )
        resp2 = client.post(
            "/workforce/provision", json=payload, headers={"x-caller-agent-id": "caller-001"}
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]


# ---------------------------------------------------------------------------
# Profile update endpoint
# ---------------------------------------------------------------------------


class TestProfileUpdateEndpoint:
    def _provision(self, client, agent_id_suffix="") -> str:
        _create_caller_agent(client, f"caller{agent_id_suffix}")
        resp = client.post(
            "/workforce/provision",
            json={"display_name": f"Worker{agent_id_suffix}", "role": "worker", "capabilities": {}},
            headers={"x-caller-agent-id": f"caller{agent_id_suffix}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_update_allowed_field(self, client):
        agent_id = self._provision(client, "-upd")
        resp = client.patch(
            f"/workforce/agents/{agent_id}/profile",
            json={"changes": {"description": "Updated description"}, "actor": "admin"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["description"] == "Updated description"

    def test_update_immutable_field_blocked(self, client):
        agent_id = self._provision(client, "-imm")
        resp = client.patch(
            f"/workforce/agents/{agent_id}/profile",
            json={"changes": {"id": "new-id"}, "actor": "admin"},
        )
        assert resp.status_code == 403, resp.text

    def test_update_nonexistent_agent_404(self, client):
        resp = client.patch(
            "/workforce/agents/does-not-exist/profile",
            json={"changes": {"description": "x"}, "actor": "admin"},
        )
        assert resp.status_code == 404

    def test_archived_agent_update_blocked(self, client):

        # Use the client fixture app's own store so agent is found by the API
        # Provision via API, then archive via builder on same store
        _create_caller_agent(client, "arch-caller")
        prov = client.post(
            "/workforce/provision",
            json={"display_name": "ToArchive", "role": "archiveable", "capabilities": {}},
            headers={"x-caller-agent-id": "arch-caller"},
        )
        assert prov.status_code == 201
        agent_id = prov.json()["id"]

        # Archive via PATCH (set status directly — archive_agent is not yet an API endpoint,
        # so call the API profile update to set status=archived)
        resp = client.patch(
            f"/workforce/agents/{agent_id}/profile",
            json={"changes": {"status": "archived"}, "actor": "admin"},
        )
        assert resp.status_code == 200

        # Now updating should be blocked
        resp2 = client.patch(
            f"/workforce/agents/{agent_id}/profile",
            json={"changes": {"description": "attempt"}, "actor": "admin"},
        )
        assert resp2.status_code == 403
        assert "archived" in resp2.json()["detail"]


# ---------------------------------------------------------------------------
# Profile history endpoint
# ---------------------------------------------------------------------------


class TestProfileHistoryEndpoint:
    def test_history_has_initial_snapshot(self, client):
        """Provision via HTTP API then verify profile history via HTTP.

        Uses the same client fixture app throughout — no separate store instance.
        """
        _create_caller_agent(client, "hist-caller")
        resp = client.post(
            "/workforce/provision",
            json={"display_name": "History Agent", "role": "historian", "capabilities": {}},
            headers={"x-caller-agent-id": "hist-caller"},
        )
        assert resp.status_code == 201, resp.text
        agent_id = resp.json()["id"]

        hist = client.get(f"/workforce/agents/{agent_id}/profile-history")
        assert hist.status_code == 200, hist.text
        body = hist.json()
        assert body["agent_id"] == agent_id
        assert body["count"] >= 1
        assert body["history"][0]["version"] == 1

    def test_history_grows_after_update(self, client):
        """Provision + update via HTTP; verify history count grows.

        Uses the same client fixture app throughout — no separate store instance.
        """
        _create_caller_agent(client, "hist-upd-caller")
        resp = client.post(
            "/workforce/provision",
            json={"display_name": "Growing Agent", "role": "grower", "capabilities": {}},
            headers={"x-caller-agent-id": "hist-upd-caller"},
        )
        assert resp.status_code == 201, resp.text
        agent_id = resp.json()["id"]

        upd = client.patch(
            f"/workforce/agents/{agent_id}/profile",
            json={"changes": {"description": "v2"}, "actor": "test"},
        )
        assert upd.status_code == 200, upd.text

        hist = client.get(f"/workforce/agents/{agent_id}/profile-history")
        assert hist.status_code == 200, hist.text
        body = hist.json()
        assert body["count"] == 2
        assert body["history"][-1]["version"] == 2

    def test_history_404_for_unknown_agent(self, client):
        resp = client.get("/workforce/agents/ghost-agent/profile-history")
        assert resp.status_code == 404
