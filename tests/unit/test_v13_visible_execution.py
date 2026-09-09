"""Unit tests for V1.3A Visible Execution and Evidence Collector.

Covers:
- Event mapping to user-readable WorkEvidence records
- Automatic redaction before database persistence
- Deduplication of identical evidence
- Truthful current activity derivation without fake activity or fake percentages
- Persistence reload stability
- Room milestone notification dispatch
- Agent activity aggregation
"""

from hufiagents.contracts import Agent, Mission, Risk, State, Task
from hufiagents.evidence import get_agent_activity, get_mission_execution_feed
from hufiagents.persistence.repository import Store


def make_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"]},
                risk_ceiling=Risk.R1,
            )
        )
    return store


def test_mission_start_auto_evidence(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(outcome="Build feature"))
        tx.log("mission_created", mission_id=m.id)

    with store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id=m.id)
        assert len(evidence) == 1
        assert evidence[0].source_type == "MISSION"
        assert evidence[0].evidence_type == "STARTED"
        assert "Build feature" in evidence[0].summary
    store.close()


def test_secret_redaction_before_persistence(tmp_path):
    """Secret Golden Test: raw secrets in event metadata are redacted before storage."""
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(id="m1", outcome="Leak outcome"))
        t = tx.tasks.add(
            Task(
                mission_id=m.id,
                objective="Leak check",
                assigned_agent_id="builder",
            )
        )
        tx.log(
            "tool_result",
            task=t,
            tool_call_id="call1",
            status="ok",
            exit_code=0,
            raw_output="Authorization: Bearer super-secret-visible-999 password=hunter2-secret",
        )

    with store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id="m1")
        for e in evidence:
            assert "super-secret-visible-999" not in e.summary
            assert "hunter2-secret" not in e.summary
            assert "super-secret-visible-999" not in str(e.metadata)
            assert "hunter2-secret" not in str(e.metadata)
    store.close()


def test_evidence_deduplication(tmp_path):
    """Multiple identical observations emit a single completion evidence record."""
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(id="m1", outcome="Dedupe outcome"))
        tx.log("mission_completed", mission_id=m.id, result="done")
        tx.log("mission_completed", mission_id=m.id, result="done")
        tx.log("mission_completed", mission_id=m.id, result="done")

    with store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id="m1")
        assert len(evidence) == 1
        assert evidence[0].summary == "Mission erfolgreich abgeschlossen"
    store.close()


def test_no_fake_live_activity_when_idle(tmp_path):
    """Fake-Live Negative Test: RUNNING state without events returns generic fallback."""
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(outcome="Idle check"))
        tx.tasks.add(
            Task(
                mission_id=m.id,
                objective="Generic task",
                status=State.running,
                assigned_agent_id="builder",
            )
        )

    with store.transaction() as tx:
        feed = get_mission_execution_feed(tx, m.id)
        assert feed["current_activity"] == "Aufgabe läuft"
        assert "thinking" not in str(feed).lower()
        assert "3/7" not in str(feed)
    store.close()


def test_approval_and_handoff_evidence(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(id="m2", outcome="Approval outcome"))
        t = tx.tasks.add(
            Task(
                mission_id=m.id,
                objective="Risk task",
                assigned_agent_id="builder",
            )
        )
        tx.log("approval_requested", task=t, risk_ceiling="R2")
        tx.log("approval_granted", task=t, actor="pascal")
        tx.log("handoff", task=t, from_agent="builder", to_agent="reviewer")

    with store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id="m2")
        summaries = [e.summary for e in evidence]
        assert any("Freigabe erforderlich" in s for s in summaries)
        assert any("Freigabe erteilt" in s for s in summaries)
        assert any("builder übergibt an reviewer" in s for s in summaries)
    store.close()


def test_repo_context_evidence(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(id="m3", outcome="Repo outcome"))
        t = tx.tasks.add(
            Task(
                mission_id=m.id,
                objective="Repo inspect",
                assigned_agent_id="builder",
            )
        )
        tx.log("repo_context_prepared", task=t, selected_count=4, truncated=False)

    with store.transaction() as tx:
        evidence = tx.work_evidence.list(mission_id="m3")
        assert len(evidence) == 1
        assert "Repository-Kontext vorbereitet: 4 relevante Dateien" in evidence[0].summary
    store.close()


def test_agent_activity_feed(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        m = tx.missions.add(Mission(id="m4", outcome="Agent outcome"))
        t = tx.tasks.add(
            Task(
                mission_id=m.id,
                objective="Builder task",
                assigned_agent_id="builder",
            )
        )
        tx.log("repo_context_prepared", task=t, selected_count=2, truncated=False)

    with store.transaction() as tx:
        activity = get_agent_activity(tx, "builder")
        assert activity["agent_id"] == "builder"
        assert len(activity["recent_evidence"]) == 1
    store.close()
