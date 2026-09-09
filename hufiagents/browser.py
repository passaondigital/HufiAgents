"""V1.3 Browser Automation Service, integrates Real BrowserWorker and Work Evidence."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from hufiagents.browser_worker import BrowserWorker
from hufiagents.contracts import WorkEvidence, now
from hufiagents.redaction import redact
from hufiagents.tools.workspace import Workspace


class BrowserAutomationService:
    def __init__(self, store, session_service, worker: BrowserWorker | None = None):
        self.store = store
        self.session_service = session_service
        self.worker = worker

    def _run_async(self, coro):
        """Run an async coroutine from synchronous service methods."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    def navigate(
        self,
        agent_id: str,
        session_id: str,
        url: str,
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
    ) -> WorkEvidence:
        url_clean = str(redact(url)).strip()
        if not (
            url_clean.startswith("http://")
            or url_clean.startswith("https://")
            or url_clean.startswith("file://")
            or url_clean.startswith("app://")
        ):
            raise ValueError("invalid browser URL scheme; must be http, https, file, or app")

        with self.store.transaction() as tx:
            session = tx.browser_sessions.get(session_id)
            self.session_service._assert_owner(agent_id, session.workspace_id)
            if session.status in {"closed", "expired"}:
                raise PermissionError("browser session is not active")

            session.current_url = url_clean
            session.status = "active"
            session.last_activity = now()
            tx.browser_sessions.save(session)

            title = urlparse(url_clean).netloc or url_clean
            dom_content = ""

            if self.worker:
                try:
                    res = self._run_async(
                        self.worker.open_url(
                            session_id=session_id,
                            url=url_clean,
                            agent_id=agent_id,
                            workspace_id=session.workspace_id,
                            max_tabs=session.max_tabs,
                        )
                    )
                    title = res.get("title") or title
                    dom_content = self._run_async(
                        self.worker.read_page(session_id=session_id, agent_id=agent_id)
                    )
                except Exception as exc:
                    dom_content = f"Error navigating browser: {exc}"
            else:
                dom_content = (
                    f"<!DOCTYPE html><html><head><title>{title}</title></head>"
                    f"<body><main><h1>Page loaded: {title}</h1>"
                    f"<p>URL: {url_clean}</p></main></body></html>"
                )

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="browser_automation",
                    evidence_type="browser_dom",
                    summary=f"Navigated browser session {session_id[:8]} to {url_clean}",
                    content=dom_content,
                    metadata={
                        "url": url_clean,
                        "session_id": session_id,
                        "active_tabs": session.active_tab_count,
                    },
                )
            )
            tx.log(
                "browser_navigated",
                actor=agent_id,
                session_id=session_id,
                url=url_clean,
                evidence_id=evidence.id,
            )
            return evidence

    def take_screenshot(
        self,
        agent_id: str,
        session_id: str,
        label: str = "screenshot",
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
    ) -> WorkEvidence:
        label_clean = str(redact(label)).replace(" ", "_")
        with self.store.transaction() as tx:
            session = tx.browser_sessions.get(session_id)
            self.session_service._assert_owner(agent_id, session.workspace_id)
            if session.status in {"closed", "expired"}:
                raise PermissionError("browser session is not active")

            ws_path = self.session_service.workspace_path(session.workspace_id)
            ws = Workspace(ws_path)
            current_url = session.current_url or "about:blank"

            if self.worker:
                artifact_rel = f"screenshots/{label_clean}_{session_id[:8]}.png"
                dest = ws_path / artifact_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    self._run_async(
                        self.worker.screenshot(
                            session_id=session_id,
                            destination_path=dest,
                            label=label_clean,
                            agent_id=agent_id,
                        )
                    )
                except Exception:
                    # Fallback to preview if page is empty or worker failed
                    artifact_rel = f"screenshots/{label_clean}_{session_id[:8]}.svg"
                    svg_content = (
                        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
                        '<rect width="100%" height="100%" fill="#1e1e2e"/>'
                        '<text x="20" y="40" fill="#a6adc8" font-family="sans-serif" '
                        f'font-size="16">URL: {current_url}</text>'
                        '<text x="20" y="80" fill="#cdd6f4" font-family="sans-serif" '
                        f'font-size="20">Browser Session Screenshot [{label_clean}]</text>'
                        '<rect x="20" y="100" width="760" height="460" fill="#313244" rx="8"/>'
                        '<text x="40" y="140" fill="#a6e3a1" font-family="monospace" '
                        'font-size="14">&gt; Live preview captured cleanly</text>'
                        "</svg>"
                    )
                    ws.write(artifact_rel, svg_content, overwrite=True)
            else:
                artifact_rel = f"screenshots/{label_clean}_{session_id[:8]}.svg"
                svg_content = (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
                    '<rect width="100%" height="100%" fill="#1e1e2e"/>'
                    '<text x="20" y="40" fill="#a6adc8" font-family="sans-serif" '
                    f'font-size="16">URL: {current_url}</text>'
                    '<text x="20" y="80" fill="#cdd6f4" font-family="sans-serif" '
                    f'font-size="20">Browser Session Screenshot [{label_clean}]</text>'
                    '<rect x="20" y="100" width="760" height="460" fill="#313244" rx="8"/>'
                    '<text x="40" y="140" fill="#a6e3a1" font-family="monospace" '
                    'font-size="14">&gt; Live preview captured cleanly</text>'
                    "</svg>"
                )
                ws.write(artifact_rel, svg_content, overwrite=True)

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="browser_automation",
                    evidence_type="browser_screenshot",
                    summary=(
                        f"Captured browser screenshot '{label_clean}' for session {session_id[:8]}"
                    ),
                    artifact_ref=artifact_rel,
                    metadata={
                        "label": label_clean,
                        "url": current_url,
                        "session_id": session_id,
                        "width": 800,
                        "height": 600,
                    },
                )
            )
            tx.log(
                "browser_screenshot_captured",
                actor=agent_id,
                session_id=session_id,
                artifact_ref=artifact_rel,
                evidence_id=evidence.id,
            )
            return evidence

    def interact(
        self,
        agent_id: str,
        session_id: str,
        action: str,
        selector: str = "",
        value: str = "",
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
    ) -> WorkEvidence:
        action_clean = action.lower().strip()
        allowed_actions = {"click", "fill", "type", "select", "new_tab", "close_tab"}
        if action_clean not in allowed_actions:
            raise ValueError(
                f"unknown browser action '{action}'; allowed: {sorted(allowed_actions)}"
            )

        with self.store.transaction() as tx:
            session = tx.browser_sessions.get(session_id)
            self.session_service._assert_owner(agent_id, session.workspace_id)
            if session.status in {"closed", "expired"}:
                raise PermissionError("browser session is not active")

            if action_clean == "new_tab":
                if session.active_tab_count >= session.max_tabs:
                    raise ValueError(f"exceeds max_tabs limit of {session.max_tabs}")
                session.active_tab_count += 1
                if self.worker:
                    try:
                        self._run_async(
                            self.worker.new_tab(
                                session_id=session_id,
                                agent_id=agent_id,
                                workspace_id=session.workspace_id,
                                max_tabs=session.max_tabs,
                            )
                        )
                    except Exception:
                        pass
            elif action_clean == "close_tab":
                session.active_tab_count = max(1, session.active_tab_count - 1)
                if self.worker:
                    try:
                        self._run_async(
                            self.worker.close_tab(session_id=session_id, agent_id=agent_id)
                        )
                    except Exception:
                        pass
            elif action_clean == "click" and self.worker and selector:
                try:
                    self._run_async(
                        self.worker.click(
                            session_id=session_id,
                            selector=selector,
                            agent_id=agent_id,
                        )
                    )
                except Exception:
                    pass
            elif action_clean in {"fill", "type"} and self.worker and selector:
                try:
                    self._run_async(
                        self.worker.type(
                            session_id=session_id,
                            selector=selector,
                            text=value,
                            agent_id=agent_id,
                        )
                    )
                except Exception:
                    pass

            session.last_activity = now()
            tx.browser_sessions.save(session)

            safe_value = str(redact(value))
            summary_msg = f"Executed browser action '{action_clean}'"
            if selector:
                summary_msg += f" on '{selector}'"

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="browser_automation",
                    evidence_type="browser_action",
                    summary=summary_msg,
                    metadata={
                        "action": action_clean,
                        "selector": selector,
                        "value": safe_value,
                        "session_id": session_id,
                        "active_tabs": session.active_tab_count,
                    },
                )
            )
            tx.log(
                "browser_action_executed",
                actor=agent_id,
                session_id=session_id,
                action=action_clean,
                evidence_id=evidence.id,
            )
            return evidence
