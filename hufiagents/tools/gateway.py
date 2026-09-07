"""Classify -> persist intent -> approval -> bounded execution -> persisted result."""

import asyncio
import hashlib
import json

from hufiagents.contracts import ApprovalRequest, State, ToolCall, now
from hufiagents.redaction import redact


class ApprovalPending(Exception):
    pass


class ToolGateway:
    def __init__(self, store, policy):
        self.store, self.policy = store, policy

    async def invoke(self, task, agent, tool, action, target, params):
        risk = await tool.classify(action, {**params, "target": target})
        decision = self.policy.decide(risk, task, agent, tool.id, action)
        key = hashlib.sha256(
            json.dumps([task.id, tool.id, action, target, params], sort_keys=True).encode()
        ).hexdigest()
        with self.store.transaction() as tx:
            current = tx.tasks.get(task.id)
            if current.status != State.running:
                raise PermissionError("tool requires a running task")
            existing = tx.tool_calls.list(idempotency_key=key)
            if existing:
                call = existing[0]
                if call.result_status == "ok":
                    tx.log("tool_reused", task=task, tool_call_id=call.id)
                    return call
                if call.execution_started and tool.id != "files":
                    raise PermissionError("uncertain prior effect; manual reconciliation required")
            else:
                call = ToolCall(
                    task_id=task.id,
                    tool=tool.id,
                    action=action,
                    target=target,
                    params=redact(params),
                    risk_class=risk,
                    policy_decision=decision,
                    idempotency_key=key,
                )
                tx.tool_calls.add(call)
                tx.log(
                    "tool_call",
                    task=task,
                    tool_call_id=call.id,
                    tool=tool.id,
                    action=action,
                    target=target,
                    risk_class=risk,
                    policy_decision=decision,
                )
            approved = tx.approvals.list(tool_call_id=call.id, status="approved")
            if decision == "approval_required" and not approved:
                if not tx.approvals.list(tool_call_id=call.id, status="pending"):
                    approval = tx.approvals.add(
                        ApprovalRequest(
                            tool_call_id=call.id,
                            risk_class=risk,
                            summary=f"{tool.id}.{action} on {target}",
                        )
                    )
                    tx.log(
                        "approval_requested",
                        task=task,
                        approval_id=approval.id,
                        tool_call_id=call.id,
                        risk_class=risk,
                    )
                tx.transition(current, State.waiting_approval)
            elif decision in {"denied", "reviewer_gate"}:
                # R2 preflight has no approved external executor in V1. Reject before effect.
                call.result_summary = (
                    "policy denied" if decision == "denied" else "R2 preflight rejected"
                )
                tx.tool_calls.save(call)
                tx.log("policy_blocked", task=task, tool_call_id=call.id, decision=decision)
        if decision == "approval_required" and not approved:
            raise ApprovalPending()
        if decision in {"denied", "reviewer_gate"}:
            raise PermissionError("tool not authorized by capability/risk policy")
        with self.store.transaction() as tx:
            call.execution_started = True
            tx.tool_calls.save(call)
            tx.log("tool_started", task=task, tool_call_id=call.id)
        # Actual parameters are held in memory, never use persisted redacted secrets as inputs.
        execution = call.model_copy(update={"params": params})
        try:
            result = await tool.execute(execution)
            result.params = redact(params)
            result.result_summary = redact(result.result_summary)
        except (Exception, asyncio.CancelledError) as exc:
            with self.store.transaction() as tx:
                call.result_status = "timeout" if isinstance(exc, TimeoutError) else "error"
                call.result_summary = type(exc).__name__
                call.executed_at = now()
                tx.tool_calls.save(call)
                tx.log(
                    "tool_result",
                    task=task,
                    tool_call_id=call.id,
                    status=call.result_status,
                    error=type(exc).__name__,
                )
            raise
        with self.store.transaction() as tx:
            tx.tool_calls.save(result)
            tx.log(
                "tool_result",
                task=task,
                tool_call_id=call.id,
                status=result.result_status,
                exit_code=result.exit_code,
            )
        if result.result_status != "ok":
            raise RuntimeError("tool failed")
        return result
