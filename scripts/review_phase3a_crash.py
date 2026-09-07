"""Bounded hard-crash probe of the shared process runner, using sleep, no network.

Reports the missing parent-death boundary without exposing credential bytes.
Always kills its disposable child process group after observing the result.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from hufiagents.contracts import ToolCall
from hufiagents.tools.process import run_process
from hufiagents.tools.workspace import Workspace


async def worker(root):
    original = asyncio.create_subprocess_exec

    async def capture(*args, **kwargs):
        process = await original(*args, **kwargs)
        print(process.pid, flush=True)
        return process

    asyncio.create_subprocess_exec = capture
    call = ToolCall(
        task_id="crash-probe",
        tool="git",
        action="push",
        target="workspace",
        risk_class="R2",
        policy_decision="auto_allow",
        idempotency_key="crash-probe",
    )
    await run_process(
        ["/bin/sleep", "30"],
        Workspace(Path(root)),
        call,
        extra_env={"HUFI_GIT_PUSH_TOKEN": "disposable-fixture"},
    )


def probe():
    with tempfile.TemporaryDirectory(prefix="hufi-crash-review-") as root:
        parent = subprocess.Popen(
            [sys.executable, __file__, "--worker", root], stdout=subprocess.PIPE, text=True
        )
        child = None
        try:
            child = int(parent.stdout.readline())
            parent.kill()
            parent.wait(timeout=5)
            env = Path(f"/proc/{child}/environ")
            survived = env.exists() and b"HUFI_GIT_PUSH_TOKEN=" in env.read_bytes()
            print(
                json.dumps(
                    {
                        "credential_child_survives_parent_sigkill": survived,
                        "credential_values_reported": 0,
                    }
                )
            )
        finally:
            if child:
                try:
                    os.killpg(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
            parent.stdout.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(worker(sys.argv[2]))
    else:
        probe()
