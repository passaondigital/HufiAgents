"""Unit tests for V1.3A Autonomous Routine Scheduler Runtime.

Covers:
- Autonomous background scheduler tick
- Due routine claim & execution
- Future, paused, and archived routine filtering
- Resume lifecycle
- Mission creation and linkage
- Timezone-aware next_run advancement
- Bounded retry and retry exhaustion
- Multi-worker / concurrent tick safety (atomic claim)
- Process restart / reconstruction idempotency
- Waiting approval idempotency
- Failure redaction
- Graceful scheduler shutdown
- Deterministic no-LLM routine execution (model_calls = 0)
"""

import asyncio
from datetime import timedelta

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import Agent, Risk, Routine, now
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.routine_runtime import RoutineScheduler
from hufiagents.workforce.routines import RoutineService, next_occurrence


def make_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["fake"]},
                risk_ceiling=Risk.R1,
            )
        )
    return store


# 1. Due routine automatically runs via RoutineScheduler
@pytest.mark.asyncio
async def test_due_routine_automatically_runs(tmp_path):
    store = make_store(tmp_path)
    engine = Orchestrator(
        store, Settings(workspace_root=tmp_path / "workspaces", default_provider="fake")
    )
    service = RoutineService(store, engine.submit)
    scheduler = RoutineScheduler(service, poll_interval_seconds=0.01)

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "Auto routine outcome"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    await scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop()

    with store.transaction() as tx:
        updated = tx.routines.get(routine.id)
        assert updated.last_run is not None
        assert updated.next_run > now()
        missions = tx.missions.list(limit=10)
        assert len(missions) == 1
        assert missions[0].outcome == "Auto routine outcome"

    store.close()


# 2. Future routine does not run
def test_future_routine_does_not_run(tmp_path):
    store = make_store(tmp_path)
    submitted = []
    service = RoutineService(store, lambda t: submitted.append(t))
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "future outcome"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() + timedelta(days=5)
        tx.routines.save(r)

    dispatched = service.tick()
    assert dispatched == []
    assert len(submitted) == 0
    store.close()


# 3. Paused routine does not run
def test_paused_routine_does_not_run(tmp_path):
    store = make_store(tmp_path)
    submitted = []
    service = RoutineService(store, lambda t: submitted.append(t))
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "paused outcome"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )
    service.pause(routine.id)

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    assert service.tick() == []
    assert len(submitted) == 0
    store.close()


# 4. Archived routine does not run
def test_archived_routine_does_not_run(tmp_path):
    store = make_store(tmp_path)
    submitted = []
    service = RoutineService(store, lambda t: submitted.append(t))
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "archived outcome"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )
    service.archive(routine.id)

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    assert service.tick() == []
    assert len(submitted) == 0
    store.close()


# 5. Resumed routine can run
def test_resumed_routine_can_run(tmp_path):
    store = make_store(tmp_path)
    submitted = []
    service = RoutineService(store, lambda t: submitted.append(t) or type("M", (), {"id": "m1"})())
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "resumed outcome"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )
    service.pause(routine.id)
    service.resume(routine.id)

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    assert service.tick() == [routine.id]
    assert len(submitted) == 1
    store.close()


# 6 & 7. Successful occurrence creates Mission and links to it
def test_successful_occurrence_creates_mission(tmp_path):
    store = make_store(tmp_path)
    engine = Orchestrator(
        store, Settings(workspace_root=tmp_path / "workspaces", default_provider="fake")
    )
    service = RoutineService(store, engine.submit)

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "linked outcome", "constraints": {"room_id": "room-1"}},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    dispatched = service.tick()
    assert dispatched == [routine.id]

    with store.transaction() as tx:
        events = tx.audit.list(limit=20)
        dispatch_events = [e for e in events if e.event_type == "routine_dispatched"]
        assert len(dispatch_events) == 1
        submitted_mission_id = dispatch_events[0].detail.get("submitted_mission_id")
        assert submitted_mission_id is not None
        mission = tx.missions.get(submitted_mission_id)
        assert mission.outcome == "linked outcome"
        assert mission.constraints.get("routine_id") == routine.id

    store.close()


# 9. Next run advances correctly after tick
def test_next_run_advances(tmp_path):
    store = make_store(tmp_path)
    service = RoutineService(store, lambda t: type("M", (), {"id": "m1"})())
    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "test"},
            schedule="every monday at 08:00",
            timezone="Europe/Berlin",
        )
    )

    past = now() - timedelta(seconds=10)
    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = past
        tx.routines.save(r)

    service.tick(at=past)
    with store.transaction() as tx:
        updated = tx.routines.get(routine.id)
        assert updated.last_run == past
        assert updated.next_run > past

    store.close()


# 10 & 11. Retry and retry exhaustion
def test_retry_and_exhaustion(tmp_path):
    store = make_store(tmp_path)

    def def_fail(_):
        raise RuntimeError("Simulated failure")

    service = RoutineService(store, def_fail)

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "failing"},
            schedule="every day at 08:00",
            timezone="UTC",
            retry_policy={"max_attempts": 1, "retry_delay_seconds": 10},
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    # First failure -> schedules retry
    service.tick()
    with store.transaction() as tx:
        r1 = tx.routines.get(routine.id)
        assert r1.retry_count == 1
        assert r1.notification_state == "pending"

    # Make retry due
    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    # Second failure -> retry exhausted
    service.tick()
    with store.transaction() as tx:
        r2 = tx.routines.get(routine.id)
        assert r2.retry_count == 0
        assert r2.notification_state == "failed"
        events = tx.audit.list()
        assert any(e.event_type == "routine_dispatch_exhausted" for e in events)

    store.close()


