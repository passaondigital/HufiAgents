"""Integration tests for V1.3 Real Browser Worker and Runtime Integration."""

from __future__ import annotations

import http.server
import socketserver
import threading

import pytest

from hufiagents.browser_worker import PNG_MAGIC, BrowserWorker
from hufiagents.config import Settings
from hufiagents.contracts import (
    Agent,
    AgentProvisioningRequest,
    Mission,
    Risk,
    State,
    Task,
    ToolCall,
)
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.persistence.repository import Store
from hufiagents.tools.browser import BrowserTool
from hufiagents.tools.workspace import Workspace
from hufiagents.workforce.builder import WorkforceBuilder


class _GoldenServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/golden":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<!DOCTYPE html><html><head><title>Golden Test</title></head><body>"
                b"<h1>Hufi Browser Golden Test</h1>"
                b"<label for='name-input'>Name</label>"
                b"<input id='name-input' name='name' placeholder='Name' />"
                b"<button id='save-btn'>Speichern</button>"
                b"<div id='output'></div>"
                b"<script>"
                b"document.getElementById('save-btn').onclick = () => {"
                b"  const val = document.getElementById('name-input').value;"
                b"  document.getElementById('output').innerText = 'Gespeichert: ' + val;"
                b"};"
                b"</script>"
                b"</body></html>"
            )
            return

        if self.path == "/secret-form":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<!DOCTYPE html><html><body>"
                b"<input id='secret-field' type='password' name='password' "
                b"placeholder='Password' />"
                b"<button id='login-btn'>Login</button>"
                b"</body></html>"
            )
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<!DOCTYPE html><html><head><title>Second Tab</title></head>"
            b"<body><h1>Second Tab Page</h1></body></html>"
        )

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def golden_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), _GoldenServerHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()


