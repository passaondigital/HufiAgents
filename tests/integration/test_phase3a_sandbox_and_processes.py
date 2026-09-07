"""Real Linux boundary checks for Phase 3A hardening.

All fixtures are disposable and contain only synthetic credentials.  These
tests deliberately exercise bwrap rather than mocking its security boundary.
"""

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from hufiagents.contracts import Risk, ToolCall
from hufiagents.projects import Project
from hufiagents.tools.process import run_process
from hufiagents.tools.sandbox import available
from hufiagents.tools.shell import ShellTool
from hufiagents.tools.workspace import Workspace


def call(action="run_tests"):
    return ToolCall(
        task_id="sandbox-test",
        tool="shell",
        action=action,
        target="workspace",
        params={},
        risk_class=Risk.R1,
        policy_decision="auto_allow",
        idempotency_key=action,
    )


def project(command):
    return Project(
        id="sandbox", repo_url="https://github.com/example/repo.git", test_command=command
    )


@pytest.mark.skipif(not available(), reason="Bubblewrap unavailable: executor must fail closed")
async def test_project_script_is_confined_to_workspace_with_no_network_or_credentials(tmp_path):
    workspace = Workspace(tmp_path / "mission-a")
    outside = tmp_path / "outside-write"
    script = workspace.root / "probe.sh"
    network_probe = (
        "require('net').connect(9,'1.1.1.1')"
        ".on('connect',()=>process.exit(92)).on('error',()=>process.exit(0))"
    )
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            test ! -e /home/administrator/.ssh
            test ! -e /home/administrator/.config
            test ! -e /home/administrator/.gitconfig
            test ! -e /srv
            test ! -e /var/run/docker.sock
            test ! -e /workspace/../mission-b
            test -z "$HUFI_GITHUB_TOKEN"
            test -z "$HUFI_GIT_PUSH_TOKEN"
            if touch {outside}; then exit 91; fi
            /usr/bin/node -e '{network_probe}'
            /usr/bin/node -e "require('fs').writeFileSync('/workspace/probe-ok','ok')"
            """
        )
    )
    os.chmod(script, 0o700)
    os.environ["HUFI_GITHUB_TOKEN"] = "parent-secret-never-in-sandbox"
    os.environ["HUFI_GIT_PUSH_TOKEN"] = "parent-push-secret-never-in-sandbox"
    try:
        result = await ShellTool(workspace, project=project(["/bin/sh", "probe.sh"])).execute(
            call()
        )
    finally:
        os.environ.pop("HUFI_GITHUB_TOKEN", None)
        os.environ.pop("HUFI_GIT_PUSH_TOKEN", None)
    assert result.exit_code == 0
    assert (workspace.root / "probe-ok").exists()
    assert not outside.exists()


async def test_project_script_fails_closed_when_bwrap_is_missing(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr("hufiagents.tools.sandbox.BWRAP", "/not-present/bwrap")
    with pytest.raises(PermissionError, match="Bubblewrap sandbox"):
        await ShellTool(workspace, project=project(["/bin/echo", "never"])).execute(call())


async def test_project_script_fails_closed_when_bwrap_setup_fails(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr("hufiagents.tools.sandbox.available", lambda: True)
    monkeypatch.setattr("hufiagents.tools.sandbox.BWRAP", "/bin/false")
    result = await ShellTool(workspace, project=project(["/bin/echo", "never"])).execute(call())
    assert result.result_status == "error"
    assert result.exit_code != 0


def _credential_pids(marker: bytes) -> set[int]:
    found = set()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if marker in (proc / "environ").read_bytes():
                found.add(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return found


@pytest.mark.skipif(
    not available(), reason="Bubblewrap unavailable: credential execution fails closed"
)
@pytest.mark.parametrize("death", ["sigkill", "sigterm"])
async def test_parent_death_reaps_credential_child_and_grandchild(tmp_path, death):
    marker = b"phase3a-process-tree-fixture"
    worker = tmp_path / "worker.py"
    worker.write_text(
        textwrap.dedent(
            """\
            import asyncio
            from pathlib import Path
            from hufiagents.contracts import Risk, ToolCall
            from hufiagents.tools.process import run_process
            from hufiagents.tools.workspace import Workspace
            async def main():
                call = ToolCall(task_id='t', tool='git', action='push', target='w', params={},
                    risk_class=Risk.R2, policy_decision='auto_allow', idempotency_key='x')
                await run_process(['/bin/sh', '-c',
                    '/bin/sh -c "sleep 30 & wait" & sleep 30 & wait'], Workspace(Path('w')), call,
                    timeout=40, extra_env={'HUFI_GIT_PUSH_TOKEN': 'phase3a-process-tree-fixture'})
            asyncio.run(main())
            """
        )
    )
    worker_env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    parent = subprocess.Popen([sys.executable, str(worker)], cwd=tmp_path, env=worker_env)
    try:
        for _ in range(100):
            if len(_credential_pids(marker)) >= 2:  # bwrap/Git shell plus a descendant
                break
            time.sleep(0.05)
        assert len(_credential_pids(marker)) >= 2
        if death == "sigkill":
            parent.kill()
        else:
            parent.terminate()
        parent.wait(timeout=5)
        for _ in range(100):
            if not _credential_pids(marker):
                break
            time.sleep(0.05)
        assert _credential_pids(marker) == set()
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        for pid in _credential_pids(marker):
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


@pytest.mark.skipif(
    not available(), reason="Bubblewrap unavailable: credential execution fails closed"
)
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_timeout_and_cancel_reap_credential_process_tree(tmp_path, mode):
    marker = b"phase3a-cancel-timeout-fixture"
    call_ = ToolCall(
        task_id="t",
        tool="git",
        action="push",
        target="w",
        params={},
        risk_class=Risk.R2,
        policy_decision="auto_allow",
        idempotency_key=mode,
    )
    task = asyncio.create_task(
        run_process(
            ["/bin/sh", "-c", '/bin/sh -c "sleep 30 & wait" & sleep 30 & wait'],
            Workspace(tmp_path),
            call_,
            timeout=0.15 if mode == "timeout" else 30,
            extra_env={"HUFI_GIT_PUSH_TOKEN": marker.decode()},
        )
    )
    for _ in range(100):
        if _credential_pids(marker):
            break
        await asyncio.sleep(0.01)
    if mode == "cancel":
        task.cancel()
    with pytest.raises(asyncio.CancelledError if mode == "cancel" else TimeoutError):
        await task
    for _ in range(100):
        if not _credential_pids(marker):
            break
        await asyncio.sleep(0.01)
    assert _credential_pids(marker) == set()
