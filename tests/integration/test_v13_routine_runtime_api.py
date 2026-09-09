"""Integration tests for V1.3A Autonomous Routine Scheduler Runtime API.

Covers:
- Golden Autonomy Test: background RoutineScheduler detects due routine,
  claims it, creates Mission, executes Task to terminal result, and advances next_run
  WITHOUT manual tick invocation after startup.
- HTTP POST /routines/runtime/tick diagnostic endpoint
- HTTP GET /routines/runtime/status diagnostic endpoint
- Unauthenticated access protection
- Room integration link back
"""

import time
from datetime import timedelta

from fastapi.testclient import TestClient

from hufiagents import auth
from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import ChatRoom, now


def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        poll_interval_seconds=0.05,
        routine_poll_interval_seconds=0.05,
        _env_file=None,
    )


def auth_settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        admin_username="pascal",
        admin_password_hash=auth.hash_password("test-pass"),
        session_secret="test-secret-for-sessions",
        _env_file=None,
    )


# ---------------------------------------------------------------------------
# Golden Autonomy Test
# ---------------------------------------------------------------------------


def test_golden_autonomous_routine_execution(tmp_path):
    """
    Golden Autonomy Test (Section 23):
    1. Create Agent and Routine ("every monday at 08:00").
    2. Make routine due in store.
    3. Start application runtime via TestClient (lifespan starts scheduler & engine loops).
    4. DO NOT call RoutineService.tick manually from the test.
    5. Background application scheduler automatically detects, claims, creates Mission,
       executes Task to terminal state, and advances next_run.
    """
    s = settings(tmp_path)
    app = create_app(s)

    with TestClient(app) as client:
        store = app.state.store

        # builder agent is seeded automatically at app startup

        # 2. Create routine
        create_resp = client.post(
            "/routines",
            json={
                "owner_agent_id": "builder",
                "mission_template": {"outcome": "Golden autonomous routine check"},
                "schedule": "every monday at 08:00",
                "timezone": "Europe/Berlin",
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        routine_id = create_resp.json()["id"]

        # Make routine due
        with store.transaction() as tx:
            r = tx.routines.get(routine_id)
            r.next_run = now() - timedelta(seconds=10)
            tx.routines.save(r)

        # 3. Wait for background scheduler to autonomously detect and execute routine
        # DO NOT call RoutineService.tick manually!
        completed = False
        deadline = time.time() + 5.0
        while time.time() < deadline:
            time.sleep(0.1)
            with store.transaction() as tx:
                r = tx.routines.get(routine_id)
                missions = tx.missions.list()
                if r.last_run is not None and len(missions) > 0:
                    if missions[0].status.value == "completed":
                        completed = True
                        break

        assert completed is True, "Background scheduler failed to execute routine autonomously"

        with store.transaction() as tx:
            r = tx.routines.get(routine_id)
            assert r.last_run is not None
            assert r.next_run > now()
            missions = tx.missions.list()
            assert len(missions) == 1
            assert missions[0].outcome == "Golden autonomous routine check"
            assert missions[0].status.value == "completed"


# ---------------------------------------------------------------------------
# Diagnostic HTTP Endpoints
# ---------------------------------------------------------------------------


def test_routines_runtime_status_endpoint(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        resp = client.get("/routines/runtime/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert data["running"] is True
        assert "tick_count" in data


def test_routines_runtime_tick_manual_endpoint(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        resp = client.post("/routines/runtime/tick")
        assert resp.status_code == 200
        data = resp.json()
        assert "dispatched" in data
        assert "count" in data


# ---------------------------------------------------------------------------
# Auth Protection
# ---------------------------------------------------------------------------


def test_unauthenticated_routines_api_denied(tmp_path):
    with TestClient(create_app(auth_settings(tmp_path))) as client:
        assert client.get("/routines").status_code == 401
        assert client.get("/routines/runtime/status").status_code == 401
        assert client.post("/routines/runtime/tick").status_code == 401


# ---------------------------------------------------------------------------
# Room Integration Link Back
# ---------------------------------------------------------------------------


def test_routine_room_integration(tmp_path):
    """Routine with room_id constraint posts execution result back into ChatRoom."""
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = app.state.store
        with store.transaction() as tx:
            room = tx.chat_rooms.add(
                ChatRoom(room_type="team", host_type="team", name="release-team")
            )

        create_resp = client.post(
            "/routines",
            json={
                "owner_agent_id": "builder",
                "mission_template": {
                    "outcome": "Room integrated routine check",
                    "constraints": {"room_id": room.id},
                },
                "schedule": "every day at 08:00",
                "timezone": "Europe/Berlin",
            },
        )
        assert create_resp.status_code == 201
        routine_id = create_resp.json()["id"]

        with store.transaction() as tx:
            r = tx.routines.get(routine_id)
            r.next_run = now() - timedelta(seconds=10)
            tx.routines.save(r)

        # Wait for autonomous execution & room result posting
        completed = False
        deadline = time.time() + 5.0
        while time.time() < deadline:
            time.sleep(0.1)
            with store.transaction() as tx:
                messages = tx.room_messages.list(room_id=room.id)
                if len(messages) > 0:
                    completed = True
                    break

        assert completed is True, "Routine execution result was not posted back into ChatRoom"
        with store.transaction() as tx:
            messages = tx.room_messages.list(room_id=room.id)
            assert len(messages) == 1
            assert messages[0].sender_type == "system"
            assert "Room integrated routine check" in messages[0].content
