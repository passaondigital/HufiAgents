"""HTTP-layer coverage for the two mutation endpoints that were only exercised
through Orchestrator.resolve()/cancel() directly before this review:
- approve/deny require the owner bearer token (hmac.compare_digest path in
  hufiagents.api); the wrong-token and no-token cases were untested at the HTTP
  boundary (only the "no token configured" 503 case existed, via an unknown id).
- POST /tasks/{id}/cancel had no test at all.
"""

import asyncio
import time

from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import Risk
from hufiagents.providers.fake import FakeProvider
from hufiagents.tools.files import FilesTool


def settings(tmp_path, **kwargs):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
        **kwargs,
    )


def wait_status(client, path, statuses):
    for _ in range(200):
        body = client.get(path).json()
        if body["status"] in statuses:
            return body
        time.sleep(0.02)
    raise AssertionError(f"did not reach {statuses}: {body}")


class ApprovalFiles(FilesTool):
    level = Risk.R3

    async def classify(self, action, params):
        await super().classify(action, params)
        return self.level


def test_approval_http_requires_correct_owner_token(tmp_path):
    config = settings(tmp_path, approval_token="s3cr3t-owner-token")
    with TestClient(create_app(config)) as client:
        with client.app.state.store.transaction() as tx:
            agent = tx.agents.get("builder")
            agent.default_risk_ceiling = Risk.R4
            tx.agents.save(agent)
        client.app.state.engine.tools = lambda workspace, task=None: {
            "files": ApprovalFiles(workspace)
        }

        response = client.post(
            "/missions", json={"outcome": "needs approval", "risk_ceiling": "R4"}
        )
        identifier = response.json()["id"]
        mission = wait_status(client, f"/missions/{identifier}", {"waiting_approval"})
        assert mission["status"] == "waiting_approval"
        approval_id = client.get("/approvals").json()[0]["id"]

        # No credential at all must not resolve the approval.
        assert client.post(f"/approvals/{approval_id}/approve", json={}).status_code == 401
        # A wrong credential must not be treated as authorized (constant-time compare path).
        wrong = client.post(
            f"/approvals/{approval_id}/approve",
            json={},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert wrong.status_code == 401
        assert client.get(f"/missions/{identifier}").json()["status"] == "waiting_approval"
        assert client.get("/approvals").json()[0]["status"] == "pending"

        # The correct owner token resolves the approval and resumes the task.
        response = client.post(
            f"/approvals/{approval_id}/approve",
            json={"note": "reviewed exact requested effect"},
            headers={"Authorization": "Bearer s3cr3t-owner-token"},
        )
        assert response.status_code == 200
        mission = wait_status(client, f"/missions/{identifier}", {"completed", "failed"})
        assert mission["status"] == "completed"


class SlowProvider(FakeProvider):
    async def complete(self, request):
        await asyncio.sleep(5)
        return await super().complete(request)


def test_cancel_via_http_interrupts_a_running_task(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config, providers={"fake": SlowProvider()})) as client:
        response = client.post("/missions", json={"outcome": "cancel me"})
        identifier = response.json()["id"]
        task_id = None
        for _ in range(200):
            tasks = client.get("/tasks", params={"mission_id": identifier}).json()
            if tasks and tasks[0]["status"] == "running":
                task_id = tasks[0]["id"]
                break
            time.sleep(0.02)
        assert task_id, "task never reached running before cancel could be tested"

        assert client.post(f"/tasks/{task_id}/cancel").status_code == 200
        mission = wait_status(client, f"/missions/{identifier}", {"cancelled"})
        assert mission["status"] == "cancelled"
        assert client.get(f"/tasks/{task_id}").json()["status"] == "cancelled"
