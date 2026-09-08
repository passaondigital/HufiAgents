from hufiagents.contracts import Mission, ReviewResult, ScopedMemory, Skill, State, Task
from hufiagents.knowledge import KnowledgeService
from hufiagents.persistence.repository import Store


def test_scoped_memory_isolation_and_secret_sanitization():
    store = Store("sqlite:///:memory:")
    service = KnowledgeService(store)
    a = service.create_memory(
        ScopedMemory(
            scope_type="agent",
            scope_id="a",
            category="fact",
            summary="token test",
            content="token=ghp_FAKE123",
        )
    )
    service.create_memory(
        ScopedMemory(
            scope_type="agent", scope_id="b", category="fact", summary="other", content="visible"
        )
    )
    assert "ghp_FAKE123" not in a.content
    assert a.id not in [m.id for m in service.relevant_memories("token", scopes=[("agent", "b")])]
    assert service.relevant_memories("token", scopes=[("agent", "a")])[0].id == a.id


def test_context_is_bounded_and_records_compaction():
    store = Store("sqlite:///:memory:")
    service = KnowledgeService(store)
    service.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="p",
            category="fact",
            summary="important",
            content="x" * 500,
        )
    )
    result = service.assemble_context(
        "important",
        scopes=[("project", "p")],
        max_context_chars=100,
        max_context_tokens_estimate=30,
    )
    assert len(result["text"]) <= 100
    assert result["compacted"] is True
    with store.transaction() as tx:
        assert tx.audit.list(event_type="context_compacted")


def test_learning_requires_approved_completed_mission_and_keeps_learned_skill_draft():
    store = Store("sqlite:///:memory:")
    service = KnowledgeService(store)
    mission = Mission(outcome="do work")
    task = Task(mission_id=mission.id, objective="work", status=State.completed)
    with store.transaction() as tx:
        tx.missions.add(mission)
        tx.tasks.add(task)
        tx.reviews.add(ReviewResult(task_id=task.id, verdict="approve"))
        mission.status = State.completed
        tx.missions.save(mission)
    result = service.learn(mission.id, candidate=Skill(name="repeatable", source="learned"))
    assert result.outcome == "skill_proposed"
    with store.transaction() as tx:
        assert tx.skills.list(status="draft")[0].name == "repeatable"
        assert tx.audit.list(event_type="learning_completed")
