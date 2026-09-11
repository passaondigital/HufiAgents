"""V1.4A Corporate Matrix, outcome, artifact and live-event migration.

The migration is additive.  Fresh databases already have the current columns
through migration 001; upgraded V1.3.1 databases receive only missing columns
and tables.
"""

from sqlalchemy import inspect

from hufiagents.persistence.schema import TABLES


def apply(connection):
    for name in (
        "organization_units",
        "owner_outcome_contracts",
        "work_artifacts",
        "workforce_events",
    ):
        TABLES[name].create(connection, checkfirst=True)

    existing = set(inspect(connection).get_table_names())
    if "tasks" in existing:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tasks)")}
        for name in ("workstream_key", "deliverable_key"):
            if name not in columns:
                connection.exec_driver_sql(f"ALTER TABLE tasks ADD COLUMN {name} VARCHAR")

    if "agent_messages" in existing:
        columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(agent_messages)")
        }
        if "message_type" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE agent_messages ADD COLUMN message_type VARCHAR NOT NULL DEFAULT 'INFO'"
            )
