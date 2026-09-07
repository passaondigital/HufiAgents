"""Independent adversarial regressions; all credentials are synthetic fixtures."""

import base64
import subprocess

import pytest

from hufiagents.tools.process import run_process
from hufiagents.tools.workspace import Workspace
from tests.support.git_http_server import basic_auth_git_server, make_bare_http_repo
from tests.unit.test_git_push_credentials import call, committed_workspace


async def test_pushurl_cannot_redirect_credentials(tmp_path):
    root = tmp_path / "http"
    root.mkdir()
    bare = make_bare_http_repo(root)
    with basic_auth_git_server(root, username="x-access-token", password="fixture-only") as url:
        workspace, tool = await committed_workspace(
            tmp_path, "https://github.com/allowed/repo.git", push_token="fixture-only"
        )
        subprocess.run(
            ["git", "config", "remote.origin.pushurl", f"{url}/repo.git"],
            cwd=workspace.root,
            check=True,
        )
        with pytest.raises(PermissionError):
            await tool.execute(call("push"))
    refs = subprocess.run(["git", "--git-dir", str(bare), "show-ref"], capture_output=True)
    assert refs.returncode == 1


async def test_credential_output_is_not_persistable_even_if_encoded_or_truncated(tmp_path):
    value = "synthetic-opaque-value-839122"
    encoded = base64.b64encode(f"x-access-token:{value}".encode()).decode()
    result = await run_process(
        ["/usr/bin/printf", "%s", "x" * 15995 + value + encoded],
        Workspace(tmp_path),
        call("push"),
        extra_env={"HUFI_GIT_PUSH_TOKEN": value},
    )
    assert result.result_summary == "credentialed subprocess completed (output suppressed)"


@pytest.mark.parametrize(
    "key,value",
    [
        ("remote.origin.push", "+refs/heads/hufi/mission:refs/heads/main"),
        ("remote.origin.mirror", "true"),
        ("remote.origin.receivepack", "/bin/false"),
        ("url.https://evil.example/.pushInsteadOf", "https://github.com/"),
        ("credential.helper", "!env"),
        ("core.askpass", "/bin/env"),
        ("core.hooksPath", "/tmp/evil"),
        ("http.followRedirects", "true"),
        ("http.sslVerify", "false"),
        ("http.proxy", "http://evil.example"),
        ("http.extraHeader", "arbitrary"),
        ("pack.window", "0"),
        ("include.path", "/tmp/evil"),
    ],
)
async def test_unsafe_git_configuration_fails_closed(tmp_path, key, value):
    workspace, tool = await committed_workspace(
        tmp_path, "https://github.com/allowed/repo.git", push_token="fixture-only"
    )
    subprocess.run(["git", "config", key, value], cwd=workspace.root, check=True)
    with pytest.raises(PermissionError, match="unsafe Git configuration"):
        await tool.execute(call("push"))


@pytest.mark.parametrize(
    "url",
    [
        "https://user:fixture@github.com/o/r.git",
        "http://github.com/o/r.git",
        "https://github.com/o/r.git?x=1",
        "https://github.com/o/r.git#x",
        "https://github.com/o/../r.git",
        "https://github.com/o/%2e%2e/r.git",
        "ext::sh -c env",
        "ssh://git@github.com/o/r.git",
        "-x",
        "https://github.com/\nr.git",
        "https://github.com:bad/o/r.git",
        "https://github.com\\@evil.example/o/r.git",
    ],
)
def test_malicious_remote_rejected_without_echoing_input(url):
    from hufiagents.tools.git_security import validate_remote

    with pytest.raises(PermissionError) as error:
        validate_remote(url)
    assert str(error.value) == "unsafe configured Git remote"


@pytest.mark.parametrize(
    "branch",
    ["main", "master", "hufi/x:main", "hufi/x;env", "hufi/../main", "--all", "hufi/" + "x" * 81],
)
async def test_malicious_branch_rejected(tmp_path, branch):
    from hufiagents.tools.git import GitTool

    tool = GitTool(Workspace(tmp_path))
    await tool.execute(call("init"))
    with pytest.raises(PermissionError):
        await tool.execute(call("branch", branch=branch))


async def test_task_and_parent_cannot_inject_push_environment(tmp_path, monkeypatch):
    import asyncio

    from hufiagents.tools.git import ASKPASS_SCRIPT

    root = tmp_path / "http"
    root.mkdir()
    make_bare_http_repo(root)
    captured = []
    original = asyncio.create_subprocess_exec

    async def spy(*args, **kwargs):
        env = kwargs["env"]
        has_secret = "HUFI_GIT_PUSH_TOKEN" in env
        captured.append(("push" in args, has_secret))
        assert "HUFI_GITHUB_TOKEN" not in env
        assert "GIT_CONFIG_COUNT" not in env
        if has_secret:
            assert env["GIT_ASKPASS"] == str(ASKPASS_SCRIPT)
        else:
            assert "GIT_ASKPASS" not in env
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spy)
    monkeypatch.setenv("HUFI_GITHUB_TOKEN", "parent-fixture")
    monkeypatch.setenv("GIT_ASKPASS", "/bin/env")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "7")
    with basic_auth_git_server(root, username="x-access-token", password="fixture-only") as url:
        workspace, tool = await committed_workspace(
            tmp_path, f"{url}/repo.git", push_token="fixture-only"
        )
        result = await tool.execute(
            call(
                "push",
                remote_url="https://evil.example/x",
                env={"GIT_ASKPASS": "/bin/env"},
                GIT_ASKPASS="/bin/env",
            )
        )
    assert result.exit_code == 0
    assert sum(secret for _, secret in captured) == 1
    assert all(push for push, secret in captured if secret)


