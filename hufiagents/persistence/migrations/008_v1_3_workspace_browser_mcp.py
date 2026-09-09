"""V1.3 persistent computer, browser automation, MCP adapter and connector scope tables/columns."""

from sqlalchemy import inspect

from hufiagents.persistence.schema import TABLES


def apply(connection):
    existing = set(inspect(connection).get_table_names())
    for name in ("mcp_servers", "mcp_tools"):
        if name not in existing:
            TABLES[name].create(connection, checkfirst=True)

    if "computer_sessions" in existing:
        cs_cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(computer_sessions)")}
        if "snapshot_path" not in cs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE computer_sessions ADD COLUMN snapshot_path VARCHAR"
            )
        if "handoff_token" not in cs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE computer_sessions ADD COLUMN handoff_token VARCHAR"
            )

    if "browser_sessions" in existing:
        bs_cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(browser_sessions)")}
        if "current_url" not in bs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE browser_sessions ADD COLUMN current_url VARCHAR"
            )
        if "active_tab_count" not in bs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE browser_sessions ADD COLUMN active_tab_count INTEGER NOT NULL DEFAULT 1"
            )
        if "snapshot_path" not in bs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE browser_sessions ADD COLUMN snapshot_path VARCHAR"
            )
        if "handoff_token" not in bs_cols:
            connection.exec_driver_sql(
                "ALTER TABLE browser_sessions ADD COLUMN handoff_token VARCHAR"
            )

    if "agent_connector_access" in existing:
        aca_cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(agent_connector_access)")}
        if "scopes" not in aca_cols:
            connection.exec_driver_sql(
                "ALTER TABLE agent_connector_access ADD COLUMN scopes JSON NOT NULL DEFAULT '[]'"
            )
