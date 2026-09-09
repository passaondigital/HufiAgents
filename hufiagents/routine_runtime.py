"""Autonomous Routine Scheduler Runtime (V1.3A).

Periodically ticks the RoutineService from the main application lifespan loop,
detecting due routines, claiming occurrences atomically, and submitting real
Missions to the Orchestrator.
"""

import asyncio
import contextlib
from datetime import datetime
from typing import Any

from hufiagents.contracts import now
from hufiagents.workforce.routines import RoutineService


class RoutineScheduler:
    """Background loop that periodically ticks the RoutineService."""

    def __init__(
        self,
        routine_service: RoutineService,
        poll_interval_seconds: float = 30.0,
    ):
        self.routine_service = routine_service
        self.poll_interval_seconds = poll_interval_seconds
        self.loop_task: asyncio.Task | None = None
        self.stopping = False
        self.last_tick_at: datetime | None = None
        self.last_error: str | None = None
        self.tick_count: int = 0

    async def start(self):
        """Start the background scheduler loop."""
        self.stopping = False
        self.loop_task = asyncio.create_task(self._loop())

    async def stop(self):
        """Stop the background scheduler loop gracefully."""
        self.stopping = True
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task

    async def _loop(self):
        """Internal loop running every poll_interval_seconds."""
        while not self.stopping:
            try:
                await self.tick()
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(self.poll_interval_seconds)

    async def tick(self) -> list[str]:
        """Perform one scheduler tick; returns dispatched routine IDs."""
        self.last_tick_at = now()
        self.tick_count += 1
        return self.routine_service.tick(at=self.last_tick_at)

    @property
    def status(self) -> dict[str, Any]:
        """Diagnostic state summary."""
        return {
            "running": bool(self.loop_task and not self.loop_task.done()),
            "last_tick_at": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "last_error": self.last_error,
            "tick_count": self.tick_count,
            "poll_interval_seconds": self.poll_interval_seconds,
        }
