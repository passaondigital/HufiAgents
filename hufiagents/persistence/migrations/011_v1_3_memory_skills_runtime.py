"""V1.3 ScopedMemory status column migration."""

from sqlalchemy import inspect


def apply(connection):
    existing = set(inspect(connection).get_table_names())
    if "scoped_memories" in existing:
        sm_cols = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(scoped_memories)")
        }
        if "status" not in sm_cols:
            connection.exec_driver_sql(
                "ALTER TABLE scoped_memories ADD COLUMN status VARCHAR NOT NULL DEFAULT 'approved'"
            )
