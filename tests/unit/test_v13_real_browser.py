"""Unit tests for V1.3 Real Browser Worker and Browser Tool."""

from __future__ import annotations

import http.server
import socketserver
import threading

import pytest

from hufiagents.browser_worker import PNG_MAGIC, BrowserWorker
from hufiagents.contracts import Risk, Task, ToolCall
from hufiagents.tools.browser import BrowserTool
from hufiagents.tools.workspace import Workspace


class _TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/isolated":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Set-Cookie", "auth_cookie=agent_secret_cookie; Path=/")
            self.end_headers()
            self.wfile.write(
                b"<!DOCTYPE html><html><body><h1>Isolated Page</h1>"
                b"<script>localStorage.setItem('agent_key', 'agent_val');</script></body></html>"
            )
            return

        if self.path == "/form":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<!DOCTYPE html><html><head><title>Form Test</title></head><body>"
                b"<h1>Form Page</h1>"
                b"<label for='uname'>Username</label>"
                b"<input id='uname' name='username' placeholder='Enter username' />"
                b"<label for='pwd'>Password</label>"
                b"<input id='pwd' type='password' name='password' />"
                b"<button id='save-btn'>Submit Form</button>"
                b"<a href='/next'>Next Page</a>"
                b"<div id='result'></div>"
                b"<script>"
                b"document.getElementById('save-btn').onclick = () => {"
                b"  const val = document.getElementById('uname').value;"
                b"  document.getElementById('result').innerText = 'Processed: ' + val;"
                b"};"
                b"</script>"
                b"</body></html>"
            )
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<!DOCTYPE html><html><head><title>Basic Page</title></head>"
            b"<body><h1>Hello World</h1></body></html>"
        )

    def log_message(self, format, *args):
        pass  # quiet test logs


@pytest.fixture(scope="module")
def local_http_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), _TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_browser_worker_lifecycle_and_diagnostics():
    worker = BrowserWorker(headless=True, allow_localhost=True)
    assert worker.browser_engine == "chromium"
    assert worker.real_process is True

    await worker.start()
    assert worker._playwright is not None
    assert worker._browser is not None
    assert "chrome" in worker.executable.lower() or "chromium" in worker.executable.lower()

    diag = worker.diagnostics()
    assert diag["browser_engine"] == "chromium"
    assert diag["real_process"] is True
    assert diag["executable"] == worker.executable
    assert diag["headless"] is True
    assert diag["active_sessions"] == 0

    await worker.stop()
    assert worker._browser is None
    assert worker._playwright is None
    assert worker.diagnostics()["real_process"] is False


