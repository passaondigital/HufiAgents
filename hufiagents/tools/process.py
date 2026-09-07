import asyncio
import contextlib
import ctypes
import os
import signal

from hufiagents.contracts import ToolResult, now
from hufiagents.redaction import redact
from hufiagents.tools.sandbox import credential_argv

PR_SET_PDEATHSIG = 1


def _linux_child_guard(expected_parent: int):
    """Set a death signal before exec and close the getppid race.

    PDEATHSIG protects the immediate child; credentialed commands additionally
    run in a bwrap PID namespace so killing that child also reaps descendants.
    """
    os.setsid()
    if ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != expected_parent:
        os.kill(os.getpid(), signal.SIGKILL)


async def run_process(argv, workspace, call, timeout=30, extra_env=None, sandboxed=False):
    # No inherited credentials, PATH overrides, Git config or Python/npm hooks.
    # extra_env is for narrow, caller-controlled additions (e.g. a scoped
    # GH_TOKEN) -- it is layered on top of, and can only add to, this fixed
    # baseline; it never comes from task/agent-supplied params.
    credentialed = bool(
        extra_env and (extra_env.get("HUFI_GIT_PUSH_TOKEN") or extra_env.get("GH_TOKEN"))
    )
    if credentialed:
        argv = credential_argv(argv, workspace.root)
    if sandboxed:
        # The caller supplies the complete bwrap argv.  A credentialed call is
        # never allowed through this route.
        if credentialed:
            raise PermissionError("credentialed project process forbidden")
    parent_pid = os.getpid()
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
        stdout=asyncio.subprocess.DEVNULL if credentialed else asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        preexec_fn=lambda: _linux_child_guard(parent_pid),
    )
    output = bytearray()
    truncated = False

    async def drain():
        nonlocal truncated
        if credentialed:
            await process.wait()
            return  # Credentialed output goes directly to /dev/null.
        while chunk := await process.stdout.read(4096):
            remaining = 16000 - len(output)
            output.extend(chunk[: max(0, remaining)])
            truncated |= len(chunk) > remaining
        await process.wait()

    try:
        await asyncio.wait_for(drain(), timeout=timeout)
    except asyncio.CancelledError:
        # Cancellation itself is already a hard stop request.  Do not await a
        # grace period here: a cancelled coroutine can be interrupted again,
        # leaving a credentialed bwrap tree orphaned.  TERM records the normal
        # intent; KILL immediately makes the cancellation boundary final.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # Reap the direct supervisor before propagating cancellation.  shield
        # keeps a second cancellation from abandoning the wait mid-cleanup.
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.shield(process.wait())
        raise
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=2)
        except TimeoutError:
            pass
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await asyncio.shield(process.wait())
        raise
    return ToolResult(
        **{
            **call.model_dump(),
            "executed_at": now(),
            "result_status": "ok" if process.returncode == 0 else "error",
            "exit_code": process.returncode,
            "result_summary": (
                "credentialed subprocess "
                + ("completed" if process.returncode == 0 else "failed")
                + " (output suppressed)"
                if credentialed
                else redact(output.decode(errors="replace"))
                + ("\n[truncated]" if truncated else "")
            ),
        }
    )
