"""V1.3 Browser Tool for the HufiAgents Runtime.

Exposes controlled Chromium browser actions through ToolGateway to agents with browser capabilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hufiagents.browser_worker import BrowserWorker
from hufiagents.contracts import Risk, ToolCall, ToolResult, WorkEvidence, now
from hufiagents.redaction import redact


class BrowserTool:
    id = "browser"

    def __init__(
        self,
        workspace,
        browser_worker: BrowserWorker,
        store=None,
        settings=None,
        task=None,
    ):
        self.workspace = workspace
        self.browser_worker = browser_worker
        self.store = store
        self.settings = settings
        self.task = task

    async def classify(self, action: str, params: dict[str, Any]) -> Risk:
        """Classify browser actions into appropriate risk levels."""
        action_clean = action.lower().strip()
        safe_read_actions = {
            "open_url",
            "navigate",
            "read_page",
            "get_current_url",
            "get_title",
            "list_tabs",
            "switch_tab",
            "screenshot",
            "wait_for",
        }
        interaction_actions = {
            "click",
            "type",
            "fill",
            "press_key",
            "new_tab",
            "close_tab",
        }
        critical_actions = {
            "submit_destructive",
            "delete_account",
            "purchase",
            "publish",
        }

        if action_clean in safe_read_actions or action_clean in interaction_actions:
            return Risk.R1
        if action_clean in critical_actions:
            return Risk.R3
        raise PermissionError(f"Unsupported browser action '{action}'")

    async def execute(self, call: ToolCall) -> ToolResult:
        """Execute a browser tool action using the real BrowserWorker."""
        action = call.action.lower().strip()
        params = call.params or {}
        target = call.target or ""

        task_id = call.task_id
        mission_id = getattr(self.task, "mission_id", None) if self.task else None
        agent_id = (
            getattr(self.task, "assigned_agent_id", "builder")
            if self.task
            else params.get("agent_id", "builder")
        )

        session_id = params.get("session_id") or (
            f"session-{task_id}" if task_id else "default-browser-session"
        )

        result_data: Any = None
        evidence_summary: str = ""
        artifact_ref: str | None = None

        if action in {"open_url", "navigate"}:
            url = params.get("url") or target
            result_data = await self.browser_worker.open_url(
                session_id=session_id,
                url=url,
                agent_id=agent_id,
                max_tabs=params.get("max_tabs", 5),
            )
            evidence_summary = (
                f"Seite geöffnet: {result_data.get('url')} ({result_data.get('title')})"
            )

        elif action == "read_page":
            max_chars = int(params.get("max_chars", 4000))
            result_data = await self.browser_worker.read_page(
                session_id=session_id,
                agent_id=agent_id,
                max_chars=max_chars,
            )
            evidence_summary = f"Seite gelesen ({len(result_data)} Zeichen)"

        elif action in {"click", "click_element"}:
            selector = params.get("selector") or target
            result_data = await self.browser_worker.click(
                session_id=session_id,
                selector=selector,
                agent_id=agent_id,
            )
            evidence_summary = f"Schaltfläche angeklickt: {selector}"

        elif action in {"type", "fill"}:
            selector = params.get("selector") or target
            text = params.get("text") or params.get("value") or ""
            result_data = await self.browser_worker.type(
                session_id=session_id,
                selector=selector,
                text=text,
                agent_id=agent_id,
            )
            evidence_summary = f"Text eingegeben in '{selector}'"

        elif action == "press_key":
            key = params.get("key") or target or "Enter"
            result_data = await self.browser_worker.press_key(
                session_id=session_id,
                key=key,
                agent_id=agent_id,
            )
            evidence_summary = f"Taste gedrückt: {key}"

        elif action == "wait_for":
            selector = params.get("selector") or (target if target else None)
            timeout_ms = int(params.get("timeout_ms", 5000))
            result_data = await self.browser_worker.wait_for(
                session_id=session_id,
                selector=selector,
                timeout_ms=timeout_ms,
                agent_id=agent_id,
            )
            evidence_summary = f"Warten beendet: {selector or f'{timeout_ms}ms'}"

        elif action == "new_tab":
            url = params.get("url") or (target if target else None)
            result_data = await self.browser_worker.new_tab(
                session_id=session_id,
                url=url,
                agent_id=agent_id,
                max_tabs=params.get("max_tabs", 5),
            )
            evidence_summary = f"Neuer Tab geöffnet (Index {result_data.get('tab_index')})"

        elif action == "list_tabs":
            result_data = await self.browser_worker.list_tabs(
                session_id=session_id,
                agent_id=agent_id,
            )
            evidence_summary = f"Tabs aufgelistet ({len(result_data)} offen)"

        elif action == "switch_tab":
            index = int(params.get("index", target if target.isdigit() else 0))
            result_data = await self.browser_worker.switch_tab(
                session_id=session_id,
                index=index,
                agent_id=agent_id,
            )
            evidence_summary = f"Zu Tab {index} gewechselt"

        elif action == "close_tab":
            index = (
                int(params["index"])
                if "index" in params
                else (int(target) if target.isdigit() else None)
            )
            result_data = await self.browser_worker.close_tab(
                session_id=session_id,
                index=index,
                agent_id=agent_id,
            )
            evidence_summary = f"Tab geschlossen ({result_data.get('tab_count')} verbleibend)"

        elif action == "screenshot":
            label = str(params.get("label") or target or "screenshot").replace(" ", "_")
            artifact_ref = f"screenshots/{label}_{session_id[:8]}.png"

            # Create path inside workspace
            dest_path = Path(self.workspace.root) / artifact_ref
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            result_data = await self.browser_worker.screenshot(
                session_id=session_id,
                destination_path=dest_path,
                label=label,
                agent_id=agent_id,
            )
            evidence_summary = (
                f"Screenshot erstellt: {artifact_ref} ({result_data.get('size_bytes')} Bytes)"
            )

        elif action == "get_current_url":
            url = await self.browser_worker.get_current_url(session_id, agent_id)
            result_data = {"status": "ok", "url": url}
            evidence_summary = f"Aktuelle URL: {url}"

        elif action == "get_title":
            title = await self.browser_worker.get_title(session_id, agent_id)
            result_data = {"status": "ok", "title": title}
            evidence_summary = f"Seitentitel: {title}"

        else:
            raise PermissionError(f"Unsupported browser action '{action}'")

        # Record WorkEvidence in store if available
        if self.store and evidence_summary:
            try:
                with self.store.transaction() as tx:
                    evidence_type = (
                        "browser_screenshot" if action == "screenshot" else "browser_action"
                    )
                    content = (
                        result_data
                        if isinstance(result_data, str)
                        else json.dumps(redact(result_data))
                    )
                    tx.work_evidence.add(
                        WorkEvidence(
                            mission_id=mission_id,
                            task_id=task_id,
                            source_type="browser_automation",
                            evidence_type=evidence_type,
                            summary=redact(evidence_summary),
                            content=content[:16000],
                            artifact_ref=artifact_ref,
                            metadata={
                                "action": action,
                                "session_id": session_id,
                                "agent_id": agent_id,
                            },
                        )
                    )
                    tx.log(
                        "browser_action_completed",
                        actor=agent_id,
                        task_id=task_id,
                        action=action,
                        session_id=session_id,
                    )
            except Exception:
                pass

        summary_text = (
            result_data if isinstance(result_data, str) else json.dumps(redact(result_data))
        )

        return ToolResult(
            **{
                **call.model_dump(),
                "result_status": "ok",
                "result_summary": redact(summary_text),
                "executed_at": now(),
            }
        )
