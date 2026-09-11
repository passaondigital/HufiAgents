import importlib
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, TypeVar

from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.pool import StaticPool

from hufiagents.contracts import (
    AuditEvent,
    Contract,
    State,
    WorkArtifact,
    WorkEvidence,
    WorkforceEvent,
    now,
)
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

    def list(self, *, limit=100, offset=0, descending=False, **filters):
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
        ordering = (
            (order.desc(), self.table.c.id.desc()) if descending else (order, self.table.c.id)
        )
        rows = self.connection.execute(query.order_by(*ordering).limit(limit).offset(offset))
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
        safe_detail = redact(detail)
        event = self.audit.append(
            AuditEvent(
                event_type=event_type,
                actor=actor,
                mission_id=task.mission_id if task else mission_id,
                task_id=task.id if task else None,
                detail=safe_detail,
            )
        )
        self._project_workforce_event(event, task, safe_detail)
        from hufiagents.evidence import EvidenceCollector

        EvidenceCollector.process_event(
            self, event_type, task=task, mission_id=mission_id, actor=actor, detail=safe_detail
        )
        return event

    def _project_workforce_event(self, event, task, detail):
        event_names = {
            "mission_created": "MISSION_ACCEPTED",
            "planning_started": "PLANNING_STARTED",
            "unit_selected": "UNIT_SELECTED",
            "agent_dispatch_persisted": "AGENT_ASSIGNED",
            "agent_assigned": "AGENT_ASSIGNED",
            "tool_started": "TOOL_STARTED",
            "tool_result": "TOOL_COMPLETED",
            "artifact_created": "ARTIFACT_CREATED",
            "message_sent": "MESSAGE_SENT",
            "handoff": "HANDOFF",
            "review_requested": "REVIEW_REQUESTED",
            "review": "REVIEW_COMPLETED",
            "approval_requested": "APPROVAL_REQUIRED",
            "policy_blocked": "BLOCKED",
            "error": "ERROR",
            "executor_error": "ERROR",
            "outcome_completed": "OUTCOME_COMPLETED",
        }
        projected = event_names.get(event.event_type)
        if event.event_type == "state_transition":
            projected = {
                "running": "TASK_STARTED",
                "review": "REVIEW_STARTED",
                "retrying": "RETRY",
                "blocked": "BLOCKED",
                "completed": "TASK_COMPLETED",
                "failed": "ERROR",
            }.get(str(detail.get("target")))
        if not projected:
            return
        summary = (
            detail.get("summary") or detail.get("reason") or projected.replace("_", " ").title()
        )
        self.workforce_events.add(
            WorkforceEvent(
                timestamp=event.ts,
                agent_id=(task.assigned_agent_id if task else None) or detail.get("agent_id"),
                unit_id=detail.get("unit_id"),
                mission_id=event.mission_id,
                task_id=event.task_id,
                event_type=projected,
                safe_summary=redact(str(summary)),
                artifact_ref=redact(detail.get("artifact_ref")),
                status=str(detail.get("target") or detail.get("status") or "") or None,
                severity="error" if projected == "ERROR" else None,
                metadata=safe_detail_without_summary(detail),
            )
        )

    def transition(self, task, target, *, recovery=False, cancel=False, reason=""):
        validate_transition(task.status, target, recovery=recovery, cancel=cancel)
        previous = task.status
        if target == State.completed:
            reviews = self.reviews.list(task_id=task.id, limit=100)
            if not reviews or reviews[-1].verdict != "approve":
                raise ValueError("completion requires reviewer approval")
            if task.deliverable_key and not self.work_artifacts.list(
                task_id=task.id, deliverable_key=task.deliverable_key, limit=1
            ):
                artifact = self.work_artifacts.add(
                    WorkArtifact(
                        mission_id=task.mission_id,
                        task_id=task.id,
                        agent_id=task.assigned_agent_id,
                        deliverable_key=task.deliverable_key,
                        name=task.expected_output,
                        artifact_ref=task.expected_output,
                        origin="AGENT_GENERATED",
                    )
                )
                self.log(
                    "artifact_created",
                    task=task,
                    actor=task.assigned_agent_id or "system",
                    artifact_id=artifact.id,
                    artifact_ref=artifact.artifact_ref,
                    deliverable_key=artifact.deliverable_key,
                )
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
        contracts = self.owner_outcome_contracts.list(mission_id=mission_id, limit=1)
        contract = contracts[0] if contracts else None
        if states == {State.completed} and contract:
            artifacts = self.work_artifacts.list(mission_id=mission_id, limit=1000)
            generated = [
                item for item in artifacts if item.origin in {"AGENT_GENERATED", "TOOL_GENERATED"}
            ]
            deliverables = {item.deliverable_key for item in generated}
            workstreams = {task.workstream_key for task in tasks}
            roles = {task.assigned_agent_id for task in tasks}
            reviews = self.reviews.list(limit=1000)
            task_by_id = {task.id: task for task in tasks}
            independent_reviews = [
                review
                for review in reviews
                if review.task_id in task_by_id
                and review.verdict == "approve"
                and review.reviewer_agent_id != task_by_id[review.task_id].assigned_agent_id
            ]
            evidence = self.work_evidence.list(mission_id=mission_id, limit=1000)
            evidenced_tasks = {item.task_id for item in evidence if item.task_id}
            conditions_met = (
                set(contract.required_deliverables) <= deliverables
                and set(contract.required_workstreams) <= workstreams
                and set(contract.required_roles) <= roles
                and len(independent_reviews) >= len(tasks)
                and {task.id for task in tasks} <= evidenced_tasks
            )
            if conditions_met:
                status = State.completed
                contract.status = "COMPLETED"
                contract.completed_at = now()
                from hufiagents.corporate_router import CorporateRouter

                mission.result = CorporateRouter.format_management_summary(
                    mission.outcome,
                    generated,
                    mission.constraints.get("corporate_route", {}),
                    {
                        "tasks": len(tasks),
                        "artifacts": len(generated),
                        "evidence": len(evidence),
                        "reviews": len(independent_reviews),
                    },
                )
            else:
                status = State.blocked
                contract.status = "PARTIAL"
            contract.updated_at = now()
            self.owner_outcome_contracts.save(contract)
        elif states == {State.completed}:
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
            if contract:
                contract.status = {
                    State.queued: "DISPATCHING",
                    State.planning: "PLANNING",
                    State.running: "RUNNING",
                    State.waiting_approval: "WAITING_APPROVAL",
                    State.blocked: "WAITING",
                    State.review: "REVIEWING",
                    State.retrying: "RUNNING",
                    State.failed: "FAILED",
                    State.cancelled: "FAILED",
                }.get(status, "RUNNING")
                contract.updated_at = now()
                self.owner_outcome_contracts.save(contract)
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
            if status == State.completed:
                self.log(
                    "outcome_completed", mission_id=mission_id, summary="Owner outcome completed"
                )


def safe_detail_without_summary(detail):
    return redact({key: value for key, value in detail.items() if key != "summary"})


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
            if 8 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.008_v1_3_workspace_browser_mcp"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (8)")
            if 9 not in versions:
                importlib.import_module("hufiagents.persistence.migrations.009_room_runtime").apply(
                    connection
                )
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (9)")
            if 10 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.010_workforce_builder"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (10)")
            if 11 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.011_v1_3_memory_skills_runtime"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (11)")
            if 12 not in versions:
                importlib.import_module(
                    "hufiagents.persistence.migrations.012_v1_4a_corporate_matrix"
                ).apply(connection)
                connection.exec_driver_sql("INSERT INTO schema_migrations VALUES (12)")

    @contextmanager
    def transaction(self):
        with self.engine.begin() as connection:
            yield UnitOfWork(connection)

    def close(self):
        self.engine.dispose()