@pytest.mark.asyncio
async def test_browser_worker_open_url_and_read_page(local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    try:
        res = await worker.open_url("sess-1", f"{local_http_server}/form", "agent-1")
        assert res["status"] == "ok"
        assert res["title"] == "Form Test"

        url = await worker.get_current_url("sess-1", "agent-1")
        assert "/form" in url

        title = await worker.get_title("sess-1", "agent-1")
        assert title == "Form Test"

        page_repr = await worker.read_page("sess-1", "agent-1")
        assert "Form Test" in page_repr
        assert "Buttons: Submit Form" in page_repr
        assert "Inputs:" in page_repr
        assert "Form Page" in page_repr
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_browser_worker_click_type_and_press_key(local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    try:
        await worker.open_url("sess-1", f"{local_http_server}/form", "agent-1")

        # Type text
        type_res = await worker.type("sess-1", "Enter username", "Alice", "agent-1")
        assert type_res["status"] == "ok"

        # Press key
        key_res = await worker.press_key("sess-1", "Tab", "agent-1")
        assert key_res["status"] == "ok"

        # Click button
        click_res = await worker.click("sess-1", "Submit Form", "agent-1")
        assert click_res["status"] == "ok"

        # Read page to verify JavaScript executed
        content = await worker.read_page("sess-1", "agent-1")
        assert "Processed: Alice" in content
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_browser_worker_tabs(local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    try:
        await worker.open_url("sess-tabs", f"{local_http_server}/", "agent-1", max_tabs=3)

        tabs_initial = await worker.list_tabs("sess-tabs", "agent-1")
        assert len(tabs_initial) == 1

        # New tab
        new_tab_res = await worker.new_tab(
            "sess-tabs", f"{local_http_server}/form", "agent-1", max_tabs=3
        )
        assert new_tab_res["tab_index"] == 1
        assert new_tab_res["tab_count"] == 2

        tabs = await worker.list_tabs("sess-tabs", "agent-1")
        assert len(tabs) == 2
        assert tabs[1]["active"] is True

        # Switch tab
        sw_res = await worker.switch_tab("sess-tabs", 0, "agent-1")
        assert sw_res["active_tab"] == 0

        # Max tabs limit
        await worker.new_tab("sess-tabs", None, "agent-1", max_tabs=3)
        with pytest.raises(ValueError, match="Exceeds max_tabs limit"):
            await worker.new_tab("sess-tabs", None, "agent-1", max_tabs=3)

        # Close tab
        close_res = await worker.close_tab("sess-tabs", index=2, agent_id="agent-1")
        assert close_res["tab_count"] == 2
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_browser_worker_real_png_screenshot(tmp_path, local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    try:
        await worker.open_url("sess-shot", f"{local_http_server}/form", "agent-1")

        shot_path = tmp_path / "test_screenshot.png"
        res = await worker.screenshot("sess-shot", shot_path, "form_view", "agent-1")

        assert res["status"] == "ok"
        assert shot_path.exists()
        raw_bytes = shot_path.read_bytes()
        assert len(raw_bytes) > 0
        assert raw_bytes.startswith(PNG_MAGIC)
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_browser_session_isolation(local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    try:
        # Agent A sets cookies and localStorage
        await worker.open_url("sess-a", f"{local_http_server}/isolated", "agent-a")

        # Agent B in separate session
        await worker.open_url("sess-b", f"{local_http_server}/", "agent-b")

        # Agent B attempts to access Agent A session -> rejected
        with pytest.raises(PermissionError, match="belongs to agent 'agent-a'"):
            await worker.get_current_url("sess-a", "agent-b")

        # Agent B's page checks cookies / localStorage -> isolated
        session_b = await worker._ensure_session("sess-b", "agent-b")
        storage_val = await session_b.active_page.evaluate(
            "() => localStorage.getItem('agent_key')"
        )
        assert storage_val is None

        cookies = await session_b.context.cookies()
        assert not any(c["name"] == "auth_cookie" for c in cookies)
    finally:
        await worker.stop()


def test_ssrf_and_file_url_blocking():
    worker = BrowserWorker(headless=True, allow_localhost=False)

    # file:// scheme is forbidden
    with pytest.raises(PermissionError, match="URL scheme 'file' is forbidden"):
        worker.validate_url("file:///etc/passwd")

    # loopback addresses blocked when allow_localhost=False
    with pytest.raises(PermissionError, match="Access to localhost/loopback"):
        worker.validate_url("http://localhost:8080/admin")

    with pytest.raises(PermissionError, match="Access to localhost/loopback"):
        worker.validate_url("http://127.0.0.1:3000")

    with pytest.raises(PermissionError, match="Access to private/internal"):
        worker.validate_url("http://10.0.0.1:8080")

    with pytest.raises(PermissionError, match="Access to private/internal"):
        worker.validate_url("http://192.168.1.100")


@pytest.mark.asyncio
async def test_browser_tool_classification_and_execution(tmp_path, local_http_server):
    worker = BrowserWorker(headless=True, allow_localhost=True)
    ws = Workspace(tmp_path / "tool_ws")
    task = Task(
        mission_id="mission-123",
        objective="Inspect web page",
        assigned_agent_id="agent-qa",
        allowed_tools=["browser", "files"],
    )
    tool = BrowserTool(workspace=ws, browser_worker=worker, task=task)

    # Risk classifications
    assert await tool.classify("open_url", {}) == Risk.R1
    assert await tool.classify("read_page", {}) == Risk.R1
    assert await tool.classify("click", {}) == Risk.R1
    assert await tool.classify("screenshot", {}) == Risk.R1
    assert await tool.classify("submit_destructive", {}) == Risk.R3

    with pytest.raises(PermissionError, match="Unsupported browser action"):
        await tool.classify("unsupported_action", {})

    try:
        # Execute open_url
        call_open = ToolCall(
            task_id=task.id,
            tool="browser",
            action="open_url",
            target=f"{local_http_server}/form",
            risk_class=Risk.R1,
            policy_decision="auto_allow",
            idempotency_key="key-open",
        )
        res_open = await tool.execute(call_open)
        assert res_open.result_status == "ok"
        assert "Form Test" in res_open.result_summary

        # Execute screenshot
        call_shot = ToolCall(
            task_id=task.id,
            tool="browser",
            action="screenshot",
            target="golden_shot",
            risk_class=Risk.R1,
            policy_decision="auto_allow",
            idempotency_key="key-shot",
        )
        res_shot = await tool.execute(call_shot)
        assert res_shot.result_status == "ok"
        assert "screenshots/golden_shot_" in res_shot.result_summary

        shot_files = list((tmp_path / "tool_ws" / "screenshots").glob("*.png"))
        assert len(shot_files) == 1
        assert shot_files[0].read_bytes().startswith(PNG_MAGIC)
    finally:
        await worker.stop()
