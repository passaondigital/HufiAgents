"""Add WF-5--7 routine, workspace/session and connector metadata tables.

Additive and idempotent. Secrets and absolute host paths are deliberately not
stored here; credential material remains in Settings/a secret provider and
workspace paths are derived from the configured root.
"""

from sqlalchemy import inspect

from hufiagents.persistence.schema import TABLES


NAMES = (
    "routines", "agent_workspaces", "workspace_sessions", "computer_sessions",
    "browser_sessions", "connectors", "agent_connector_access",
)


def apply(connection):
    existing = set(inspect(connection).get_table_names())
    for name in NAMES:
        if name not in existing:
            TABLES[name].create(connection)
    # A database that briefly ran an earlier development version of this
    # migration is upgraded safely as well.
    columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(routines)")}
    if "retry_count" not in columns:
        connection.exec_driver_sql("ALTER TABLE routines ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    if "notification_state" not in columns:
        connection.exec_driver_sql("ALTER TABLE routines ADD COLUMN notification_state VARCHAR NOT NULL DEFAULT 'none'")
