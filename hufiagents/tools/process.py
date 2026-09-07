import asyncio
import os
import signal

from hufiagents.contracts import ToolResult, now
from hufiagents.redaction import redact


async def run_process(argv, workspace, call, timeout=30, extra_env=None):
    # No inherited credentials, PATH overrides, Git config or Python/npm hooks.
    # extra_env is for narrow, caller-controlled additions (e.g. a scoped
    # GH_TOKEN) -- it is layered on top of, and can only add to, this fixed
    # baseline; it never comes from task/agent-supplied params.
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=workspace.root,
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": str(workspace.root),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            **(extra_env or {}),
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    output = bytearray()
    truncated = False

    async def drain():
        nonlocal truncated
        while chunk := await process.stdout.read(4096):
            remaining = 16000 - len(output)
            output.extend(chunk[: max(0, remaining)])
            truncated |= len(chunk) > remaining
        await process.wait()

    try:
        await asyncio.wait_for(drain(), timeout=timeout)
    except (TimeoutError, asyncio.CancelledError):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
        raise
    return ToolResult(
        **{
            **call.model_dump(),
            "executed_at": now(),
            "result_status": "ok" if process.returncode == 0 else "error",
            "exit_code": process.returncode,
            "result_summary": redact(output.decode(errors="replace"))
            + ("\n[truncated]" if truncated else ""),
        }
    )