@pytest.fixture()
def store(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.sqlite3"
    s = Store(db_url)
    yield s
    s.close()


@pytest.mark.asyncio
async def test_golden_real_browser_flow(tmp_path, golden_server):
    """Full Golden Real Browser Test:

    1. Launch REAL Chromium
    2. Open test page
    3. Verify heading
    4. Type: Pascal
    5. Click: Speichern
    6. Verify: Gespeichert: Pascal
    7. Open second tab
    8. List/switch tabs
    9. Create screenshot
    10. Verify screenshot is real PNG with magic bytes
    11. Close browser cleanly
    """
    worker = BrowserWorker(headless=True, allow_localhost=True)
    assert worker.browser_engine == "chromium"
    assert worker.real_process is True

    try:
        session_id = "golden-session-001"
        agent_id = "agent-pascal"

        # 1 & 2: Open test page
        nav_res = await worker.open_url(session_id, f"{golden_server}/golden", agent_id)
        assert nav_res["status"] == "ok"
        assert nav_res["title"] == "Golden Test"

        # 3: Verify heading in page content
        page_content = await worker.read_page(session_id, agent_id)
        assert "Hufi Browser Golden Test" in page_content
        assert "Buttons: Speichern" in page_content

        # 4: Type "Pascal"
        type_res = await worker.type(session_id, "Name", "Pascal", agent_id)
        assert type_res["status"] == "ok"

        # 5: Click "Speichern"
        click_res = await worker.click(session_id, "Speichern", agent_id)
        assert click_res["status"] == "ok"

        # 6: Verify "Gespeichert: Pascal"
        updated_content = await worker.read_page(session_id, agent_id)
        assert "Gespeichert: Pascal" in updated_content

        # 7: Open second tab
        new_tab_res = await worker.new_tab(
            session_id, f"{golden_server}/second", agent_id, max_tabs=4
        )
        assert new_tab_res["tab_index"] == 1
        assert new_tab_res["tab_count"] == 2

        # 8: List & switch tabs
        tabs = await worker.list_tabs(session_id, agent_id)
        assert len(tabs) == 2
        assert tabs[1]["active"] is True

        sw_res = await worker.switch_tab(session_id, 0, agent_id)
        assert sw_res["active_tab"] == 0

        # 9 & 10: Create and verify real PNG screenshot
        shot_path = tmp_path / "golden_screenshot.png"
        shot_res = await worker.screenshot(session_id, shot_path, "golden_verification", agent_id)
        assert shot_res["status"] == "ok"
        assert shot_path.exists()

        png_bytes = shot_path.read_bytes()
        assert len(png_bytes) > 0
        assert png_bytes.startswith(PNG_MAGIC)
    finally:
        # 11: Close browser cleanly
        await worker.stop()
        assert worker._browser is None


@pytest.mark.asyncio
async def test_agent_browser_capability_guard_and_tool_gateway(tmp_path, store, golden_server):
    """Prove capability gating:

    - Agent with browser capability can invoke BrowserTool via ToolGateway
    - Agent without browser capability is DENIED
    - Team membership does not grant browser capability
    """
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/test_guard.sqlite3",
        workspace_root=tmp_path / "workspaces",
        browser_allow_localhost=True,
    )
    engine = Orchestrator(store, settings)

    with store.transaction() as tx:
        tx.missions.add(Mission(id="mission-guard", outcome="Guard mission outcome"))
        # Agent with browser capability
        browser_agent = Agent(
            id="agent-browser",
            role="Browser Tester",
            capabilities={"tools": ["browser", "files"]},
            risk_ceiling=Risk.R1,
        )
        tx.agents.add(browser_agent)

        # Agent without browser capability
        restricted_agent = Agent(
            id="agent-restricted",
            role="Restricted Worker",
            capabilities={"tools": ["files"]},
            risk_ceiling=Risk.R1,
        )
        tx.agents.add(restricted_agent)

        # Running task with browser tool allowed
        task = Task(
            mission_id="mission-guard",
            objective="Perform browser navigation",
            status=State.running,
            assigned_agent_id="agent-browser",
            allowed_tools=["browser", "files"],
            risk_ceiling=Risk.R1,
        )
        tx.tasks.add(task)

    ws = Workspace(tmp_path / "workspaces" / "mission-guard")
    tools = engine.tools(ws, task)
    browser_tool = tools["browser"]

    # 1. Allowed agent succeeds
    res = await engine.gateway.invoke(
        task,
        browser_agent,
        browser_tool,
        "open_url",
        f"{golden_server}/golden",
        {"url": f"{golden_server}/golden"},
    )
    assert res.result_status == "ok"

    # 2. Restricted agent is denied before action
    with pytest.raises(PermissionError, match="tool not authorized by capability/risk policy"):
        await engine.gateway.invoke(
            task,
            restricted_agent,
            browser_tool,
            "open_url",
            f"{golden_server}/restricted",
            {"url": f"{golden_server}/restricted"},
        )

    # 3. Team membership does NOT grant browser capability
    builder = WorkforceBuilder(store)
    builder.assign_team(restricted_agent.id, "team-qa")

    with pytest.raises(PermissionError, match="tool not authorized by capability/risk policy"):
        await engine.gateway.invoke(
            task,
            restricted_agent,
            browser_tool,
            "open_url",
            f"{golden_server}/team-qa",
            {"url": f"{golden_server}/team-qa"},
        )

    await engine.stop()


