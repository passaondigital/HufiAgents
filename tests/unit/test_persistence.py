import itertools
import time

import pytest
from sqlalchemy.exc import IntegrityError

from hufiagents.contracts import ApprovalRequest, AuditEvent, Mission, Risk, State, Task, ToolCall
from hufiagents.orchestrator.state import ALLOWED, validate_transition
from hufiagents.persistence.repository import Store


@pytest.mark.parametrize("source,target", itertools.product(State, State))
def test_all_lifecycle_edges(source, target):
    if target in ALLOWED[source]:
        validate_transition(source, target)
    else:
        with pytest.raises(ValueError):
            validate_transition(source, target)


def test_transaction_rollback_audit_and_migrations(tmp_path):
    url = f"sqlite:///{tmp_path}/state.sqlite3"
    store = Store(url)
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="test"))
        task = tx.tasks.add(Task(mission_id=mission.id, objective="test"))
    with pytest.raises(RuntimeError), store.transaction() as tx:
        tx.transition(tx.tasks.get(task.id), State.planning)
        raise RuntimeError("fault injection")
    with store.transaction() as tx:
        assert tx.tasks.get(task.id).status == State.queued
        assert tx.audit.list() == []
        tx.audit.append(AuditEvent(event_type="test"))
    with pytest.raises(IntegrityError), store.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM audit_log")
    with pytest.raises(IntegrityError), store.engine.begin() as connection:
        connection.exec_driver_sql("UPDATE audit_log SET actor='bad'")
    store.close()
    store = Store(url)
    with store.transaction() as tx:
        assert tx.missions.get(mission.id).outcome == "test"
        assert len(tx.audit.list()) == 1
    store.close()


def test_tool_call_and_approval_lists_are_chronological_not_by_id(tmp_path):
    """Rows.list() ordered by `self.table.c.get("created_at", ... "ts" ... "id")`.
    ToolCall and ApprovalRequest have neither `created_at` nor `ts` (they use
    `requested_at`), so listing silently fell back to ordering by the random UUID
    `id` column instead of time. Ids below are chosen to sort in the opposite
    order from insertion time, so a regression back to id-ordering fails loudly."""
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="test"))
        task = tx.tasks.add(Task(mission_id=mission.id, objective="test"))
        tx.tool_calls.add(
            ToolCall(
                id="z-first-call",
                task_id=task.id,
                tool="files",
                action="read_file",
                target="a",
                risk_class=Risk.R0,
                policy_decision="auto_allow",
                idempotency_key="key-1",
            )
        )
    time.sleep(0.01)
    with store.transaction() as tx:
        tx.tool_calls.add(
            ToolCall(
                id="a-second-call",
                task_id=task.id,
                tool="files",
                action="read_file",
                target="b",
                risk_class=Risk.R0,
                policy_decision="auto_allow",
                idempotency_key="key-2",
            )
        )
        tx.approvals.add(
            ApprovalRequest(id="z-first-approval", task_id=task.id, risk_class=Risk.R3, summary="a")
        )
    time.sleep(0.01)
    with store.transaction() as tx:
        tx.approvals.add(
            ApprovalRequest(
                id="a-second-approval", task_id=task.id, risk_class=Risk.R3, summary="b"
            )
        )
    with store.transaction() as tx:
        assert [c.id for c in tx.tool_calls.list(task_id=task.id)] == [
            "z-first-call",
            "a-second-call",
        ]
        assert [a.id for a in tx.approvals.list(task_id=task.id)] == [
            "z-first-approval",
            "a-second-approval",
        ]
    store.close()
