"""WF-5 recurring missions. Product schedules are parsed narrowly, never cron."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hufiagents.contracts import Routine, now

_WEEKDAYS = {
    name: index
    for index, name in enumerate(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    )
}
_SCHEDULE = re.compile(r"every (day|" + "|".join(_WEEKDAYS) + r") at ([0-2]\d):([0-5]\d)$")


def next_occurrence(schedule: str, timezone: str, after: datetime | None = None) -> datetime:
    """Return the next occurrence for the intentionally small V1 schedule grammar.

    The API accepts product language (for example ``every monday at 08:00``),
    not cron. Unsupported language is rejected at creation instead of silently
    scheduling a surprising job.
    """
    match = _SCHEDULE.fullmatch(schedule.strip().lower())
    if not match:
        raise ValueError("schedule must be 'every day at HH:MM' or 'every monday at HH:MM'")
    zone = ZoneInfo(timezone)
    point = (after or now()).astimezone(zone).replace(second=0, microsecond=0)
    kind, hour, minute = match.groups()
    candidate = point.replace(hour=int(hour), minute=int(minute))
    if kind == "day":
        if candidate <= point:
            candidate += timedelta(days=1)
    else:
        delta = (_WEEKDAYS[kind] - candidate.weekday()) % 7
        candidate += timedelta(days=delta)
        if candidate <= point:
            candidate += timedelta(days=7)
    return candidate.astimezone(UTC)


class RoutineService:
    """Persistence/lifecycle facade; execution is injected so it cannot bypass Engine gates."""

    def __init__(self, store, submit: Callable[[dict], object] | None = None):
        self.store, self.submit = store, submit

    def create(self, routine: Routine) -> Routine:
        ZoneInfo(routine.timezone)
        routine.next_run = routine.next_run or next_occurrence(routine.schedule, routine.timezone)
        with self.store.transaction() as tx:
            tx.agents.get(routine.owner_agent_id)
            tx.routines.add(routine)
            tx.log("routine_created", actor=routine.owner_agent_id, routine_id=routine.id)
        return routine

    def update(self, routine_id: str, **changes) -> Routine:
        allowed = {"mission_template", "schedule", "timezone", "enabled", "retry_policy"}
        if set(changes) - allowed:
            raise ValueError("routine field is not editable")
        with self.store.transaction() as tx:
            routine = tx.routines.get(routine_id)
            for key, value in changes.items():
                setattr(routine, key, value)
            ZoneInfo(routine.timezone)
            if "schedule" in changes or "timezone" in changes:
                routine.next_run = next_occurrence(routine.schedule, routine.timezone)
            routine.updated_at = now()
            tx.routines.save(routine)
            tx.log("routine_updated", actor=routine.owner_agent_id, routine_id=routine.id)
            return routine

    def pause(self, routine_id: str) -> Routine:
        return self.update(routine_id, enabled=False)

    def resume(self, routine_id: str) -> Routine:
        return self.update(routine_id, enabled=True)

    def archive(self, routine_id: str) -> Routine:
        with self.store.transaction() as tx:
            routine = tx.routines.get(routine_id)
            routine.status, routine.enabled, routine.updated_at = "archived", False, now()
            tx.routines.save(routine)
            tx.log("routine_archived", actor=routine.owner_agent_id, routine_id=routine.id)
            return routine

    def tick(self, at: datetime | None = None) -> list[str]:
        """Submit due templates with durable, bounded retry state.

        ``retry_policy`` accepts ``max_attempts`` (default 2) and an optional
        ``retry_delay_seconds`` (default 300, capped at one day). A terminal
        dispatch failure advances to the normal next occurrence and records a
        failed notification state rather than hot-looping on restart.
        """
        if self.submit is None:
            return []
        current, dispatched = (at or now()), []
        with self.store.transaction() as tx:
            due = tx.routines.list(enabled=True, status="active", limit=10000)
        for routine in due:
            if routine.next_run is None or routine.next_run > current:
                continue
            try:
                mission = self.submit(routine.mission_template)
            except Exception as exc:
                with self.store.transaction() as tx:
                    fresh = tx.routines.get(routine.id)
                    maximum = min(20, max(0, int(fresh.retry_policy.get("max_attempts", 2))))
                    delay = min(
                        86400, max(1, int(fresh.retry_policy.get("retry_delay_seconds", 300)))
                    )
                    fresh.retry_count += 1
                    if fresh.retry_count <= maximum:
                        fresh.next_run = current + timedelta(seconds=delay)
                        fresh.notification_state = "pending"
                        event = "routine_retry_scheduled"
                    else:
                        fresh.next_run = next_occurrence(fresh.schedule, fresh.timezone, current)
                        fresh.retry_count = 0
                        fresh.notification_state = "failed"
                        event = "routine_dispatch_exhausted"
                    fresh.updated_at = now()
                    tx.routines.save(fresh)
                    tx.log(
                        event,
                        actor=fresh.owner_agent_id,
                        routine_id=fresh.id,
                        error=type(exc).__name__,
                    )
                continue
            with self.store.transaction() as tx:
                fresh = tx.routines.get(routine.id)
                fresh.last_run = current
                fresh.next_run = next_occurrence(fresh.schedule, fresh.timezone, current)
                fresh.retry_count, fresh.notification_state = 0, "pending"
                fresh.updated_at = now()
                tx.routines.save(fresh)
                # The Engine normally persists the mission, but keep this
                # scheduler usable with an injected submitter too; audit
                # detail must not introduce an FK dependency on its return.
                tx.log(
                    "routine_dispatched",
                    actor=fresh.owner_agent_id,
                    routine_id=fresh.id,
                    submitted_mission_id=getattr(mission, "id", None),
                )
            dispatched.append(routine.id)
        return dispatched