@pytest.mark.asyncio
async def test_workforce_builder_browser_provisioning_and_execution(tmp_path, store, golden_server):
    """Provision a browser-capable agent and verify it can execute browser tasks."""
    builder = WorkforceBuilder(store)
    req = AgentProvisioningRequest(
        display_name="QA Browser Bot",
        role="qa-browser",
        capabilities={"tools": ["browser", "files"], "providers": ["local"]},
        risk_ceiling=Risk.R1,
    )
    agent = builder.provision(
        req,
        caller_capabilities={"tools": ["browser", "files"], "providers": ["local"]},
    )
    assert agent.role == "qa-browser"
    assert "browser" in agent.capabilities.get("tools", [])

    ws = Workspace(tmp_path / "ws_prov")
    worker = BrowserWorker(headless=True, allow_localhost=True)
    task = Task(
        mission_id="mission-prov",
        objective="Verify provisioned agent browser use",
        assigned_agent_id=agent.id,
        allowed_tools=["browser", "files"],
    )
    tool = BrowserTool(workspace=ws, browser_worker=worker, store=store, task=task)

    try:
        call = ToolCall(
            task_id=task.id,
            tool="browser",
            action="open_url",
            target=f"{golden_server}/golden",
            risk_class=Risk.R1,
            policy_decision="auto_allow",
            idempotency_key="key-prov-open",
        )
        res = await tool.execute(call)
        assert res.result_status == "ok"
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_secret_redaction_during_browser_interaction(tmp_path, store, golden_server):
    """Verify that sensitive secrets (e.g. browser-secret-999) are never logged unredacted."""
    with store.transaction() as tx:
        tx.missions.add(Mission(id="mission-sec", outcome="Secret testing mission"))
    worker = BrowserWorker(headless=True, allow_localhost=True)
    ws = Workspace(tmp_path / "ws_secret")
    task = Task(
        mission_id="mission-sec",
        objective="Fill credentials safely",
        assigned_agent_id="agent-sec",
        allowed_tools=["browser"],
    )
    tool = BrowserTool(workspace=ws, browser_worker=worker, store=store, task=task)

    try:
        # Open secret form
        call_open = ToolCall(
            task_id=task.id,
            tool="browser",
            action="open_url",
            target=f"{golden_server}/secret-form",
            risk_class=Risk.R1,
            policy_decision="auto_allow",
            idempotency_key="key-sec-open",
        )
        await tool.execute(call_open)

        # Type secret value specified in requirement: browser-secret-999
        secret_val = "browser-secret-999"
        call_type = ToolCall(
            task_id=task.id,
            tool="browser",
            action="type",
            target="Password",
            params={"selector": "Password", "text": secret_val},
            risk_class=Risk.R1,
            policy_decision="auto_allow",
            idempotency_key="key-sec-type",
        )
        res_type = await tool.execute(call_type)
        assert res_type.result_status == "ok"
        assert secret_val not in res_type.result_summary

        # Check that the raw secret is never present in WorkEvidence or audit logs
        with store.transaction() as tx:
            evidence_items = tx.work_evidence.list(mission_id="mission-sec")
            for item in evidence_items:
                assert secret_val not in (item.summary or "")
                assert secret_val not in (item.content or "")
                assert secret_val not in str(item.metadata or {})

            audit_items = tx.audit.list()
            for a in audit_items:
                assert secret_val not in str(a.detail or {})
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_room_and_routine_browser_integration(tmp_path, store, golden_server):
    """Test Room and Routine integration with real browser-capable agent."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/test_room_browser.sqlite3",
        workspace_root=tmp_path / "workspaces",
        browser_allow_localhost=True,
    )
    engine = Orchestrator(store, settings)

    with store.transaction() as tx:
        # 1. Provision browser agent
        agent = Agent(
            id="agent-browser-bot",
            role="Browser Operator",
            capabilities={"tools": ["browser", "files"]},
            risk_ceiling=Risk.R1,
        )
        tx.agents.add(agent)

        # 2. Create mission with room constraint
        mission = Mission(
            id="mission-room-browser",
            outcome="Execute browser check for room",
            constraints={"room_id": "room-ops"},
        )
        tx.missions.add(mission)

        task = Task(
            mission_id=mission.id,
            objective="Navigate golden page and capture screenshot",
            assigned_agent_id=agent.id,
            allowed_tools=["browser", "files"],
            risk_ceiling=Risk.R1,
            status=State.running,
        )
        tx.tasks.add(task)

    ws = Workspace(tmp_path / "workspaces" / mission.id)
    tools = engine.tools(ws, task)
    browser_tool = tools["browser"]

    # Execute browser navigation
    nav_res = await engine.gateway.invoke(
        task,
        agent,
        browser_tool,
        "open_url",
        f"{golden_server}/golden",
        {"url": f"{golden_server}/golden"},
    )
    assert nav_res.result_status == "ok"

    # Execute screenshot
    shot_res = await engine.gateway.invoke(
        task,
        agent,
        browser_tool,
        "screenshot",
        "room_check",
        {"label": "room_check"},
    )
    assert shot_res.result_status == "ok"

    # Verify screenshot file exists in workspace
    png_files = list(ws.root.glob("screenshots/*.png"))
    assert len(png_files) >= 1
    assert png_files[0].read_bytes().startswith(PNG_MAGIC)

    await engine.stop()
