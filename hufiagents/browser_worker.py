"""V1.3 Real Playwright / Chromium Browser Worker.

Controls headless Chromium instances, manages isolated browser contexts per agent session,
enforces strict SSRF and network isolation policies, captures real PNG screenshots,
and ensures complete process cleanup.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from hufiagents.redaction import redact

logger = logging.getLogger(__name__)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass
class SessionState:
    agent_id: str
    workspace_id: str
    context: BrowserContext
    pages: list[Page] = field(default_factory=list)
    active_index: int = 0
    max_tabs: int = 5
    created_at: float = field(default_factory=time.time)

    @property
    def active_page(self) -> Page:
        if not self.pages:
            raise RuntimeError("No active pages in browser session")
        if self.active_index >= len(self.pages):
            self.active_index = len(self.pages) - 1
        return self.pages[self.active_index]


class BrowserWorker:
    """Manages real Chromium processes and per-session isolated contexts."""

    def __init__(
        self,
        *,
        headless: bool = True,
        allow_localhost: bool = False,
        executable_path: str | None = None,
    ):
        self.headless = headless
        self.allow_localhost = allow_localhost
        self.executable_path = executable_path
        self.browser_engine = "chromium"
        self.real_process = True

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    @property
    def executable(self) -> str:
        """Return the path to the real Chromium executable."""
        if self._playwright:
            return self._playwright.chromium.executable_path
        return self.executable_path or ""

    def diagnostics(self) -> dict[str, Any]:
        """Return controlled proof of real browser engine and process status."""
        return {
            "browser_engine": self.browser_engine,
            "real_process": bool(self.real_process and self._browser is not None),
            "executable": self.executable,
            "headless": self.headless,
            "active_sessions": len(self._sessions),
        }

    async def start(self) -> None:
        """Start Playwright and launch the Chromium process."""
        async with self._lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self._browser is None:
                launch_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
                kwargs: dict[str, Any] = {
                    "headless": self.headless,
                    "args": launch_args,
                }
                if self.executable_path:
                    kwargs["executable_path"] = self.executable_path
                self._browser = await self._playwright.chromium.launch(**kwargs)

    async def stop(self) -> None:
        """Close all sessions, close Chromium, and stop Playwright cleanly."""
        async with self._lock:
            for session_id, state in list(self._sessions.items()):
                try:
                    for p in state.pages:
                        if not p.is_closed():
                            await p.close()
                    await state.context.close()
                except Exception as exc:
                    logger.debug("Error closing session %s: %s", session_id, exc)
            self._sessions.clear()

            if self._browser:
                try:
                    await self._browser.close()
                except Exception as exc:
                    logger.debug("Error closing browser: %s", exc)
                self._browser = None

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as exc:
                    logger.debug("Error stopping playwright: %s", exc)
                self._playwright = None

    async def close_all(self) -> None:
        await self.stop()

    async def close_session(self, session_id: str) -> None:
        """Close an isolated session context and its associated pages."""
        async with self._lock:
            state = self._sessions.pop(session_id, None)
            if state:
                for p in state.pages:
                    if not p.is_closed():
                        try:
                            await p.close()
                        except Exception:
                            pass
                try:
                    await state.context.close()
                except Exception:
                    pass

    def validate_url(self, url: str) -> str:
        """Validate URL against SSRF and forbidden scheme policies.

        - Rejects file://, data:, javascript:, and other non-http/https schemes unconditionally.
        - Blocks loopback, private, link-local, and internal addresses unless allow_localhost=True.
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        url_stripped = url.strip()
        parsed = urlsplit(url_stripped)

        if parsed.scheme.lower() not in {"http", "https"}:
            raise PermissionError(
                f"URL scheme '{parsed.scheme}' is forbidden; only http and https are allowed"
            )

        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid URL without hostname: '{url_stripped}'")

        host_lower = hostname.lower()

        # Check explicit loopback hostnames
        if host_lower in {"localhost", "127.0.0.1", "::1", "0.0.0.0"} or host_lower.endswith(
            ".localhost"
        ):
            if not self.allow_localhost:
                raise PermissionError(
                    f"Access to localhost/loopback address '{hostname}' "
                    "is blocked by security policy"
                )
            return url_stripped

        # Check IP literal or resolve hostname
        try:
            ip = ipaddress.ip_address(host_lower)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                if not self.allow_localhost:
                    raise PermissionError(
                        f"Access to private/internal IP address '{hostname}' "
                        "is blocked by security policy"
                    )
            return url_stripped
        except ValueError:
            # Not an IP literal - check DNS resolution if not in test mode
            if not self.allow_localhost:
                try:
                    addr_info = socket.getaddrinfo(hostname, None)
                    for _family, _, _, _, sockaddr in addr_info:
                        ip_str = sockaddr[0]
                        resolved_ip = ipaddress.ip_address(ip_str)
                        if (
                            resolved_ip.is_loopback
                            or resolved_ip.is_private
                            or resolved_ip.is_link_local
                            or resolved_ip.is_reserved
                            or resolved_ip.is_multicast
                        ):
                            raise PermissionError(
                                f"Access to private/internal address '{hostname}' ({ip_str}) "
                                "is blocked by security policy"
                            )
                except socket.gaierror:
                    # DNS resolution failed; Playwright will handle connection failure
                    pass

        return url_stripped

    async def _ensure_session(
        self,
        session_id: str,
        agent_id: str,
        workspace_id: str = "",
        max_tabs: int = 5,
    ) -> SessionState:
        """Retrieve existing isolated session or create a new isolated browser context."""
        if not self._browser or not self._playwright:
            await self.start()

        assert self._browser is not None

        if session_id in self._sessions:
            state = self._sessions[session_id]
            if state.agent_id != agent_id:
                raise PermissionError(
                    f"Session '{session_id}' belongs to agent '{state.agent_id}', not '{agent_id}'"
                )
            return state

        async with self._lock:
            # Double check inside lock
            if session_id in self._sessions:
                state = self._sessions[session_id]
                if state.agent_id != agent_id:
                    raise PermissionError(f"Session '{session_id}' belongs to another agent")
                return state

            # Create isolated context
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="HufiAgents-BrowserWorker/1.3 (Automated Agent; Linux x86_64)",
                ignore_https_errors=True if self.allow_localhost else False,
            )
            page = await context.new_page()
            state = SessionState(
                agent_id=agent_id,
                workspace_id=workspace_id,
                context=context,
                pages=[page],
                active_index=0,
                max_tabs=max(1, min(max_tabs, 8)),
            )
            self._sessions[session_id] = state
            return state

    async def open_url(
        self,
        session_id: str,
        url: str,
        agent_id: str,
        workspace_id: str = "",
        max_tabs: int = 5,
        timeout_ms: int = 20000,
    ) -> dict[str, Any]:
        """Navigate active tab to the specified URL after SSRF validation."""
        clean_url = self.validate_url(url)
        session = await self._ensure_session(session_id, agent_id, workspace_id, max_tabs)
        page = session.active_page

        response = await page.goto(clean_url, wait_until="domcontentloaded", timeout=timeout_ms)
        title = await page.title()
        return {
            "status": "ok",
            "url": page.url,
            "title": title,
            "http_status": response.status if response else None,
        }

    async def get_current_url(self, session_id: str, agent_id: str) -> str:
        """Return the URL of the active tab."""
        session = await self._ensure_session(session_id, agent_id)
        return session.active_page.url

    async def get_title(self, session_id: str, agent_id: str) -> str:
        """Return the page title of the active tab."""
        session = await self._ensure_session(session_id, agent_id)
        return await session.active_page.title()

    async def read_page(
        self,
        session_id: str,
        agent_id: str,
        max_chars: int = 4000,
    ) -> str:
        """Return bounded structured representation of visible content & interactive elements."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page

        title = await page.title()
        url = page.url

        # Extract text and element metadata using DOM evaluation
        dom_info = await page.evaluate(
            """() => {
                const bodyText = document.body ? document.body.innerText.trim() : '';

                const btnSel = (
                    'button, input[type="button"], input[type="submit"], [role="button"]'
                );
                const buttons = Array.from(document.querySelectorAll(btnSel))
                    .map(el => {
                        const aria = el.getAttribute('aria-label');
                        return el.innerText || el.value || aria || el.id || '';
                    })
                    .filter(t => t.trim().length > 0)
                    .slice(0, 15);

                const inputs = Array.from(document.querySelectorAll('input, textarea, select'))
                    .map(el => {
                        const type = el.getAttribute('type') || el.tagName.toLowerCase();
                        const n = el.getAttribute('name') || el.getAttribute('placeholder');
                        const name = n || el.getAttribute('aria-label') || el.id || '';
                        return `${name} (type=${type})`;
                    })
                    .filter(t => t.length > 0)
                    .slice(0, 15);

                const links = Array.from(document.querySelectorAll('a[href]'))
                    .map(el => {
                        const text = el.innerText.trim();
                        const href = el.getAttribute('href');
                        return text ? `[${text}](${href})` : href;
                    })
                    .filter(t => t && t.length > 0)
                    .slice(0, 15);

                return { bodyText, buttons, inputs, links };
            }"""
        )

        body_text = dom_info.get("bodyText", "")
        buttons = dom_info.get("buttons", [])
        inputs = dom_info.get("inputs", [])
        links = dom_info.get("links", [])

        elements_summary = []
        if buttons:
            elements_summary.append(f"Buttons: {', '.join(buttons)}")
        if inputs:
            elements_summary.append(f"Inputs: {', '.join(inputs)}")
        if links:
            elements_summary.append(f"Links: {', '.join(links[:8])}")

        interactive_block = "\n".join(elements_summary) if elements_summary else "None detected"

        output = (
            f"Title: {title}\n"
            f"URL: {url}\n\n"
            f"Interactive Elements:\n{interactive_block}\n\n"
            f"Page Content:\n{body_text}"
        )

        if len(output) > max_chars:
            output = output[:max_chars] + "\n... [Content truncated to character limit]"

        return output

    async def click(
        self,
        session_id: str,
        selector: str,
        agent_id: str,
        timeout_ms: int = 5000,
    ) -> dict[str, Any]:
        """Click an element using semantic selectors or CSS fallback."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page

        locator = None
        # Try semantic match: button by role/name
        try:
            btn = page.get_by_role("button", name=selector)
            if await btn.count() > 0:
                locator = btn.first
        except Exception:
            pass

        # Try semantic match: link by role/name
        if locator is None:
            try:
                lnk = page.get_by_role("link", name=selector)
                if await lnk.count() > 0:
                    locator = lnk.first
            except Exception:
                pass

        # Try semantic match: text
        if locator is None:
            try:
                txt = page.get_by_text(selector, exact=False)
                if await txt.count() > 0:
                    locator = txt.first
            except Exception:
                pass

        # Try semantic match: label
        if locator is None:
            try:
                lbl = page.get_by_label(selector)
                if await lbl.count() > 0:
                    locator = lbl.first
            except Exception:
                pass

        # Direct locator / CSS fallback
        if locator is None:
            locator = page.locator(selector).first

        await locator.click(timeout=timeout_ms)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=2000)
        except Exception:
            pass

        return {
            "status": "ok",
            "url": page.url,
            "title": await page.title(),
            "clicked": selector,
        }

    async def type(
        self,
        session_id: str,
        selector: str,
        text: str,
        agent_id: str,
        timeout_ms: int = 5000,
    ) -> dict[str, Any]:
        """Fill an input field with text using semantic or CSS selectors."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page

        locator = None
        try:
            lbl = page.get_by_label(selector)
            if await lbl.count() > 0:
                locator = lbl.first
        except Exception:
            pass

        if locator is None:
            try:
                ph = page.get_by_placeholder(selector)
                if await ph.count() > 0:
                    locator = ph.first
            except Exception:
                pass

        if locator is None:
            try:
                tb = page.get_by_role("textbox", name=selector)
                if await tb.count() > 0:
                    locator = tb.first
            except Exception:
                pass

        if locator is None:
            locator = page.locator(selector).first

        await locator.fill(text, timeout=timeout_ms)
        return {
            "status": "ok",
            "selector": selector,
            "typed_chars": len(text),
        }

    async def press_key(
        self,
        session_id: str,
        key: str,
        agent_id: str,
    ) -> dict[str, Any]:
        """Press a keyboard key on the active page."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page
        await page.keyboard.press(key)
        return {"status": "ok", "key": key}

    async def wait_for(
        self,
        session_id: str,
        selector: str | None = None,
        timeout_ms: int = 5000,
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Wait for a selector or timeout in milliseconds."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page
        if selector:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return {"status": "ok", "waited_for": selector}
        await page.wait_for_timeout(timeout_ms)
        return {"status": "ok", "waited_for": f"{timeout_ms}ms"}

    async def new_tab(
        self,
        session_id: str,
        url: str | None = None,
        agent_id: str = "",
        workspace_id: str = "",
        max_tabs: int = 5,
    ) -> dict[str, Any]:
        """Open a new tab in the session context, enforcing max_tabs limit."""
        session = await self._ensure_session(session_id, agent_id, workspace_id, max_tabs)
        if len(session.pages) >= session.max_tabs:
            raise ValueError(f"Exceeds max_tabs limit of {session.max_tabs}")

        page = await session.context.new_page()
        session.pages.append(page)
        session.active_index = len(session.pages) - 1

        title = ""
        current_url = page.url
        if url:
            res = await self.open_url(session_id, url, agent_id, workspace_id, max_tabs)
            title = res.get("title", "")
            current_url = res.get("url", page.url)

        return {
            "status": "ok",
            "tab_index": session.active_index,
            "tab_count": len(session.pages),
            "url": current_url,
            "title": title,
        }

    async def list_tabs(self, session_id: str, agent_id: str) -> list[dict[str, Any]]:
        """List all open tabs in the session context."""
        session = await self._ensure_session(session_id, agent_id)
        tabs = []
        for idx, page in enumerate(session.pages):
            title = await page.title()
            tabs.append(
                {
                    "index": idx,
                    "url": page.url,
                    "title": title,
                    "active": idx == session.active_index,
                }
            )
        return tabs

    async def switch_tab(self, session_id: str, index: int, agent_id: str) -> dict[str, Any]:
        """Switch the active tab to the specified index."""
        session = await self._ensure_session(session_id, agent_id)
        if index < 0 or index >= len(session.pages):
            raise ValueError(
                f"Invalid tab index {index}; valid indices: 0..{len(session.pages) - 1}"
            )
        session.active_index = index
        page = session.active_page
        await page.bring_to_front()
        return {
            "status": "ok",
            "active_tab": index,
            "url": page.url,
            "title": await page.title(),
        }

    async def close_tab(
        self,
        session_id: str,
        index: int | None = None,
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Close a specific tab or the active tab."""
        session = await self._ensure_session(session_id, agent_id)
        if len(session.pages) <= 1:
            raise ValueError("Cannot close the only open tab in browser session")

        target_index = session.active_index if index is None else index
        if target_index < 0 or target_index >= len(session.pages):
            raise ValueError(f"Invalid tab index {target_index}")

        page_to_close = session.pages.pop(target_index)
        if not page_to_close.is_closed():
            await page_to_close.close()

        if session.active_index >= len(session.pages):
            session.active_index = len(session.pages) - 1

        active_page = session.active_page
        return {
            "status": "ok",
            "tab_count": len(session.pages),
            "active_tab": session.active_index,
            "url": active_page.url,
        }

    async def screenshot(
        self,
        session_id: str,
        destination_path: Path | str,
        label: str = "screenshot",
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Capture a real PNG screenshot and save it to the destination path."""
        session = await self._ensure_session(session_id, agent_id)
        page = session.active_page

        dest = Path(destination_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        png_bytes = await page.screenshot(path=str(dest), full_page=False)

        # Validate PNG magic bytes and non-zero size
        if not png_bytes.startswith(PNG_MAGIC) or len(png_bytes) == 0:
            raise RuntimeError("Captured screenshot is not a valid PNG")

        return {
            "status": "ok",
            "path": str(dest),
            "size_bytes": len(png_bytes),
            "label": redact(label),
            "url": page.url,
        }
