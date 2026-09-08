"""Dynamic workforce persistence, additive and safe for existing V1 databases."""

from hufiagents.persistence.schema import TABLES


def _columns(connection, table):
    return {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}


def apply(connection):
    # 001 creates an up-to-date schema for fresh installs; older databases need
    # only the additive Agent columns below.
    agent_columns = {
        "name": "VARCHAR NOT NULL DEFAULT ''",
        "description": "VARCHAR NOT NULL DEFAULT ''",
        "parent_agent_id": "VARCHAR",
        "project_id": "VARCHAR",
        "risk_ceiling": "VARCHAR NOT NULL DEFAULT 'R1'",
        "model_preference": "VARCHAR",
        "memory_scope": "VARCHAR NOT NULL DEFAULT 'agent'",
        "workspace_id": "VARCHAR",
        "created_by": "VARCHAR NOT NULL DEFAULT 'system'",
        "created_at": "VARCHAR",
        "archived_at": "VARCHAR",
    }
    existing = _columns(connection, "agents")
    for name, definition in agent_columns.items():
        if name not in existing:
            connection.exec_driver_sql(f"ALTER TABLE agents ADD COLUMN {name} {definition}")
    # Old V1 seed rows predate this required contract field. SQLite ALTER TABLE
    # cannot add a non-constant timestamp default, so make the upgrade rows
    # valid explicitly rather than weakening the public Agent contract.
    connection.exec_driver_sql(
        "UPDATE agents SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
        "WHERE created_at IS NULL"
    )
    for name in ("agent_messages", "delegations", "channels"):
        TABLES[name].create(connection, checkfirst=True)
