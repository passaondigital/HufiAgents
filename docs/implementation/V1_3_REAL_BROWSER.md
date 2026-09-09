# V1.3 Real Playwright / Chromium Browser Integration

## Overview

The V1.3 Real Browser integration gives HufiAgents the capability to automate real Chromium browser instances via Playwright within isolated per-agent contexts, enforcing strict capability guards, risk policy classification, workspace-contained screenshot artifacts, and network/SSRF protection.

## Core Architecture & Engine

- **Browser Engine**: Chromium (managed via `playwright.async_api`).
- **Browser Executable**: `/home/administrator/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome` (or system/configured Chromium executable).
- **Playwright Dependency**: Added to `pyproject.toml` and locked in `uv.lock`.
- **Process Model**: `BrowserWorker` controls a persistent Playwright runner with headless Chromium processes.
- **Controlled Diagnostics**: `BrowserWorker.diagnostics()` returns `browser_engine="chromium"`, `real_process=True`, and the verified `executable` path.

## Session Isolation & Workspace Binding

- **Isolated Browser Contexts**: Each session creates an isolated `BrowserContext` (`browser.new_context()`). Sessions do not share cookies, `localStorage`, `sessionStorage`, history, or open tabs.
- **Session Ownership**: Access is gated strictly by `agent_id` and session ownership. Cross-agent context hijacking is rejected with `PermissionError`.
- **Workspace Binding**: Artifacts (such as PNG screenshots) are written strictly inside the assigned task workspace (`workspaces/<mission_id>/screenshots/`).

## Supported Browser Actions

1. `open_url` / `navigate`: Navigates the active tab to the specified URL after SSRF validation.
2. `get_current_url`: Retrieves the URL of the active tab.
3. `get_title`: Retrieves the document title of the active tab.
4. `read_page`: Returns a structured representation of visible content and interactive elements (`buttons`, `inputs`, `links`, body text) bounded by `max_chars`.
5. `click`: Clicks elements using semantic selectors (`get_by_role("button")`, `get_by_role("link")`, `get_by_text()`, `get_by_label()`) with CSS selector fallback.
6. `type` / `fill`: Fills input fields using semantic selectors (`get_by_label()`, `get_by_placeholder()`, `get_by_role("textbox")`) with CSS fallback.
7. `press_key`: Dispatches keyboard key events (`Enter`, `Tab`, etc.).
8. `wait_for`: Waits for an explicit selector or timeout.
9. `new_tab`: Opens an additional tab within the session context (bounded by `max_tabs`).
10. `list_tabs`: Lists all open tabs with URLs, titles, and active indicators.
11. `switch_tab`: Brings a specified tab index to the front.
12. `close_tab`: Closes a tab while maintaining active session tab invariants.
13. `screenshot`: Captures a real PNG screenshot and verifies the PNG magic bytes (`PNG

`).

## Security & Governance

### SSRF & Network Policy
- Rejects non-HTTP/HTTPS schemes (including `file://`, `data:`, `javascript:`).
- Rejects loopback addresses (`127.0.0.1`, `::1`, `localhost`, `0.0.0.0`), private RFC1918 subnets, and link-local/cloud-metadata addresses.
- `allow_localhost=True` is only enabled in explicit test fixture configurations and is disabled by default in production.

### Capability Guard & Least Privilege
- Only agents with the `"browser"` tool capability in their profile/task configuration can invoke browser actions via `ToolGateway`.
- Team, Project, or Room membership alone does not grant browser execution rights.

### Risk Policy & Approvals
- Read/navigation and standard form interactions are classified as `Risk.R1` (auto-allow).
- Potentially destructive browser operations (such as account deletion or publish operations) are classified as `Risk.R3` (approval required).

### Secret Redaction
- Sensitive typed inputs (e.g. passwords, API keys, tokens like `browser-secret-999`) are never persisted in raw form to `WorkEvidence`, audit logs, room messages, or task results.

### Resource Cleanup
- `BrowserWorker.stop()` and `BrowserWorker.close_session()` cleanly close owned pages, contexts, and Chromium processes, leaving no orphaned browser processes.

## Normal Agent Runtime Integration

The browser automation is exposed via `BrowserTool` in `hufiagents/tools/browser.py` and registered with the standard `Orchestrator` tool dictionary. Missions created directly, dispatched from Room chats, or scheduled from Routines execute through the standard `ToolGateway` without special golden-test paths.

## Known Limitations

- Persistent browser cookies and session state are retained in-memory per session lifecycle and are not serialized across complete application restarts.
- Full desktop/GUI desktop control (e.g. X11/Wayland/VNC) is not supported; browser actions operate strictly in headless Chromium.
