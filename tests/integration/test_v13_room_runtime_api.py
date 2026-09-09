"""Integration tests for the V1.3 Room->Runtime API.

Covers:
- Unauthenticated access denied (when auth enabled)
- Room message CRUD via HTTP
- Unknown room safe failure
- Unknown mention safe failure (not abort)
- Dispatch endpoint
- Participant management
- Cross-room isolation
- Message reload via new client
"""

from fastapi.testclient import TestClient

from hufiagents import auth
from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import Agent, ChatRoom, Risk


def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
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


def _create_room_direct(store, name="release-team"):
    with store.transaction() as tx:
        return tx.chat_rooms.add(ChatRoom(room_type="team", host_type="team", name=name))


def _create_agent_direct(store, agent_id, role="specialist"):
    with store.transaction() as tx:
        return tx.agents.add(
            Agent(
                id=agent_id,
                role=role,
                capabilities={"tools": ["files"], "providers": ["fake"]},
                risk_ceiling=Risk.R1,
            )
        )


# ---------------------------------------------------------------------------
# Unauthenticated access
# ---------------------------------------------------------------------------


def test_unauthenticated_rooms_api_denied(tmp_path):
    """When auth is enabled, unauthenticated requests to rooms endpoints are denied."""
    with TestClient(create_app(auth_settings(tmp_path))) as client:
        response = client.get("/rooms/any-room/messages")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Basic message API (no auth required in default settings)
# ---------------------------------------------------------------------------


def test_unknown_room_returns_404(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        resp = client.get("/rooms/no-such-room/messages")
        assert resp.status_code == 404


def test_post_message_persists_and_get_returns_it(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)

        resp = client.post(
            f"/rooms/{room.id}/messages",
            json={"sender_id": "pascal", "content": "Prüft bitte den aktuellen Release."},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data
        assert data["message"]["sender_id"] == "pascal"
        assert "unknown_mentions" in data

        # GET should return the persisted message
        get_resp = client.get(f"/rooms/{room.id}/messages")
        assert get_resp.status_code == 200
        messages = get_resp.json()
        assert len(messages) == 1
        assert messages[0]["id"] == data["message"]["id"]


def test_post_message_empty_content_returns_422(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)

        resp = client.post(
            f"/rooms/{room.id}/messages",
            json={"sender_id": "pascal", "content": "   "},
        )
        assert resp.status_code == 422


def test_post_message_unknown_mention_surfaces_in_response(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)

        resp = client.post(
            f"/rooms/{room.id}/messages",
            json={"sender_id": "pascal", "content": "@GHOST-AGENT please check."},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "GHOST-AGENT" in data["unknown_mentions"]
        # Message still persisted
        assert data["message"]["id"] is not None


def test_dispatch_creates_mission(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)
        _create_agent_direct(store, "HM-SENTINEL")

        # Post a message with a valid mention
        post_resp = client.post(
            f"/rooms/{room.id}/messages",
            json={"sender_id": "pascal", "content": "@HM-SENTINEL check this"},
        )
        assert post_resp.status_code == 201
        msg_id = post_resp.json()["message"]["id"]

        # Dispatch
        dispatch_resp = client.post(
            f"/rooms/{room.id}/messages/{msg_id}/dispatch",
            json={"outcome": "Check the current release.", "requested_by": "pascal"},
        )
        assert dispatch_resp.status_code == 202
        dispatch_data = dispatch_resp.json()
        assert len(dispatch_data["dispatched"]) == 1
        assert dispatch_data["dispatched"][0]["agent_id"] == "HM-SENTINEL"


# ---------------------------------------------------------------------------
# Participant management
# ---------------------------------------------------------------------------


def test_participant_join_and_list(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)
        _create_agent_direct(store, "HM-SENTINEL")

        join_resp = client.post(
            f"/rooms/{room.id}/participants",
            json={"agent_id": "HM-SENTINEL"},
        )
        assert join_resp.status_code == 201
        assert join_resp.json()["participation_state"] == "active"

        list_resp = client.get(f"/rooms/{room.id}/participants")
        assert list_resp.status_code == 200
        participants = list_resp.json()
        assert any(p["agent_id"] == "HM-SENTINEL" for p in participants)


def test_participant_state_update(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)
        _create_agent_direct(store, "HM-SENTINEL")

        client.post(f"/rooms/{room.id}/participants", json={"agent_id": "HM-SENTINEL"})

        for state in ("listening", "sleeping", "active"):
            patch_resp = client.patch(
                f"/rooms/{room.id}/participants/HM-SENTINEL",
                json={"state": state},
            )
            assert patch_resp.status_code == 200
            assert patch_resp.json()["participation_state"] == state


def test_participant_invalid_state_returns_422(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)
        _create_agent_direct(store, "HM-SENTINEL")

        client.post(f"/rooms/{room.id}/participants", json={"agent_id": "HM-SENTINEL"})
        resp = client.patch(
            f"/rooms/{room.id}/participants/HM-SENTINEL",
            json={"state": "busy"},
        )
        assert resp.status_code == 422


def test_participant_leave(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)
        _create_agent_direct(store, "HM-SENTINEL")

        client.post(f"/rooms/{room.id}/participants", json={"agent_id": "HM-SENTINEL"})
        leave_resp = client.delete(f"/rooms/{room.id}/participants/HM-SENTINEL")
        assert leave_resp.status_code == 200
        assert leave_resp.json()["participation_state"] == "left"


# ---------------------------------------------------------------------------
# Security: cross-room isolation
# ---------------------------------------------------------------------------


def test_cross_room_message_isolation(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        roomA = _create_room_direct(store, "room-a")
        roomB = _create_room_direct(store, "room-b")

        client.post(
            f"/rooms/{roomA.id}/messages",
            json={"sender_id": "pascal", "content": "A only"},
        )

        resp_b = client.get(f"/rooms/{roomB.id}/messages")
        assert resp_b.status_code == 200
        assert resp_b.json() == []


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_message_list_pagination(tmp_path):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        store = client.app.state.store
        room = _create_room_direct(store)

        for i in range(5):
            client.post(
                f"/rooms/{room.id}/messages",
                json={"sender_id": "pascal", "content": f"Message {i}"},
            )

        page1 = client.get(f"/rooms/{room.id}/messages?limit=3&offset=0").json()
        page2 = client.get(f"/rooms/{room.id}/messages?limit=3&offset=3").json()
        assert len(page1) == 3
        assert len(page2) == 2
        all_ids = [m["id"] for m in page1 + page2]
        assert len(set(all_ids)) == 5


# ---------------------------------------------------------------------------
# Reload persistence via separate client
# ---------------------------------------------------------------------------


def test_reload_persistence_new_client(tmp_path):
    """Messages must survive a new TestClient (simulates process restart)."""
    s = settings(tmp_path)
    app1 = create_app(s)
    with TestClient(app1) as client1:
        store = client1.app.state.store
        room = _create_room_direct(store)

        for i in range(3):
            client1.post(
                f"/rooms/{room.id}/messages",
                json={"sender_id": "pascal", "content": f"Msg {i}"},
            )
        room_id = room.id

    # New app instance (new process)
    app2 = create_app(s)
    with TestClient(app2) as client2:
        resp = client2.get(f"/rooms/{room_id}/messages")
        assert resp.status_code == 200
        assert len(resp.json()) == 3
