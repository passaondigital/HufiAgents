"""WF-6 safe, durable session preparation. No browser or host computer is started here."""

import re
from pathlib import Path

from hufiagents.contracts import (
    AgentWorkspace,
    BrowserSession,
    ComputerSession,
    WorkspaceSession,
    now,
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

    def prepare_browser(
        self, agent_id: str, workspace_id: str, *, memory_limit_mb=512
    ) -> BrowserSession:
        self._assert_owner(agent_id, workspace_id)
        record = BrowserSession(
            agent_id=agent_id, workspace_id=workspace_id, memory_limit_mb=memory_limit_mb
        )
        return self._add("browser_sessions", record, "browser_session_prepared")

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
