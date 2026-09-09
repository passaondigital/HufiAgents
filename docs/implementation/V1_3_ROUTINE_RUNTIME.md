# V1.3A Autonomous Routine Scheduler Runtime Architecture & Implementation

## Overview

The Autonomous Routine Scheduler Runtime connects persisted recurring product routines (`Routine`) to the live server clock and the underlying HufiAgents Orchestrator/Workforce execution engine.

When a routine is scheduled (e.g. `"every monday at 08:00"`, `timezone: "Europe/Berlin"`), the running application scheduler automatically detects due occurrences, claims them atomically in SQLite, creates real `Mission` and `Task` contracts via `Orchestrator.submit()`, advances `next_run` to the next interval, and executes tasks to terminal results without requiring Pascal or an external admin to press anything.

---

## Key Design Principles

1. **No Second Scheduler Engine**: Reuses `RoutineService`, `Orchestrator`, `MissionCreate`, `Audit`, and `Settings`. No Celery, APScheduler, system cron, or standalone queue service.
2. **FastAPI Lifespan Integration**: The background `RoutineScheduler` loop is owned directly by the application lifespan (`create_app`). It starts on app startup and stops cleanly on app shutdown.
3. **Atomic Claim & Concurrency Safety**: Routine execution uses single-transaction row claiming (`with store.transaction() as tx:`) before mission submission, preventing duplicate mission creation even when multiple scheduler workers run simultaneously.
4. **Timezone & Grammar Integrity**: Product schedule syntax (`"every day at HH:MM"` / `"every <weekday> at HH:MM"`) and `ZoneInfo(timezone)` DST calculations remain authoritative.
5. **Security & Approval Boundaries**: Unattended routines DO NOT bypass risk ceilings, capabilities, or approval gates. Tasks requiring approval enter `WAITING APPROVAL` without triggering duplicate mission dispatches.

---

## Architecture & Flow

```
+-------------------------------------------------------------------------------+
|                            FastAPI Lifespan                                   |
| - Starts RoutineScheduler on startup (app.state.routine_scheduler)           |
| - Stops RoutineScheduler on shutdown                                         |
+-------------------------------------------------------------------------------+
       |
       | 1. Every routine_poll_interval_seconds (default: 30s)
       v
+-------------------------------------------------------------------------------+
|                            RoutineScheduler                                   |
| - Calls RoutineService.tick(at=current_time)                                  |
| - Tracks status: running, last_tick_at, last_error, tick_count                |
+-------------------------------------------------------------------------------+
       |
       | 2. RoutineService.tick()
       v
+-------------------------------------------------------------------------------+
|                            Atomic Claim & Dispatch                            |
| - Queries due routines (enabled=True, status="active", next_run <= current)   |
| - Claims routine inside transaction: updates next_run & last_run             |
| - Submits template via Orchestrator.submit()                                  |
+-------------------------------------------------------------------------------+
       |
       | 3. Orchestrator.submit(MissionCreate)
       v
+-------------------------------------------------------------------------------+
|                            HufiAgents Orchestrator                            |
| - Plans Mission & Tasks                                                      |
| - Executes via Workforce / Providers                                         |
| - Respects approval gates (WAITING APPROVAL)                                  |
| - Updates terminal result & logs Audit / WorkEvidence                        |
+-------------------------------------------------------------------------------+
```

---

## 1. Application Lifecycle & Polling Interval

- **Startup**: In `create_app`, `lifespan(app)` initializes `RoutineService` and `RoutineScheduler`, setting `app.state.routine_scheduler`, and invokes `await routine_scheduler.start()`.
- **Shutdown**: On lifespan exit (`finally:`), `await routine_scheduler.stop()` cancels the loop task cleanly without leaving orphaned background processes.
- **Polling Interval**: Governed by `routine_poll_interval_seconds: float = Field(30.0, gt=0, le=600)` in `Settings`. Tests override this interval to milliseconds (e.g., `0.05s`) for fast deterministic runs.

---

## 2. Atomic Claiming & Multi-Worker Idempotency

To prevent race conditions when multiple app workers or simultaneous scheduler ticks run concurrently:

1. `RoutineService.tick()` lists candidate active due routines.
2. For each candidate, a single atomic SQLite transaction (`with store.transaction() as tx:`) re-fetches `fresh = tx.routines.get(routine.id)`.
3. If `fresh.next_run <= current`, `fresh.next_run` is immediately advanced to `next_due = next_occurrence(...)` (or retry delay) and saved *before* calling `submit()`.
4. A second concurrent worker inspecting the same routine sees `fresh.next_run > current` and skips it.

---

## 3. Occurrence Linkage & Failure / Retry Behavior

- **Linkage**: Dispatched missions carry `constraints: {"routine_id": routine.id, "scheduled_for": ISO_TIMESTAMP}`.
- **Room Linkage**: If a routine template includes `"constraints": {"room_id": room.id}`, the completed mission result automatically posts back to the `ChatRoom` via PR #29's fan-in mechanism.
- **Retry Policy**: Governed by `retry_policy` (`max_attempts`, `retry_delay_seconds`).
  - Upon transient failure, `retry_count` increments, `notification_state="pending"`, and `next_run` is set to `current + retry_delay`.
  - When retries are exhausted, `notification_state="failed"`, `retry_count=0`, and `next_run` advances to the next normal schedule.
- **Redaction**: Error strings logged to `audit_log` are passed through `hufiagents.redaction.redact` to prevent credential leakage.

---

## 4. Pause, Resume, Archive & Restart Recovery

- **Paused** (`enabled=False` or `status="paused"`): Skipped by `tick()`.
- **Archived** (`status="archived"`): Skipped by `tick()`.
- **Resumed** (`enabled=True`, `status="active"`): Evaluates `next_run` against `current` and fires when due.
- **Restart Recovery**: If an app process restarts while a routine is due, the atomic claim picks it up cleanly. If a routine was already dispatched, `next_run` is already in the future, preventing duplicate submissions.

---

## 5. Risk, Approvals & Cost Governor

- Routines DO NOT bypass risk policy or auto-approve risky actions.
- Tasks requiring approval transition to `WAITING APPROVAL`. The scheduler advances `next_run` upon dispatch, so subsequent scheduler ticks DO NOT create duplicate missions while waiting for approval.
- External model calls adhere strictly to `Settings` defaults and provider health routing.

---

## 6. Deterministic No-LLM Execution

- When a routine's task template uses deterministic tool operations (or pre-cached completions), task execution completes with `model_calls = 0` in audit logs, proving that routines do not force unnecessary LLM calls.

---

## 7. Diagnostic & Administrative Endpoints

- `POST /routines/runtime/tick`: Authenticated administrative endpoint to manually invoke one scheduler scan. Returns `{"dispatched": [...], "count": N}`.
- `GET /routines/runtime/status`: Returns scheduler status (`running`, `last_tick_at`, `last_error`, `tick_count`, `poll_interval_seconds`).

---

## 8. Known Limitations

- **Single SQLite Database Lease**: Atomic claiming relies on SQLite single-file write lock / WAL transaction isolation. Multi-host horizontal scaling across independent database files requires a shared WAL DB file or distributed lock manager.
- **No Cron Syntax**: V1 schedule grammar supports `"every day at HH:MM"` and `"every <weekday> at HH:MM"`. Standard 5-field cron syntax is rejected by design.
