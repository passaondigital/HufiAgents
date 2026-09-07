"""Executed in a child process; exits abruptly at a real tool checkpoint."""

import asyncio
import os
import sys
from pathlib import Path

from hufiagents.config import Settings
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.tools.files import FilesTool


async def main():
    root, stage = Path(sys.argv[1]), sys.argv[2]
    settings = Settings(
        database_url=f"sqlite:///{root}/db.sqlite3",
        workspace_root=root / "ws",
        default_provider="fake",
        heartbeat_timeout_seconds=0.05,
        heartbeat_interval_seconds=0.01,
    )
    store = Store(settings.database_url)
    engine = Orchestrator(store, settings)
    engine.submit(MissionCreate(outcome="survive abrupt process death"))
    if stage == "after_result":
        invoke = engine.gateway.invoke

        async def crash(*args, **kwargs):
            await invoke(*args, **kwargs)
            os._exit(75)

        engine.gateway.invoke = crash
    else:

        class CrashFiles(FilesTool):
            async def execute(self, call):
                await super().execute(call)
                os._exit(75)

        engine.tools = lambda workspace: {"files": CrashFiles(workspace)}
    await engine.tick()
    await asyncio.gather(*engine.active.values())


if __name__ == "__main__":
    asyncio.run(main())
