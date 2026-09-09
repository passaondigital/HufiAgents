import pytest
from fastapi.testclient import TestClient

from hufiagents.api import create_app
from hufiagents.config import Settings
from hufiagents.orchestrator.registry import AgentRegistry
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider


@pytest.fixture
def api_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/v13_api_test.sqlite3",
        workspaces_path=tmp_path / "workspaces",
        auth_enabled=False,
    )
    providers = {"fake": FakeProvider()}
    app = create_app(settings=settings, providers=providers)
    with TestClient(app) as client:
        # Seed agents
        store = app.state.store
        AgentRegistry(store).seed()
        yield client


def test_v13_api_computer_session_lifecycle(api_client):
    # Setup workspace
    sessions = api_client.post("/agents")
    ws_res = api_client.get("/agents/builder")
    assert ws_res.status_code == 200

    # Create workspace via low-level store/session helper or API
    app = api_client.app
    from hufiagents.workforce.sessions import SessionService
    sessions_svc = SessionService(app.state.store, app.state.engine.settings.workspace_root)
    ws = sessions_svc.create_workspace("builder", "builder-api-ws")
    comp = sessions_svc.prepare_computer("builder", ws.id)
    comp_id = comp.id

    res_act = api_client.post(f"/sessions/computer/{comp_id}/activate?agent_id=builder")
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "active"

    res_snap = api_client.post(f"/sessions/computer/{comp_id}/snapshot?agent_id=builder&snapshot_name=snap1")
    assert res_snap.status_code == 200
    assert res_snap.json()["status"] == "snapshot"

    res_reset = api_client.post(f"/sessions/computer/{comp_id}/reset?agent_id=builder&snapshot_name=snap1")
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "reset"

    res_rec = api_client.post(f"/sessions/computer/{comp_id}/recover?agent_id=builder")
    assert res_rec.status_code == 200
    assert res_rec.json()["status"] == "recovered"

    res_ho = api_client.post(
        f"/sessions/computer/{comp_id}/handoff",
        json={"agent_id": "builder", "target_agent_id": "reviewer", "session_id": comp_id, "summary": "check code"},
    )
    assert res_ho.status_code == 200
    assert res_ho.json()["from_agent_id"] == "builder"


def test_v13_api_browser_automation_endpoints(api_client):
    app = api_client.app
    from hufiagents.workforce.sessions import SessionService
    sessions_svc = SessionService(app.state.store, app.state.engine.settings.workspace_root)
    ws = sessions_svc.create_workspace("builder", "builder-browser-api-ws")
    browser_sess = sessions_svc.prepare_browser("builder", ws.id)
    browser_id = browser_sess.id

    res_act = api_client.post(f"/sessions/browser/{browser_id}/activate?agent_id=builder")
    assert res_act.status_code == 200

    # Navigate
    res_nav = api_client.post(
        "/browser/navigate",
        json={"agent_id": "builder", "session_id": browser_id, "url": "https://example.com/app"},
    )
    assert res_nav.status_code == 201
    assert res_nav.json()["evidence_type"] == "browser_dom"

    # Screenshot
    res_shot = api_client.post(
        "/browser/screenshot",
        json={"agent_id": "builder", "session_id": browser_id, "label": "login_view"},
    )
    assert res_shot.status_code == 201
    assert res_shot.json()["evidence_type"] == "browser_screenshot"

    # Interact
    res_act = api_client.post(
        "/browser/interact",
        json={"agent_id": "builder", "session_id": browser_id, "action": "fill", "selector": "#user", "value": "pascal"},
    )
    assert res_act.status_code == 201
    assert res_act.json()["evidence_type"] == "browser_action"


def test_v13_api_mcp_endpoints(api_client):
    # Register MCP Server
    res_srv = api_client.post(
        "/mcp/servers",
        json={
            "name": "sqlite-mcp",
            "version": "1.0",
            "transport": "stdio",
            "command_or_url": "npx -y @modelcontextprotocol/server-sqlite",
            "capabilities": ["db.query"],
            "risk_mapping": {"db.query": "R1"},
        },
    )
    assert res_srv.status_code == 201
    server_id = res_srv.json()["id"]

    # Register Tool
    res_tool = api_client.post(
        "/mcp/tools",
        json={
            "server_id": server_id,
            "name": "sql_query",
            "description": "Execute read-only SQL query",
            "risk_ceiling": "R1",
        },
    )
    assert res_tool.status_code == 201

    # List Tools
    res_list = api_client.get(f"/mcp/tools?server_id={server_id}")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # Invoke Tool
    res_inv = api_client.post(
        "/mcp/invoke",
        json={"agent_id": "builder", "tool_name": "sql_query", "params": {"query": "SELECT * FROM users"}},
    )
    assert res_inv.status_code == 201
    assert res_inv.json()["result_status"] == "ok"


def test_v13_api_connector_check_endpoints(api_client):
    # Register Connector
    with api_client.app.state.store.transaction() as tx:
        from hufiagents.contracts import ConnectorRegistration
        conn = tx.connectors.add(
            ConnectorRegistration(
                name="slack-conn",
                version="v1",
                capabilities=["chat.send"],
                modes=["write"],
                auth_state="configured",
                risk_mapping={"chat.send": "R1"},
                enabled=True,
            )
        )
        conn_id = conn.id

    # Grant Connector Access with scope
    res_grant = api_client.post(
        "/connectors/grant",
        json={
            "agent_id": "builder",
            "connector_id": conn_id,
            "capabilities": ["chat.send"],
            "modes": ["write"],
            "scopes": ["channels:write"],
            "risk_ceiling": "R1",
        },
    )
    assert res_grant.status_code == 201

    # Check Access (Valid scope)
    res_check = api_client.post(
        "/connectors/check",
        json={
            "agent_id": "builder",
            "connector_id": conn_id,
            "capability": "chat.send",
            "mode": "write",
            "required_scope": "channels:write",
        },
    )
    assert res_check.status_code == 200
    assert res_check.json()["allowed"] is True
