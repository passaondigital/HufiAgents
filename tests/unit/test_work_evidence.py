from hufiagents.contracts import Mission, WorkEvidence
from hufiagents.persistence.repository import Store


def test_work_evidence_is_persistent_and_sanitized(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="evidence"))
        record = tx.work_evidence.add(
            WorkEvidence(
                mission_id=mission.id,
                source_type="tool",
                evidence_type="command",
                summary="remote check",
                content={"stdout": "PASSWORD=do-not-store"},
            )
        )
        assert record.redacted_at is not None
        assert "do-not-store" not in str(record.content)
    store.close()
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        loaded = tx.work_evidence.get(record.id)
        assert loaded.mission_id == mission.id
        assert "do-not-store" not in str(loaded.content)
    store.close()
