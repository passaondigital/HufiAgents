from datetime import timedelta

import pytest

from hufiagents.contracts import AgentConnectorAccess, Risk, Routine, now
from hufiagents.orchestrator.registry import AgentRegistry
from hufiagents.persistence.repository import Store
from hufiagents.workforce.connectors import ConnectorRegistry
from hufiagents.workforce.routines import RoutineService, next_occurrence
from hufiagents.workforce.sessions import SessionService


def seeded_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    AgentRegistry(store).seed()
    return store


def test_product_schedule_is_timezone_aware_and_not_cron():
    result = next_occurrence("every monday at 08:00", "Europe/Berlin", now())
    assert result > now()
    with pytest.raises(ValueError):
        next_occurrence("0 8 * * 1", "Europe/Berlin")


def test_routine_is_persistent_lifecycle_audited_and_dispatched(tmp_path):
    store, submitted = seeded_store(tmp_path), []
    service = RoutineService(
        store, lambda template: submitted.append(template) or type("Mission", (), {"id": "m-1"})()
    )
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "check"},
            schedule="every day at 08:00",
            timezone="Europe/Berlin",
        )
    )
    service.pause(routine.id)
    assert service.tick(now() + timedelta(days=2)) == []
    service.resume(routine.id)
    with store.transaction() as tx:
        active = tx.routines.get(routine.id)
        active.next_run = now() - timedelta(seconds=1)
        tx.routines.save(active)
    assert service.tick() == [routine.id]
    assert submitted == [{"outcome": "check"}]
    service.archive(routine.id)
    with store.transaction() as tx:
        assert tx.routines.get(routine.id).status == "archived"
        assert {event.event_type for event in tx.audit.list()} >= {
            "routine_created",
            "routine_updated",
            "routine_dispatched",
            "routine_archived",
        }
    store.close()


def test_routine_failure_uses_bounded_persistent_retry(tmp_path):
    store = seeded_store(tmp_path)
    service = RoutineService(store, lambda _: (_ for _ in ()).throw(ConnectionError("offline")))
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "check"},
            schedule="every day at 08:00",
            timezone="UTC",
            retry_policy={"max_attempts": 1, "retry_delay_seconds": 10},
        )
    )
    with store.transaction() as tx:
        routine = tx.routines.get(routine.id)
        routine.next_run = now() - timedelta(seconds=1)
        tx.routines.save(routine)
    service.tick()
    with store.transaction() as tx:
        retry = tx.routines.get(routine.id)
        assert retry.retry_count == 1 and retry.notification_state == "pending"
        retry.next_run = now() - timedelta(seconds=1)
        tx.routines.save(retry)
    service.tick()
    with store.transaction() as tx:
        exhausted = tx.routines.get(routine.id)
        assert exhausted.retry_count == 0 and exhausted.notification_state == "failed"
        assert any(e.event_type == "routine_dispatch_exhausted" for e in tx.audit.list())
    store.close()


def test_workspace_and_browser_are_owned_durable_and_do_not_start_processes(tmp_path):
    store = seeded_store(tmp_path)
    service = SessionService(store, tmp_path / "controlled-workspaces")
    workspace = service.create_workspace("builder", "builder-work")
    assert service.workspace_path(workspace.id) == (
        tmp_path / "controlled-workspaces" / "builder-work"
    )
    browser = service.prepare_browser("builder", workspace.id, memory_limit_mb=256)
    assert browser.status == "prepared"
    with pytest.raises(PermissionError):
        service.prepare_computer("reviewer", workspace.id)
    service.close("browser_sessions", browser.id)
    with store.transaction() as tx:
        assert tx.browser_sessions.get(browser.id).status == "closed"
        assert any(event.event_type == "browser_session_prepared" for event in tx.audit.list())
    store.close()


def test_connector_grants_are_least_privilege_and_never_persist_secret(tmp_path):
    store = seeded_store(tmp_path)
    registry = ConnectorRegistry(store)
    github = registry.register_github(configured=True, healthy=True)
    access = registry.grant(
        AgentConnectorAccess(
            agent_id="builder",
            connector_id=github.id,
            capabilities=["repo.read"],
            modes=["read"],
            risk_ceiling=Risk.R1,
        )
    )
    assert access.status == "active"
    with pytest.raises(PermissionError):
        registry.grant(
            AgentConnectorAccess(
                agent_id="builder",
                connector_id=github.id,
                capabilities=["pull_request.draft.create"],
                modes=["write"],
                risk_ceiling=Risk.R1,
            )
        )
    registry.revoke(access.id)
    with store.transaction() as tx:
        saved = tx.connectors.get(github.id)
        assert "token" not in saved.model_dump_json().lower()
        assert tx.agent_connector_access.get(access.id).status == "revoked"
    store.close()