@pytest.mark.parametrize("mode", [0o644, 0o777])
async def test_askpass_bad_permissions_fail_closed(tmp_path, monkeypatch, mode):
    from hufiagents.tools import git

    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\nexit 1\n")
    helper.chmod(mode)
    monkeypatch.setattr(git, "ASKPASS_SCRIPT", helper)
    _, tool = await committed_workspace(
        tmp_path, "https://github.com/o/r.git", push_token="fixture"
    )
    with pytest.raises(PermissionError, match="unsafe askpass"):
        await tool.execute(call("push"))
    assert helper.stat().st_mode & 0o777 == mode


async def test_metadata_symlink_and_hardlink_are_rejected(tmp_path):
    from hufiagents.tools.git_security import validate_metadata

    workspace, _ = await committed_workspace(tmp_path, "https://github.com/o/r.git")
    link = workspace.root / ".git" / "linked"
    link.symlink_to(workspace.root / "note.md")
    with pytest.raises(PermissionError):
        validate_metadata(workspace.root)
    link.unlink()
    link.hardlink_to(workspace.root / "note.md")
    with pytest.raises(PermissionError):
        validate_metadata(workspace.root)


async def test_package_scripts_execute_only_inside_the_workspace_sandbox(tmp_path):
    from hufiagents.projects import Project
    from hufiagents.tools.shell import ShellTool

    workspace = Workspace(tmp_path)
    workspace.create(
        "package.json",
        '{"scripts":{"test":"node -e \\"require(\'fs\').writeFileSync(\'ESCAPED\',\'ok\')\\""}}',
    )
    project = Project(
        id="demo", repo_url="https://github.com/o/r.git", test_command=["/usr/bin/npm", "test"]
    )
    tool = ShellTool(workspace, project=project)
    result = await tool.execute(call("run_tests"))
    assert result.exit_code == 0
    # The script may write its mission checkout, but receives no capability to
    # write any mount outside it (covered by the adversarial bwrap probe).
    assert (tmp_path / "ESCAPED").exists()


async def test_http_redirect_is_not_followed(tmp_path):
    import http.server
    import threading

    root = tmp_path / "http"
    root.mkdir()
    bare = make_bare_http_repo(root)
    with basic_auth_git_server(root, username="x-access-token", password="fixture") as foreign:

        class Redirect(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", foreign + self.path)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _, tool = await committed_workspace(
                tmp_path, f"http://127.0.0.1:{server.server_port}/repo.git", push_token="fixture"
            )
            result = await tool.execute(call("push"))
            assert result.result_status == "error"
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    refs = subprocess.run(["git", "--git-dir", str(bare), "show-ref"], capture_output=True)
    assert refs.returncode == 1


@pytest.mark.parametrize("cancel", [True, False])
async def test_timeout_and_cancellation_reap_credential_process(tmp_path, monkeypatch, cancel):
    import asyncio
    import os

    spawned = []
    original = asyncio.create_subprocess_exec

    async def spy(*args, **kwargs):
        process = await original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spy)
    task = asyncio.create_task(
        run_process(
            ["/bin/sleep", "30"],
            Workspace(tmp_path),
            call("push"),
            timeout=30 if cancel else 0.05,
            extra_env={"HUFI_GIT_PUSH_TOKEN": "fixture"},
        )
    )
    while not spawned:
        await asyncio.sleep(0.005)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    assert spawned[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.kill(spawned[0].pid, 0)


def test_settings_read_token_as_secret_and_askpass_rejects_unknown_prompts(monkeypatch):
    from hufiagents.config import Settings
    from hufiagents.tools.git import ASKPASS_SCRIPT

    monkeypatch.setenv("HUFI_GITHUB_TOKEN", "opaque-fixture-991")
    settings = Settings(_env_file=None)
    assert settings.github_token.get_secret_value() == "opaque-fixture-991"
    assert "opaque-fixture-991" not in repr(settings)
    assert "opaque-fixture-991" not in settings.model_dump_json()
    result = subprocess.run(
        [str(ASKPASS_SCRIPT), "arbitrary prompt"],
        env={"HUFI_GIT_PUSH_TOKEN": "opaque-fixture-991"},
        capture_output=True,
    )
    assert result.returncode != 0
    assert result.stdout == b""


async def test_add_and_commit_also_require_hufi_branch(tmp_path):
    workspace, tool = await committed_workspace(tmp_path, "https://github.com/o/r.git")
    subprocess.run(
        ["git", "switch", "-c", "ordinary-feature"],
        cwd=workspace.root,
        check=True,
        capture_output=True,
    )
    for action in ("add", "commit"):
        with pytest.raises(PermissionError, match="hufi/ branch"):
            await tool.execute(call(action, path="note.md"))
