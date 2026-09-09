import pytest

from hufiagents.browser import BrowserAutomationService
from hufiagents.contracts import (
    AgentConnectorAccess,
    ConnectorRegistration,
    MCPServerRegistration,
    MCPToolDefinition,
    Risk,
)
from hufiagents.mcp import MCPAdapter
from hufiagents.orchestrator.registry import AgentRegistry
from hufiagents.persistence.repository import Store
from hufiagents.tools.workspace import Workspace
from hufiagents.workforce.connectors import ConnectorRegistry
from hufiagents.workforce.sessions import SessionService


def seeded_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/v13_state.sqlite3")
    AgentRegistry(store).seed()
    return store


def test_v13_workspace_controlled_file_ops_and_snapshots(tmp_path):
    root = tmp_path / "ws1"
    ws = Workspace(root)

    # Controlled write and read
    ws.create("hello.txt", "hello world")
    assert ws.read("hello.txt") == "hello world"

    # Overwrite control
    ws.write("hello.txt", "hello updated", overwrite=True)
    assert ws.read("hello.txt") == "hello updated"

    # File listing
    ws.create("sub/doc.txt", "doc content")
    files = ws.list_files()
    assert "hello.txt" in files
    assert "sub/doc.txt" in files

    # Snapshot and restore
    ws.snapshot("snap1")
    ws.write("hello.txt", "changed content", overwrite=True)
    assert ws.read("hello.txt") == "changed content"

    ws.restore("snap1")
    assert ws.read("hello.txt") == "hello updated"

    # Deletion
    ws.delete("sub/doc.txt")
    assert "sub/doc.txt" not in ws.list_files()


def test_v13_computer_session_full_lifecycle(tmp_path):
    store = seeded_store(tmp_path)
    sessions = SessionService(store, tmp_path / "workspaces")
    ws = sessions.create_workspace("builder", "builder-comp-ws")

    comp = sessions.prepare_computer("builder", ws.id)
    assert comp.status == "prepared"

    active_comp = sessions.activate_computer("builder", comp.id)
    assert active_comp.status == "active"

    snap_comp = sessions.snapshot_computer("builder", comp.id, "my-snap")
    assert snap_comp.status == "snapshot"
    assert snap_comp.snapshot_path is not None

    reset_comp = sessions.reset_computer("builder", comp.id, "my-snap")
    assert reset_comp.status == "reset"

    rec_comp = sessions.recover_computer("builder", comp.id)
    assert rec_comp.status == "recovered"

    handoff = sessions.handoff_computer("builder", "reviewer", comp.id)
    assert handoff.from_agent_id == "builder"
    assert handoff.to_agent_id == "reviewer"

    with store.transaction() as tx:
        saved_comp = tx.computer_sessions.get(comp.id)
        assert saved_comp.status == "handoff"
        assert saved_comp.handoff_token is not None
        events = {e.event_type for e in tx.audit.list()}
        assert events >= {
            "computer_session_prepared",
            "computer_session_activated",
            "computer_session_snapshotted",
            "computer_session_reset",
            "computer_session_recovered",
            "computer_session_handoff",
        }
    store.close()


def test_v13_browser_automation_and_work_evidence(tmp_path):
    store = seeded_store(tmp_path)
    sessions = SessionService(store, tmp_path / "workspaces")
    ws = sessions.create_workspace("builder", "builder-browser-ws")
    browser_sess = sessions.prepare_browser("builder", ws.id, memory_limit_mb=512, max_tabs=2)
    sessions.activate_browser("builder", browser_sess.id)

    browser = BrowserAutomationService(store, sessions)

    # Navigation & Evidence
    dom_ev = browser.navigate(
        "builder", browser_sess.id, "https://example.com/dashboard?token=SECRET123"
    )
    assert dom_ev.evidence_type == "browser_dom"
    assert "SECRET123" not in dom_ev.summary
    assert "SECRET123" not in dom_ev.metadata["url"]

    # Screenshot & Evidence
    shot_ev = browser.take_screenshot("builder", browser_sess.id, label="app_home")
    assert shot_ev.evidence_type == "browser_screenshot"
    assert "screenshots/app_home_" in shot_ev.artifact_ref

    # Interaction & Max Tabs
    act_ev = browser.interact("builder", browser_sess.id, "click", selector="#submit-btn")
    assert act_ev.evidence_type == "browser_action"

    # Tab count limit
    browser.interact("builder", browser_sess.id, "new_tab")
    with pytest.raises(ValueError, match="exceeds max_tabs limit"):
        browser.interact("builder", browser_sess.id, "new_tab")

    with store.transaction() as tx:
        ev_items = tx.work_evidence.list()
        assert len(ev_items) >= 3
        types = {e.evidence_type for e in ev_items}
        assert types >= {"browser_dom", "browser_screenshot", "browser_action"}
    store.close()


