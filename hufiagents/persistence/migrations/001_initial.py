"""Initial schema, including database-enforced immutable audit records."""

from hufiagents.persistence.schema import metadata


def apply(connection):
    metadata.create_all(connection)
    for operation in ("UPDATE", "DELETE"):
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS audit_no_{operation.lower()} "
            f"BEFORE {operation} ON audit_log BEGIN "
            "SELECT RAISE(ABORT, 'audit log is append-only'); END"
        )
