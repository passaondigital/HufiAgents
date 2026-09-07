import itertools

import pytest
from sqlalchemy.exc import IntegrityError

from hufiagents.contracts import AuditEvent, Mission, State, Task
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
