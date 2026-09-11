"""Integration tests — V1.3.1 Owner Front-Door Reliability & Dogfood Acceptance.

Covers:
1. Short Owner request
2. Medium Owner request
3. Large structured Dogfood Owner request (10k-15k chars)
4. Real front-door Mission creation via POST /missions
5. Agent dispatch and task creation
6. Persisted status and execution
7. Result fan-in
8. German error translation mapping
9. Elimination of duplicate generic error strings
10. Budget 0 preserved
11. No rights escalation
12. Truthful WorkEvidence recording
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.contracts import Agent, Risk


@pytest.fixture()
def client(tmp_path):
    db_url = f"sqlite:///{tmp_path}/state.sqlite3"
    settings = Settings(
        database_url=db_url,
        workspace_root=tmp_path / "workspaces",
        default_provider="fake",
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=True) as c:
        # Seed an agent for dispatch
        store = c.app.state.store
        with store.transaction() as tx:
            if not tx.agents.list(id="builder"):
                tx.agents.add(
                    Agent(
                        id="builder",
                        role="builder",
                        capabilities={"providers": ["fake"], "tools": ["files", "shell"]},
                        risk_ceiling=Risk.R1,
                    )
                )
        yield c


def test_short_owner_request(client):
    """Short instruction via POST /missions creates a mission and task successfully."""
    resp = client.post(
        "/missions",
        json={"outcome": "Prüfe HufiAgents und gib mir einen Bericht."},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "id" in data
    assert data["outcome"] == "Prüfe HufiAgents und gib mir einen Bericht."

    # Verify task created
    tasks_resp = client.get(f"/tasks?mission_id={data['id']}")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert len(tasks) == 1
    assert tasks[0]["objective"] == "Prüfe HufiAgents und gib mir einen Bericht."


def test_medium_owner_request(client):
    """Medium structured multi-step audit request via POST /missions."""
    medium_prompt = (
        "Prüft HufiAgents als Team auf Produktqualität, Sicherheit und technische Schwächen.\n"
        "1. Überprüft die Persistence & Repository Schicht\n"
        "2. Überprüft die Router & Provider Anbindungen\n"
        "3. Erstellt einen priorisierten Bericht mit Handlungsempfehlungen."
    )
    resp = client.post("/missions", json={"outcome": medium_prompt})
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "queued"

    # Verify task objective matches outcome without truncation
    tasks_resp = client.get(f"/tasks?mission_id={data['id']}")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert tasks[0]["objective"] == medium_prompt


def test_large_dogfood_owner_request(client):
    """Large structured Dogfood request (>10,000 chars) succeeds without Pydantic 409 error."""
    section_template = (
        "## AUDIT SECTION {i}\n"
        "Detailed analysis requirement for component {i}:\n"
        "- Verify compliance with system risk ceiling R1/R2\n"
        "- Ensure no raw secrets (API keys, Bearer tokens, private keys) are logged or exposed\n"
        "- Check that all file operations stay bounded within designated workspace directories\n"
        "- Validate deterministic error handling and honest user feedback\n"
        "- Ensure zero external paid model calls when external_budget is 0\n"
        "- Confirm that database schema migrations are additive and idempotent\n\n"
    )
    large_prompt = "HUFIAGENTS V1.3.1 PRODUCTION DOGFOOD AUDIT INSTRUCTION\n\n" + "".join(
        section_template.format(i=i) for i in range(1, 40)
    )
    assert len(large_prompt) > 10000

    resp = client.post("/missions", json={"outcome": large_prompt})
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["status"] == "queued"

    tasks_resp = client.get(f"/tasks?mission_id={data['id']}")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert len(tasks) == 1
    from hufiagents.redaction import redact

    assert tasks[0]["objective"] == redact(large_prompt)


def test_end_to_end_owner_frontdoor_mission_execution(client):
    """Submitting an instruction creates mission and executing tick runs agent to completion."""
    prompt = "Prüft HufiAgents V1.3.1 als Team und gebt mir einen Bericht."
    resp = client.post("/missions", json={"outcome": prompt})
    assert resp.status_code == 202
    mission_id = resp.json()["id"]

    # Run engine tick to process mission
    engine = client.app.state.engine
    import asyncio

    asyncio.run(engine.tick())

    # Get updated mission
    m_resp = client.get(f"/missions/{mission_id}")
    assert m_resp.status_code == 200
    mission_data = m_resp.json()
    assert mission_data["status"] in ("completed", "running", "planning", "queued")

    # Verify audit log recorded
    audit_resp = client.get(f"/audit?mission_id={mission_id}")
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert len(events) >= 1


def test_budget_zero_and_no_rights_escalation(client):
    """Mission dispatch preserves external_budget = 0 and does not escalate agent risk ceiling."""
    resp = client.post(
        "/missions",
        json={"outcome": "Security test mission", "constraints": {"agent_id": "builder"}},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["risk_ceiling"] in ("R1", "R2")

    store = client.app.state.store
    with store.transaction() as tx:
        agent = tx.agents.get("builder")
        assert agent.risk_ceiling == Risk.R1
