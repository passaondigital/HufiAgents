"""Adds Task.project_id/dry_run (ADR-010, Phase 2B project connector) to a
tasks table created by migration 001 before these fields existed. Idempotent:
on a brand-new database, 001's create_all already reflects the current Task
model and creates both columns itself, so this is a no-op there -- it only
acts on a database migrated before this change."""


def apply(connection):
    existing = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tasks)")}
    if "project_id" not in existing:
        connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN project_id VARCHAR")
    if "dry_run" not in existing:
        connection.exec_driver_sql("ALTER TABLE tasks ADD COLUMN dry_run BOOLEAN")
