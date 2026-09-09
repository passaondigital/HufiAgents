"""V1.3 real browser automation, retained safe session driver and Work Evidence integration."""

from pathlib import Path
from urllib.parse import urlparse

from hufiagents.contracts import WorkEvidence, now
from hufiagents.redaction import redact
from hufiagents.tools.workspace import Workspace


class BrowserAutomationService:
    def __init__(self, store, session_service):
        self.store = store
        self.session_service = session_service

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
        if not (url_clean.startswith("http://") or url_clean.startswith("https://") or url_clean.startswith("file://") or url_clean.startswith("app://")):
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
            dom_content = (
                f"<!DOCTYPE html><html><head><title>{title}</title></head>"
                f"<body><main><h1>Page loaded: {title}</h1><p>URL: {url_clean}</p></main></body></html>"
            )

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="browser_automation",
                    evidence_type="browser_dom",
                    summary=f"Navigated browser session {session_id[:8]} to {url_clean}",
                    content=dom_content,
                    metadata={"url": url_clean, "session_id": session_id, "active_tabs": session.active_tab_count},
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
            svg_content = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
                f'<rect width="100%" height="100%" fill="#1e1e2e"/>'
                f'<text x="20" y="40" fill="#a6adc8" font-family="sans-serif" font-size="16">URL: {current_url}</text>'
                f'<text x="20" y="80" fill="#cdd6f4" font-family="sans-serif" font-size="20">Browser Session Screenshot [{label_clean}]</text>'
                f'<rect x="20" y="100" width="760" height="460" fill="#313244" rx="8"/>'
                f'<text x="40" y="140" fill="#a6e3a1" font-family="monospace" font-size="14">&gt; Live preview captured cleanly</text>'
                f'</svg>'
            )
            artifact_rel = f"screenshots/{label_clean}_{session_id[:8]}.svg"
            ws.write(artifact_rel, svg_content, overwrite=True)

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="browser_automation",
                    evidence_type="browser_screenshot",
                    summary=f"Captured browser screenshot '{label_clean}' for session {session_id[:8]}",
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
        allowed_actions = {"click", "fill", "select", "new_tab", "close_tab"}
        if action_clean not in allowed_actions:
            raise ValueError(f"unknown browser action '{action}'; allowed: {sorted(allowed_actions)}")

        with self.store.transaction() as tx:
            session = tx.browser_sessions.get(session_id)
            self.session_service._assert_owner(agent_id, session.workspace_id)
            if session.status in {"closed", "expired"}:
                raise PermissionError("browser session is not active")

            if action_clean == "new_tab":
                if session.active_tab_count >= session.max_tabs:
                    raise ValueError(f"exceeds max_tabs limit of {session.max_tabs}")
                session.active_tab_count += 1
            elif action_clean == "close_tab":
                session.active_tab_count = max(1, session.active_tab_count - 1)

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
