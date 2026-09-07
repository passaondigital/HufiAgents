"""ADR-008: a crash after a non-file effect but before its result commits cannot be
proven exactly-once by an idempotency key alone, so ToolGateway must fail closed
for manual reconciliation instead of silently re-running (or silently accepting)
an uncertain shell/git effect. The `after_effect` e2e crash test only exercises
this path for the `files` tool (which is safe to reconcile by content equality);
this test proves the fail-closed branch for every other tool directly, without a
real subprocess crash."""

import hashlib
import json

import pytest

from hufiagents.contracts import Agent, Mission, Risk, Task, ToolCall
from hufiagents.persistence.repository import Store
from hufiagents.risk import Policy
from hufiagents.tools.gateway import ToolGateway


class RecordingShellTool:
    id = "shell"
    executed = False

    async def classify(self, action, params):
        return Risk.R1

    async def execute(self, call):
        RecordingShellTool.executed = True
        raise AssertionError("must not execute an uncertain prior effect")


def idempotency_key(task_id, tool_id, action, target, params):
    return hashlib.sha256(
        json.dumps([task_id, tool_id, action, target, params], sort_keys=True).encode()
    ).hexdigest()


async def test_uncertain_non_file_effect_fails_closed(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    gateway = ToolGateway(store, Policy(tmp_path / "missing-policy.yaml"))
    agent = Agent(
        id="builder",
        role="test",
        capabilities={"tools": ["shell"], "providers": []},
        default_risk_ceiling=Risk.R4,
    )
    action, target, params = "run_command", "workspace", {"command": "pwd"}
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="test"))
        task = tx.tasks.add(
            Task(
                mission_id=mission.id,
                objective="test",
                allowed_tools=["shell"],
                risk_ceiling=Risk.R4,
                status="running",
            )
        )
        tx.agents.add(agent)
        # Simulate a crash recorded mid-execution: gateway.invoke() committed
        # execution_started=True right before calling tool.execute(), then the
        # process died before the result transaction (docs/CORE-V1.md "Recovery").
        tx.tool_calls.add(
            ToolCall(
                task_id=task.id,
                tool="shell",
                action=action,
                target=target,
                params=params,
                risk_class=Risk.R1,
                policy_decision="auto_allow",
                idempotency_key=idempotency_key(task.id, "shell", action, target, params),
                execution_started=True,
                result_status="blocked",
            )
        )

    tool = RecordingShellTool()
    with pytest.raises(PermissionError, match="uncertain prior effect"):
        await gateway.invoke(task, agent, tool, action, target, params)
    assert tool.executed is False
    store.close()