# 12. Multi-worker simultaneous tick creates ONLY ONE Mission (Atomic Claim)
def test_simultaneous_scheduler_ticks_create_one_mission(tmp_path):
    store = make_store(tmp_path)
    submitted = []

    def _submit(t):
        submitted.append(t)
        return type("M", (), {"id": f"m-{len(submitted)}"})()

    service = RoutineService(store, _submit)

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "concurrent check"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    # Simulate two workers calling tick concurrently
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(service.tick)
        f2 = executor.submit(service.tick)
        r1 = f1.result()
        r2 = f2.result()

    total_dispatched = r1 + r2
    assert total_dispatched == [routine.id]
    assert len(submitted) == 1

    store.close()


# 13. Process restart / reconstruction idempotency
def test_process_restart_reconstruction_does_not_duplicate_occurrence(tmp_path):
    url = f"sqlite:///{tmp_path}/state.sqlite3"
    store1 = Store(url)
    with store1.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"]},
                risk_ceiling=Risk.R1,
            )
        )

    submitted1 = []
    service1 = RoutineService(
        store1, lambda t: submitted1.append(t) or type("M", (), {"id": "m1"})()
    )
    routine = service1.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "restart test"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store1.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    service1.tick()
    assert len(submitted1) == 1
    store1.close()

    # Re-open store (simulates process restart)
    store2 = Store(url)
    submitted2 = []
    service2 = RoutineService(
        store2, lambda t: submitted2.append(t) or type("M", (), {"id": "m2"})()
    )

    service2.tick()
    assert len(submitted2) == 0

    store2.close()


# 14. Waiting approval does not create duplicate Mission
@pytest.mark.asyncio
async def test_waiting_approval_does_not_create_duplicate_mission(tmp_path):
    store = make_store(tmp_path)
    engine = Orchestrator(
        store, Settings(workspace_root=tmp_path / "workspaces", default_provider="fake")
    )
    service = RoutineService(store, engine.submit)

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "approval test"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    dispatched1 = service.tick()
    assert dispatched1 == [routine.id]

    # Subsequent tick immediately after should NOT dispatch again
    dispatched2 = service.tick()
    assert dispatched2 == []

    with store.transaction() as tx:
        assert len(tx.missions.list()) == 1

    store.close()


# 15. Failure message redacted
def test_failure_message_redacted(tmp_path):
    store = make_store(tmp_path)
    service = RoutineService(
        store, lambda _: (_ for _ in ()).throw(RuntimeError("Error with token=secret123456"))
    )

    routine = service.create(
        Routine(
            owner_agent_id="builder",
            mission_template={"outcome": "secret failure test"},
            schedule="every day at 08:00",
            timezone="UTC",
        )
    )

    with store.transaction() as tx:
        r = tx.routines.get(routine.id)
        r.next_run = now() - timedelta(seconds=5)
        tx.routines.save(r)

    service.tick()
    with store.transaction() as tx:
        events = tx.audit.list()
        retry_events = [e for e in events if e.event_type == "routine_retry_scheduled"]
        assert len(retry_events) == 1
        err_str = retry_events[0].detail.get("error", "")
        assert "secret123456" not in err_str

    store.close()


# 16. Timezone-aware due calculation
def test_timezone_due_calculation():
    next_berlin = next_occurrence("every monday at 08:00", "Europe/Berlin")
    assert next_berlin.tzinfo is not None
    next_tokyo = next_occurrence("every monday at 08:00", "Asia/Tokyo")
    assert next_tokyo.tzinfo is not None
    assert next_berlin != next_tokyo


# 17. Graceful scheduler shutdown
@pytest.mark.asyncio
async def test_graceful_scheduler_shutdown(tmp_path):
    store = make_store(tmp_path)
    service = RoutineService(store, lambda t: None)
    scheduler = RoutineScheduler(service, poll_interval_seconds=10.0)

    await scheduler.start()
    assert scheduler.status["running"] is True
    await scheduler.stop()
    assert scheduler.status["running"] is False
    store.close()


# 18. Deterministic no-LLM routine execution (model_calls = 0)
@pytest.mark.asyncio
async def test_deterministic_no_llm_routine_proof(tmp_path):
    store = make_store(tmp_path)
    engine = Orchestrator(
        store, Settings(workspace_root=tmp_path / "workspaces", default_provider="fake")
    )
    await engine.start()

    # Pre-populate cached completion so no LLM provider is invoked
    request = MissionCreate(outcome="deterministic check")
    mission = engine.submit(request)

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        assert len(tasks) == 1
        task_id = tasks[0].id
        from hufiagents.contracts import MemoryRecord

        tx.task_context.add(
            MemoryRecord(
                owner_id=task_id,
                key="completion:0",
                value={"text": "deterministic result", "model": "no-llm"},
            )
        )

    await engine.tick()
    await asyncio.sleep(0.1)

    with store.transaction() as tx:
        events = tx.audit.list(task_id=task_id)
        model_calls = [e for e in events if e.event_type == "model_call"]
        assert len(model_calls) == 0

    await engine.stop()
    store.close()
