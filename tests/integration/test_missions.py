import time

from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings


def settings(tmp_path, **kwargs):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
        **kwargs,
    )


def wait_mission(client, identifier):
    for _ in range(200):
        mission = client.get(f"/missions/{identifier}").json()
        if mission["status"] in {"completed", "failed", "cancelled", "waiting_approval"}:
            return mission
        time.sleep(0.02)
    raise AssertionError(f"mission did not settle: {mission}")


def test_full_mission_and_restart(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config)) as client:
        response = client.post("/missions", json={"outcome": "Write a useful status report"})
        assert response.status_code == 202
        identifier = response.json()["id"]
        mission = wait_mission(client, identifier)
        assert mission["status"] == "completed", client.get(
            "/audit", params={"mission_id": identifier}
        ).json()
        task = client.get("/tasks", params={"mission_id": identifier}).json()[0]
        assert task["assigned_agent_id"] == "builder"
        assert task["selected_provider"] == "fake"
        reviews = client.get("/reviews", params={"task_id": task["id"]}).json()
        assert reviews[0]["verdict"] == "approve"
        calls = client.get("/tool-calls", params={"task_id": task["id"]}).json()
        assert calls[0]["result_status"] == "ok"
        artifact = config.workspace_root / identifier / calls[0]["target"]
        assert artifact.read_text() == task["result"]
        audit = client.get("/audit", params={"mission_id": identifier}).json()
        kinds = {event["event_type"] for event in audit}
        assert {
            "model_call",
            "model_result",
            "tool_call",
            "tool_result",
            "review",
            "state_transition",
        } <= kinds
        assert client.get("/").status_code == 200
    with TestClient(create_app(config)) as client:
        assert client.get(f"/missions/{identifier}").json() == mission
        assert client.get("/audit", params={"mission_id": identifier}).json() == audit


def test_review_failure_and_dependency_cancellation(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/missions",
            json={
                "outcome": "Sequential work",
                "steps": [
                    {
                        "objective": "first",
                        "acceptance_criteria": [{"type": "contains", "value": "MISSING"}],
                    },
                    {"objective": "second"},
                ],
            },
        )
        identifier = response.json()["id"]
        assert wait_mission(client, identifier)["status"] == "failed"
        for _ in range(100):
            tasks = client.get("/tasks", params={"mission_id": identifier}).json()
            if tasks[1]["status"] == "cancelled":
                break
            time.sleep(0.02)
        assert tasks[0]["retry_count"] == 2
        assert tasks[1]["status"] == "cancelled"
        assert len(client.get("/reviews", params={"task_id": tasks[0]["id"]}).json()) == 3


def test_sequential_tasks_and_safe_tools(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/missions",
            json={
                "outcome": "two steps",
                "steps": [
                    {
                        "objective": "one",
                        "allowed_tools": ["files", "shell", "git"],
                        "operations": [
                            {"tool": "git", "action": "init"},
                            {
                                "tool": "shell",
                                "action": "run_command",
                                "params": {"command": "pwd"},
                            },
                        ],
                    },
                    {"objective": "two"},
                ],
            },
        )
        identifier = response.json()["id"]
        assert wait_mission(client, identifier)["status"] == "completed"
        tasks = client.get("/tasks", params={"mission_id": identifier}).json()
        assert len(tasks) == 2 and all(t["status"] == "completed" for t in tasks)


def test_http_boundaries(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.get("/missions/absent").status_code == 404
        assert client.get("/missions?limit=100000").status_code == 422
        assert (
            client.post(
                "/missions", json={"outcome": "test"}, headers={"origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.get("/health", headers={"host": "evil.test"}).status_code == 400
        assert client.post("/approvals/unknown/approve", json={}).status_code == 503
        assert (
            client.post(
                "/missions",
                json={
                    "outcome": "test",
                    "steps": [{"objective": "bad", "expected_output": "../escape"}],
                },
            ).status_code
            == 409
        )