def test_v13_mcp_adapter_registration_discovery_and_invocation(tmp_path):
    store = seeded_store(tmp_path)
    mcp = MCPAdapter(store)

    server = mcp.register_server(
        MCPServerRegistration(
            name="github-mcp",
            version="1.0",
            transport="stdio",
            command_or_url="npx -y @modelcontextprotocol/server-github",
            capabilities=["repo.read", "issue.create"],
            risk_mapping={"repo.read": "R1", "issue.create": "R2"},
        )
    )
    assert server.status == "active"

    mcp.register_tool(
        MCPToolDefinition(
            server_id=server.id,
            name="read_repo",
            description="Read repository structure",
            risk_ceiling=Risk.R1,
        )
    )

    mcp.register_tool(
        MCPToolDefinition(
            server_id=server.id,
            name="delete_repo",
            description="High risk delete action",
            risk_ceiling=Risk.R4,
        )
    )

    tools = mcp.discover_tools(server.id)
    assert len(tools) == 2

    # Agent with R1 risk ceiling invokes R1 tool -> auto_allow
    tool_call = mcp.invoke_tool(
        "builder", "read_repo", {"repo": "owner/repo", "api_key": "SECRET-TOKEN"}
    )
    assert tool_call.result_status == "ok"
    assert "SECRET-TOKEN" not in tool_call.result_summary

    # Agent with R1 risk ceiling attempting R4 tool -> PermissionError
    with pytest.raises(PermissionError, match="exceeds agent risk ceiling"):
        mcp.invoke_tool("builder", "delete_repo", {"repo": "owner/repo"})

    with store.transaction() as tx:
        evs = tx.work_evidence.list(source_type="mcp_adapter")
        assert len(evs) == 1
        assert evs[0].evidence_type == "mcp_tool_result"
    store.close()


def test_v13_connector_permission_scopes_and_least_privilege(tmp_path):
    store = seeded_store(tmp_path)
    registry = ConnectorRegistry(store)

    github = registry.register(
        ConnectorRegistration(
            name="github-scoped",
            version="v1",
            capabilities=["repo.read", "repo.write"],
            modes=["read", "write"],
            auth_state="configured",
            risk_mapping={"repo.read": "R1", "repo.write": "R2"},
            enabled=True,
        )
    )

    # Grant with specific permission scope
    access = registry.grant(
        AgentConnectorAccess(
            agent_id="builder",
            connector_id=github.id,
            capabilities=["repo.read"],
            modes=["read"],
            scopes=["repo:read", "issue:read"],
            risk_ceiling=Risk.R1,
        )
    )
    assert access.status == "active"

    # Valid scope check passes
    assert registry.check_access(
        "builder", github.id, "repo.read", mode="read", required_scope="repo:read"
    )

    # Missing scope fails
    with pytest.raises(PermissionError, match="missing required permission scope"):
        registry.check_access(
            "builder", github.id, "repo.read", mode="read", required_scope="repo:admin"
        )

    # Unassigned agent fails even if team/org member (no implicit grants)
    with pytest.raises(PermissionError, match="no active connector access grant"):
        registry.check_access("reviewer", github.id, "repo.read", mode="read")

    store.close()
