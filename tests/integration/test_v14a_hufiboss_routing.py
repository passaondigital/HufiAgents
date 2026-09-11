"""Front-door and observable-product integration coverage for V1.4A."""

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.providers.fake import FakeProvider


class ObservableFakeProvider(FakeProvider):
    async def complete(self, request):
        await asyncio.sleep(0.08)
        return await super().complete(request)


GOLDEN = """Führe einen Multi-Agent-QA-Lauf durch.

Provider, Client und Partner sollen zuerst unabhängig prüfen.
Danach sollen sie gemeinsam Cross-Role-Szenarien ausführen.
Erstelle mir:
- Provider Report
- Client Report
- Partner Report
- Cross-Role Report
Nur reale Arbeit und Evidenz darf als abgeschlossen gelten."""


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/v14a.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        poll_interval_seconds=0.2,
        _env_file=None,
    )
    app = create_app(settings, providers={"fake": ObservableFakeProvider()})
    with TestClient(app, raise_server_exceptions=True) as value:
        yield value


def wait_for_terminal(client, mission_id, timeout=8):
    deadline = time.monotonic() + timeout
    states = []
    while time.monotonic() < deadline:
        mission = client.get(f"/missions/{mission_id}").json()
        states.append(mission["status"])
        if mission["status"] in {"completed", "failed", "cancelled"}:
            return mission, states
        time.sleep(0.02)
    pytest.fail(f"mission did not finish; states={states[-10:]}")


def test_org_unit_endpoints_are_bounded_and_recursive(client):
    units = client.get("/org-units?limit=100").json()
    assert {unit["name"] for unit in units} >= {"Hufi Group", "HufiTrust", "HufiAgents"}
    parent = next(unit for unit in units if unit["name"] == "HufiAgents")
    response = client.post(
        "/org-units",
        json={"name": "Custom Squad", "unit_type": "SQUAD", "parent_unit_id": parent["id"]},
    )
    assert response.status_code == 200
    assert response.json()["stable_key"].endswith("/custom-squad")


def test_simple_status_question_uses_one_worker(client):
    mission = client.post("/missions", json={"outcome": "Wie steht HufiAgents?"}).json()
    tasks = client.get(f"/tasks?mission_id={mission['id']}").json()
    route = mission["constraints"]["corporate_route"]
    assert len(tasks) == 1
    assert route["selected_agents"] == ["builder"]


def test_golden_mission_fanout_dependency_live_events_and_truthful_completion(client):
    response = client.post("/missions", json={"outcome": GOLDEN})
    assert response.status_code == 202
    mission = response.json()
    mission_id = mission["id"]
    tasks = client.get(f"/tasks?mission_id={mission_id}").json()
    assert len(tasks) == 4
    first = tasks[:3]
    cross_role = tasks[3]
    assert len({task["assigned_agent_id"] for task in first}) == 3
    assert all(not task["dependencies"] for task in first)
    assert set(cross_role["dependencies"]) == {task["id"] for task in first}

    initial_live = client.get(f"/company/live?mission_id={mission_id}&limit=50").json()["events"]
    assigned_tasks = {
        event["task_id"] for event in initial_live if event["event_type"] == "AGENT_ASSIGNED"
    }
    assert assigned_tasks == {task["id"] for task in tasks}
    assert not any(event["event_type"] == "OUTCOME_COMPLETED" for event in initial_live)

    completed, observed_states = wait_for_terminal(client, mission_id)
    assert completed["status"] == "completed"
    assert "HufiBoss Management-Zusammenfassung" in completed["result"]
    assert "4 Aufgaben" in completed["result"]
    outcome = client.get(f"/missions/{mission_id}/outcome").json()
    assert outcome["contract"]["status"] == "COMPLETED"
    artifacts = outcome["artifacts"]
    assert {item["deliverable_key"] for item in artifacts} == {
        "provider_report",
        "client_report",
        "partner_report",
        "cross_role_report",
    }
    assert {item["origin"] for item in artifacts} == {"AGENT_GENERATED"}

    live = client.get(f"/company/live?mission_id={mission_id}&limit=100").json()["events"]
    kinds = [event["event_type"] for event in live]
    assert {"TASK_STARTED", "HANDOFF", "REVIEW_COMPLETED", "ARTIFACT_CREATED"} <= set(kinds)
    assert "OUTCOME_COMPLETED" in kinds
    starts = {
        event["task_id"]: event["timestamp"]
        for event in live
        if event["event_type"] == "TASK_STARTED"
    }
    first_finished = [
        event["timestamp"]
        for event in live
        if event["event_type"] == "TASK_COMPLETED"
        and event["task_id"] in {task["id"] for task in first}
    ]
    assert starts[cross_role["id"]] >= max(first_finished)
    assert "running" in observed_states or "planning" in observed_states


def test_owner_input_remains_distinct_from_generated_outputs(client):
    response = client.post(
        "/missions",
        json={
            "outcome": GOLDEN,
            "constraints": {
                "input_artifacts": [
                    {"name": "Provider Report Client Report Partner Report Cross-Role Report"}
                ]
            },
        },
    )
    mission = response.json()
    outcome = client.get(f"/missions/{mission['id']}/outcome").json()
    owner_inputs = [item for item in outcome["artifacts"] if item["origin"] == "OWNER_INPUT"]
    assert len(owner_inputs) == 1
    assert owner_inputs[0]["deliverable_key"] is None
    assert not set(outcome["contract"]["required_deliverables"]) & {
        item["deliverable_key"] for item in owner_inputs
    }


def test_secret_is_redacted_across_visible_surfaces(client):
    sentinel = "FRONTDOOR_TEST_SECRET_92817"
    mission = client.post("/missions", json={"outcome": f"Prüfe diese Angabe: {sentinel}"}).json()
    assert sentinel not in str(mission)
    mission_id = mission["id"]
    assert sentinel not in client.get(f"/missions/{mission_id}").text
    assert sentinel not in client.get(f"/audit?mission_id={mission_id}").text
    assert sentinel not in client.get(f"/company/live?mission_id={mission_id}").text


def test_inactive_agent_has_no_fake_work_indicator(client):
    workforce = client.get("/company/workforce").json()
    boss = next(worker for worker in workforce["workers"] if worker["agent_id"] == "hufiboss")
    assert boss["live_state"] == "AVAILABLE"
    assert boss["active_task_count"] == 0
    assert boss["unread_event_count"] == 0


def test_frontend_truthful_language_and_accessibility_guards():
    static = Path(__file__).parents[2] / "hufiagents" / "api" / "static"
    chat = (static / "chat.js").read_text()
    css = (static / "chat.css").read_text()
    index = (static / "index.html").read_text()
    assert "Ich bereite den Auftrag vor." in chat
    assert "Mein Team arbeitet jetzt daran." in chat
    assert "visibleRedact(text)" in chat
    assert "prefers-reduced-motion" in css
    assert "HufiBoss" in index
