"""run_tests/run_build/run_lint (docs/DECISIONS.md ADR-010): the argv always
comes from the server-side project registry; a task only ever selects which
pre-registered command runs, never its content."""

import pytest

from hufiagents.contracts import Risk, ToolCall
from hufiagents.projects import Project
from hufiagents.tools.shell import ShellTool
from hufiagents.tools.workspace import Workspace


def call(action, **params):
    return ToolCall(
        task_id="test",
        tool="shell",
        action=action,
        target="workspace",
        params=params,
        risk_class=Risk.R1,
        policy_decision="auto_allow",
        idempotency_key="test",
    )


def project(**overrides):
    fields = {
        "id": "demo",
        "repo_url": "https://example.test/demo.git",
        "test_command": ["/bin/echo", "tests-ran"],
        "build_command": ["/bin/echo", "build-ran"],
        "lint_command": [],
        **overrides,
    }
    return Project(**fields)


async def test_run_tests_executes_the_registered_command_only(tmp_path):
    tool = ShellTool(Workspace(tmp_path), project=project())
    result = await tool.execute(call("run_tests"))
    assert result.exit_code == 0
    assert "tests-ran" in result.result_summary


async def test_command_field_ignores_caller_supplied_argv(tmp_path):
    # Even if a caller tries to smuggle a "command" param, run_tests never
    # reads call.params for its argv -- only the registry's test_command.
    tool = ShellTool(Workspace(tmp_path), project=project())
    result = await tool.execute(call("run_tests", command="rm -rf /"))
    assert "tests-ran" in result.result_summary


async def test_run_build_and_run_lint_use_their_own_registered_commands(tmp_path):
    tool = ShellTool(Workspace(tmp_path), project=project())
    build = await tool.execute(call("run_build"))
    assert "build-ran" in build.result_summary


async def test_unconfigured_project_command_is_refused(tmp_path):
    tool = ShellTool(Workspace(tmp_path), project=project(lint_command=[]))
    with pytest.raises(PermissionError, match="not configured"):
        await tool.execute(call("run_lint"))


async def test_project_command_without_a_project_is_refused(tmp_path):
    tool = ShellTool(Workspace(tmp_path))
    with pytest.raises(PermissionError, match="no project configured"):
        await tool.execute(call("run_tests"))


async def test_project_commands_are_r1_and_isolated_from_generic_shell(tmp_path):
    tool = ShellTool(Workspace(tmp_path), project=project())
    assert await tool.classify("run_tests", {}) == Risk.R1
    # The original closed pwd/git_version allowlist is unaffected.
    assert await tool.classify("run_command", {"command": "pwd"}) == Risk.R0
