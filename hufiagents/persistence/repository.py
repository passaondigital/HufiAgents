import importlib
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, TypeVar

from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.pool import StaticPool

from hufiagents.contracts import AuditEvent, Contract, State, WorkEvidence, now
from hufiagents.orchestrator.state import TERMINAL, validate_transition
from hufiagents.persistence.schema import MODELS, TABLES
from hufiagents.redaction import redact

T = TypeVar("T", bound=Contract)


class Repository(Protocol[T]):
    def get(self, identifier: str) -> T: ...
    def list(self, *, limit: int = 100, offset: int = 0, **filters) -> list[T]: ...
    def add(self, record: T) -> T: ...
    def save(self, record: T) -> T: ...


class AuditRepository(Protocol):
    def append(self, record: AuditEvent) -> AuditEvent: ...
    def list(self, *, limit: int = 100, offset: int = 0, **filters) -> list[AuditEvent]: ...


class Rows:
    def __init__(self, connection, name):
        self.connection, self.table, self.model = connection, TABLES[name], MODELS[name]

    def get(self, identifier):
        rows = self.list(id=identifier, limit=1)
        if not rows:
            raise KeyError(identifier)
        return rows[0]

    def list(self, *, limit=100, offset=0, **filters):
        query = select(self.table)
        for field, value in filters.items():
            column = self.table.c[field]
            query = query.where(
                column.in_(value) if isinstance(value, (list, set)) else column == value
            )
        order = self.table.c.get(
            "created_at",
            self.table.c.get("requested_at", self.table.c.get("ts", self.table.c.id)),
        )
        rows = self.connection.execute(
            query.order_by(order, self.table.c.id).limit(limit).offset(offset)
        )
        return [self.model.model_validate(dict(row)) for row in rows.mappings()]

    def add(self, record):
        self.connection.execute(insert(self.table).values(**record.model_dump(mode="json")))
        return record

    def save(self, record):
        result = self.connection.execute(
            update(self.table)
            .where(self.table.c.id == record.id)
            .values(**record.model_dump(mode="json"))
        )
        if result.rowcount != 1:
            raise KeyError(record.id)
        return record


class AuditRows:
    def __init__(self, connection):
        self._rows = Rows(connection, "audit_log")

    def append(self, record):
        record.detail = redact(record.detail)
        return self._rows.add(record)

    def list(self, **filters):
        return self._rows.list(**filters)


class EvidenceRows:
    """Repository boundary for WorkEvidence.

    Sanitizing here ensures direct store users receive the same guarantee as
    the HTTP API.  A caller can never accidentally persist a raw tool result.
    """

    def __init__(self, connection):
        self._rows = Rows(connection, "work_evidence")

    def add(self, record: WorkEvidence):
        record.summary = redact(record.summary)
        record.content = redact(record.content)
        record.artifact_ref = redact(record.artifact_ref)
        record.metadata = redact(record.metadata)
        record.redacted_at = now()
        return self._rows.add(record)

    def get(self, identifier):
        return self._rows.get(identifier)

    def list(self, **filters):
        return self._rows.list(**filters)


class UnitOfWork:
    def __init__(self, connection):
        for name in TABLES:
            if name != "audit_log":
                setattr(self, name, Rows(connection, name))
        self.audit = AuditRows(connection)
        self.work_evidence = EvidenceRows(connection)
        # Friendly singular alias used by service code and integrations.
        self.evidence = self.work_evidence

    def log(self, event_type, *, task=None, mission_id=None, actor="system", **detail):
        self.audit.append(
            AuditEvent(
                event_type=event_type,
                actor=actor,
                mission_id=task.mission_id if task else mission_id,
                task_id=task.id if task else None,
                detail=detail,
            )
        )

    def transition(self, task, target, *, recovery=False, cancel=False, reason=""):
        validate_transition(task.status, target, recovery=recovery, cancel=cancel)
        previous = task.status
        if target == State.completed:
            reviews = self.reviews.list(task_id=task.id, limit=100)
            if not reviews or reviews[-1].verdict != "approve":
                raise ValueError("completion requires reviewer approval")
        if target == State.queued and previous == State.retrying:
            if task.retry_count >= task.retry_limit:
                raise ValueError("retry budget exhausted")
            task.retry_count += 1
        task.status = target
        if target in {State.planning, State.running}:
            task.heartbeat_at = now()
        if target == State.running and task.started_at is None:
            task.started_at = now()
        if target in TERMINAL:
            task.finished_at = now()
        self.tasks.save(task)
        self.log("state_transition", task=task, source=previous, target=target, reason=reason)
        self.refresh_mission(task.mission_id)
        return task

    def refresh_mission(self, mission_id):
        mission = self.missions.get(mission_id)
        tasks = self.tasks.list(mission_id=mission_id, limit=10000)
        states = {task.status for task in tasks}
        if states == {State.completed}:
            status = State.completed
            mission.result = "\n\n".join(task.result or "" for task in tasks)
        else:
            status = next(
                (
                    state
                    for state in [
                        State.failed,
                        State.cancelled,
                        State.waiting_approval,
                        State.running,
                        State.review,
                        State.planning,
                        State.retrying,
                        State.blocked,
                        State.queued,
                    ]
                    if state in states
                ),
                State.queued,
            )
        if mission.status != status:
            self.log(
                "state_transition",
                mission_id=mission_id,
                source=mission.status,
                target=status,
                scope="mission",
            )
            mission.status, mission.updated_at = status, now()
            if status in TERMINAL:
                mission.completed_at = now()
            self.missions.save(mission)


class Store:
    def __init__(self, url):
        if not url.startswith("sqlite:"):
            raise ValueError("V1 supports SQLite only; use another Store adapter for other engines")
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        options = {"poolclass": StaticPool} if url.endswith(":memory:") else {}
        self.engine = create_engine(url, connect_args={"check_same_thread": False}, **options)

        @event.listens_for(self.engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA journal_mode=WAL")

        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
            )
            applied = connection.exec_driver_sql("SELECT version FROM schema_migrations").scalars()
            versions = set(applied)
            if 1 not in versions:
                importlib.import_module("hufiagents.persistence.migrations.001_initial").apply(
                    connection
                )
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (1)")
            if 2 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.002_project_fields"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (2)")
            if 3 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.003_dynamic_workforce"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (3)")
            if 4 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.004_routines_connectors"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (4)")
            if 5 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.005_work_evidence"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (5)")
            if 6 not in versions:
                importlib.import_module("hufiagents.persistence.migrations.006_org_graph").apply(
                    connection
                )
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (6)")
            if 7 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.007_skills_memory"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (7)")
            if 9 not in versions:
                importlib.import_module("hufiagents.persistence.migrations.009_room_runtime").apply(
                    connection
                )
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (9)")

    @contextmanager
    def transaction(self):
        with self.engine.begin() as connection:
            yield UnitOfWork(connection)

    def close(self):
        self.engine.dispose()
