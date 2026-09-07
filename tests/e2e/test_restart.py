import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.persistence.repository import Store


@pytest.mark.parametrize("stage", ["after_result", "after_effect"])
async def test_real_process_crash_recovery(tmp_path, stage):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("crash_worker.py")), str(tmp_path), stage],
        timeout=15,
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        capture_output=True,
    )
    assert result.returncode == 75, result.stderr.decode()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/db.sqlite3",
        workspace_root=tmp_path / "ws",
        default_provider="fake",
        heartbeat_timeout_seconds=0.05,
        heartbeat_interval_seconds=0.01,
    )
    store = Store(settings.database_url)
    with store.transaction() as tx:
        task = tx.tasks.list()[0]
        assert task.status == State.running
        call = tx.tool_calls.list()[0]
        assert call.result_status == ("ok" if stage == "after_result" else "blocked")
        artifact = settings.workspace_root / task.mission_id / call.target
        original_stat = artifact.stat()
    await asyncio.sleep(0.06)
    engine = Orchestrator(store, settings)
    engine.recover()
    await engine.tick()
    await asyncio.gather(*engine.active.values())
    with store.transaction() as tx:
        assert tx.tasks.get(task.id).status == State.completed
        assert len(tx.tool_calls.list()) == 1
        assert len(tx.reviews.list()) == 1
        events = tx.audit.list(mission_id=task.mission_id)
        assert any(e.event_type == "recovery" for e in events)
        if stage == "after_result":
            assert any(e.event_type == "tool_reused" for e in events)
    assert artifact.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert artifact.stat().st_ino == original_stat.st_ino
    await engine.stop()
    store.close()
