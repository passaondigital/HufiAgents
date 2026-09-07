"""V1 login gate (hufiagents/auth.py, docs/DECISIONS.md ADR-015): the entire
API/UI is closed by default once admin_username/admin_password_hash are
configured, /health stays public, a valid session authorizes approve/deny
without a separate bearer token, and none of this affects a deployment (or
the rest of the test suite) that never configures auth at all.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from hufiagents import auth
from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import Risk, State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider
from hufiagents.tools.files import FilesTool


def auth_settings(tmp_path, **kwargs):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        admin_username="passaondigital@gmail.com",
        admin_password_hash=auth.hash_password("a-strong-test-password"),
        session_secret="unit-test-session-secret",
        cookie_secure=False,
        _env_file=None,
        **kwargs,
    )


def test_auth_disabled_by_default_leaves_api_open(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
    )
    assert settings.auth_enabled is False
    with TestClient(create_app(settings)) as client:
        assert client.get("/missions").status_code == 200
        assert client.get("/", headers={"accept": "text/html"}).status_code == 200


def test_half_configured_auth_fails_closed_at_startup(tmp_path):
    with pytest.raises(ValueError, match="admin_password_hash"):
        Settings(
            database_url=f"sqlite:///{tmp_path}/state.sqlite3",
            workspace_root=tmp_path / "workspaces",
            default_provider="fake",
            admin_username="passaondigital@gmail.com",
            _env_file=None,
        )


def test_unauthenticated_requests_are_denied_and_health_stays_public(tmp_path):
    with TestClient(create_app(auth_settings(tmp_path))) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/missions").status_code == 401
        assert client.post("/missions", json={"outcome": "x"}).status_code == 401
        redirect = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
        assert redirect.status_code == 303 and redirect.headers["location"] == "/login"
        assert client.get("/login").status_code == 200


def test_wrong_credentials_rejected_correct_credentials_set_working_session(tmp_path):
    with TestClient(create_app(auth_settings(tmp_path))) as client:
        wrong = client.post(
            "/login", json={"username": "passaondigital@gmail.com", "password": "nope"}
        )
        assert wrong.status_code == 401
        assert auth.COOKIE_NAME not in client.cookies

        ok = client.post(
            "/login",
            json={"username": "passaondigital@gmail.com", "password": "a-strong-test-password"},
        )
        assert ok.status_code == 200
        assert auth.COOKIE_NAME in client.cookies
        assert client.get("/missions").status_code == 200

        assert client.post("/logout").status_code == 200
        assert client.get("/missions").status_code == 401


class ApprovalFiles(FilesTool):
    """R3-classified regardless of action -- forces waiting_approval without
    depending on any real tool's own risk classification (mirrors
    tests/integration/test_reliability.py's ApprovalFiles)."""

    async def classify(self, action, params):
        await super().classify(action, params)
        return Risk.R3


def test_session_authorizes_approval_without_a_separate_bearer_token(tmp_path):
    settings = auth_settings(tmp_path)
    store = Store(settings.database_url)
    engine = Orchestrator(store, settings, {"fake": FakeProvider()})
    with store.transaction() as tx:
        agent = tx.agents.get("builder")
        agent.default_risk_ceiling = Risk.R4
        tx.agents.save(agent)
    engine.tools = lambda workspace, task=None: {"files": ApprovalFiles(workspace)}
    mission = engine.submit(MissionCreate(outcome="approval simulation", risk_ceiling=Risk.R4))

    async def settle_to_waiting_approval():
        for _ in range(100):
            await engine.tick()
            if engine.active:
                await asyncio.gather(*engine.active.values())
            with engine.store.transaction() as tx:
                if tx.missions.get(mission.id).status == State.waiting_approval:
                    return tx.approvals.list()[0]
        raise AssertionError("mission never reached waiting_approval")

    approval = asyncio.run(settle_to_waiting_approval())
    asyncio.run(engine.stop())
    store.close()

    with TestClient(create_app(settings)) as client:
        # No Authorization header at all -- only the logged-in session.
        client.post(
            "/login",
            json={"username": "passaondigital@gmail.com", "password": "a-strong-test-password"},
        )
        response = client.post(f"/approvals/{approval.id}/deny", json={"note": "test denial"})
        assert response.status_code == 200

    with Store(settings.database_url).transaction() as tx:
        assert tx.approvals.get(approval.id).status == "denied"


def test_projects_and_models_endpoints_report_configured_state(tmp_path):
    with TestClient(create_app(auth_settings(tmp_path))) as client:
        client.post(
            "/login",
            json={"username": "passaondigital@gmail.com", "password": "a-strong-test-password"},
        )
        projects = client.get("/projects").json()
        assert {p["id"] for p in projects} == {"hufiagents", "hufmanager"}
        models = client.get("/models").json()
        assert models["default_provider"] == "fake"
        assert {p["provider"] for p in models["providers"]} == {
            "fake",
            "hufi-local-router",
            "ollama",
        }
