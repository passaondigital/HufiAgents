"""WF-6 safe, durable session preparation. No browser or host computer is started here."""

import re
from pathlib import Path

from hufiagents.contracts import (
    AgentWorkspace,
    BrowserSession,
    ComputerSession,
    Handoff,
    WorkspaceSession,
    now,
    uid,
)
from hufiagents.tools.workspace import Workspace

_KEY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,199}")


class SessionService:
    def __init__(self, store, workspace_root: Path):
        self.store, self.workspace_root = store, Path(workspace_root).resolve()

    def create_workspace(
        self, agent_id: str, storage_key: str, *, quota_bytes=104857600
    ) -> AgentWorkspace:
        if not _KEY.fullmatch(storage_key):
            raise PermissionError("invalid workspace storage key")
        workspace = AgentWorkspace(
            agent_id=agent_id, storage_key=storage_key, quota_bytes=quota_bytes
        )
        with self.store.transaction() as tx:
            tx.agents.get(agent_id)
            tx.agent_workspaces.add(workspace)
            tx.log("agent_workspace_created", actor=agent_id, workspace_id=workspace.id)
        # The only materialized path is derived beneath the configured root.
        Workspace(self.workspace_root / storage_key)
        return workspace

    def workspace_path(self, workspace_id: str) -> Path:
        with self.store.transaction() as tx:
            item = tx.agent_workspaces.get(workspace_id)
        if item.status != "active":
            raise PermissionError("workspace is not active")
        path = (self.workspace_root / item.storage_key).resolve()
        if not path.is_relative_to(self.workspace_root):
            raise PermissionError("workspace escape")
        return path

    def open_workspace(self, agent_id: str, workspace_id: str) -> WorkspaceSession:
        self._assert_owner(agent_id, workspace_id)
        record = WorkspaceSession(agent_id=agent_id, workspace_id=workspace_id)
        return self._add("workspace_sessions", record, "workspace_session_opened")

    def prepare_computer(self, agent_id: str, workspace_id: str) -> ComputerSession:
        self._assert_owner(agent_id, workspace_id)
        record = ComputerSession(agent_id=agent_id, workspace_id=workspace_id)
        return self._add("computer_sessions", record, "computer_session_prepared")

    def activate_computer(self, agent_id: str, session_id: str) -> ComputerSession:
        with self.store.transaction() as tx:
            record = tx.computer_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            record.status, record.last_activity = "active", now()
            tx.computer_sessions.save(record)
            tx.log("computer_session_activated", actor=agent_id, session_id=record.id)
            return record

    def snapshot_computer(
        self, agent_id: str, session_id: str, snapshot_name: str | None = None
    ) -> ComputerSession:
        with self.store.transaction() as tx:
            record = tx.computer_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            ws_path = self.workspace_path(record.workspace_id)
            ws = Workspace(ws_path)
            s_name = snapshot_name or f"snap-{record.id[:8]}"
            snap_dir = ws.snapshot(s_name)
            record.snapshot_path = str(snap_dir)
            record.status, record.last_activity = "snapshot", now()
            tx.computer_sessions.save(record)
            tx.log(
                "computer_session_snapshotted",
                actor=agent_id,
                session_id=record.id,
                snapshot_path=str(snap_dir),
            )
            return record

    def reset_computer(
        self, agent_id: str, session_id: str, snapshot_name: str | None = None
    ) -> ComputerSession:
        with self.store.transaction() as tx:
            record = tx.computer_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            ws_path = self.workspace_path(record.workspace_id)
            ws = Workspace(ws_path)
            s_name = snapshot_name or f"snap-{record.id[:8]}"
            try:
                ws.restore(s_name)
            except FileNotFoundError:
                pass
            record.status, record.last_activity = "reset", now()
            tx.computer_sessions.save(record)
            tx.log("computer_session_reset", actor=agent_id, session_id=record.id)
            return record

    def recover_computer(self, agent_id: str, session_id: str) -> ComputerSession:
        with self.store.transaction() as tx:
            record = tx.computer_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            ws_path = self.workspace_path(record.workspace_id)
            ws_path.mkdir(parents=True, exist_ok=True, mode=0o700)
            record.status, record.last_activity = "recovered", now()
            tx.computer_sessions.save(record)
            tx.log("computer_session_recovered", actor=agent_id, session_id=record.id)
            return record

    def handoff_computer(
        self,
        agent_id: str,
        target_agent_id: str,
        session_id: str,
        *,
        task_id: str | None = None,
        summary: str = "computer session handoff",
    ) -> Handoff:
        with self.store.transaction() as tx:
            record = tx.computer_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            tx.agents.get(target_agent_id)
            token = f"token-computer-{uid()[:8]}"
            record.status, record.handoff_token, record.last_activity = (
                "handoff",
                token,
                now(),
            )
            tx.computer_sessions.save(record)
            handoff = Handoff(
                from_agent_id=agent_id,
                to_agent_id=target_agent_id,
                task_id=task_id,
                summary=summary,
                artifacts=[f"session:{record.id}", f"token:{token}"],
            )
            tx.handoffs.add(handoff)
            tx.log(
                "computer_session_handoff",
                actor=agent_id,
                target_agent_id=target_agent_id,
                session_id=record.id,
                handoff_id=handoff.id,
            )
            return handoff

    def prepare_browser(
        self, agent_id: str, workspace_id: str, *, memory_limit_mb=512, max_tabs=1
    ) -> BrowserSession:
        self._assert_owner(agent_id, workspace_id)
        record = BrowserSession(
            agent_id=agent_id,
            workspace_id=workspace_id,
            memory_limit_mb=memory_limit_mb,
            max_tabs=max_tabs,
        )
        return self._add("browser_sessions", record, "browser_session_prepared")

    def activate_browser(self, agent_id: str, session_id: str) -> BrowserSession:
        with self.store.transaction() as tx:
            record = tx.browser_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            record.status, record.last_activity = "active", now()
            tx.browser_sessions.save(record)
            tx.log("browser_session_activated", actor=agent_id, session_id=record.id)
            return record

    def snapshot_browser(
        self, agent_id: str, session_id: str, snapshot_name: str | None = None
    ) -> BrowserSession:
        with self.store.transaction() as tx:
            record = tx.browser_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            ws_path = self.workspace_path(record.workspace_id)
            ws = Workspace(ws_path)
            s_name = snapshot_name or f"browser-snap-{record.id[:8]}"
            snap_dir = ws.snapshot(s_name)
            record.snapshot_path = str(snap_dir)
            record.status, record.last_activity = "snapshot", now()
            tx.browser_sessions.save(record)
            tx.log(
                "browser_session_snapshotted",
                actor=agent_id,
                session_id=record.id,
                snapshot_path=str(snap_dir),
            )
            return record

    def reset_browser(
        self, agent_id: str, session_id: str, snapshot_name: str | None = None
    ) -> BrowserSession:
        with self.store.transaction() as tx:
            record = tx.browser_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            ws_path = self.workspace_path(record.workspace_id)
            ws = Workspace(ws_path)
            s_name = snapshot_name or f"browser-snap-{record.id[:8]}"
            try:
                ws.restore(s_name)
            except FileNotFoundError:
                pass
            record.current_url = None
            record.active_tab_count = 1
            record.status, record.last_activity = "reset", now()
            tx.browser_sessions.save(record)
            tx.log("browser_session_reset", actor=agent_id, session_id=record.id)
            return record

    def recover_browser(self, agent_id: str, session_id: str) -> BrowserSession:
        with self.store.transaction() as tx:
            record = tx.browser_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            record.active_tab_count = 1
            record.status, record.last_activity = "recovered", now()
            tx.browser_sessions.save(record)
            tx.log("browser_session_recovered", actor=agent_id, session_id=record.id)
            return record

    def handoff_browser(
        self,
        agent_id: str,
        target_agent_id: str,
        session_id: str,
        *,
        task_id: str | None = None,
        summary: str = "browser session handoff",
    ) -> Handoff:
        with self.store.transaction() as tx:
            record = tx.browser_sessions.get(session_id)
            self._assert_owner(agent_id, record.workspace_id)
            tx.agents.get(target_agent_id)
            token = f"token-browser-{uid()[:8]}"
            record.status, record.handoff_token, record.last_activity = (
                "handoff",
                token,
                now(),
            )
            tx.browser_sessions.save(record)
            handoff = Handoff(
                from_agent_id=agent_id,
                to_agent_id=target_agent_id,
                task_id=task_id,
                summary=summary,
                artifacts=[f"session:{record.id}", f"token:{token}"],
            )
            tx.handoffs.add(handoff)
            tx.log(
                "browser_session_handoff",
                actor=agent_id,
                target_agent_id=target_agent_id,
                session_id=record.id,
                handoff_id=handoff.id,
            )
            return handoff

    def close(self, table: str, session_id: str) -> None:
        if table not in {"workspace_sessions", "computer_sessions", "browser_sessions"}:
            raise ValueError("unknown session type")
        with self.store.transaction() as tx:
            record = getattr(tx, table).get(session_id)
            record.status, record.last_activity = "closed", now()
            getattr(tx, table).save(record)
            tx.log(
                "session_closed", actor=record.agent_id, session_id=record.id, session_type=table
            )

    def _assert_owner(self, agent_id, workspace_id):
        with self.store.transaction() as tx:
            workspace = tx.agent_workspaces.get(workspace_id)
        if workspace.agent_id != agent_id or workspace.status != "active":
            raise PermissionError("agent cannot access this workspace")

    def _add(self, table, record, event):
        with self.store.transaction() as tx:
            getattr(tx, table).add(record)
            tx.log(
                event, actor=record.agent_id, session_id=record.id, workspace_id=record.workspace_id
            )
        return record
