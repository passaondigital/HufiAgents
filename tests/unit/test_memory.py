"""hufiagents.memory (architecture §9 memory boundaries, ADR-004 read-only global
bridge) had zero test coverage before this review. It is also not yet called by
the orchestrator (which writes task_context directly as a trusted system actor),
so this is the only place its owner/permission enforcement is exercised at all."""

import pytest

from hufiagents.contracts import Mission, Task
from hufiagents.memory import Memory, read_global
from hufiagents.persistence.repository import Store


def make_store(tmp_path):
    return Store(f"sqlite:///{tmp_path}/db.sqlite3")


def test_task_context_permitted_for_system_assignee_and_reviewer(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="test"))
        task = tx.tasks.add(
            Task(mission_id=mission.id, objective="test", assigned_agent_id="builder")
        )
    memory = Memory(store)
    for actor in ["system", "builder", "reviewer"]:
        memory.put("task_context", task.id, "note", {"x": 1}, actor=actor)
    with pytest.raises(PermissionError):
        memory.put("task_context", task.id, "note", {"x": 1}, actor="someone_else")
    store.close()


def test_agent_memory_scoped_to_owner_only(tmp_path):
    store = make_store(tmp_path)
    memory = Memory(store)
    memory.put("agent_memory", "builder", "note", {"x": 1}, actor="builder")
    with pytest.raises(PermissionError):
        memory.put("agent_memory", "builder", "note", {"x": 1}, actor="reviewer")
    store.close()


def test_project_knowledge_scoped_to_system_and_mission_assignees(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        mission = tx.missions.add(Mission(outcome="test"))
        tx.tasks.add(Task(mission_id=mission.id, objective="test", assigned_agent_id="builder"))
    memory = Memory(store)
    memory.put("project_knowledge", mission.id, "note", {"x": 1}, actor="system")
    memory.put("project_knowledge", mission.id, "note", {"x": 1}, actor="builder")
    with pytest.raises(PermissionError):
        memory.put("project_knowledge", mission.id, "note", {"x": 1}, actor="reviewer")
    store.close()


def test_unknown_layer_rejected(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(PermissionError):
        Memory(store).put("audit_log", "x", "y", {}, actor="system")
    store.close()


def test_read_global_bridge_is_read_only_and_rejects_symlink_or_missing_root(tmp_path):
    real_root = tmp_path / "knowledge"
    real_root.mkdir()
    (real_root / "note.md").write_text("canonical")
    assert read_global(real_root, "note.md") == "canonical"

    with pytest.raises(FileNotFoundError):
        read_global(tmp_path / "absent", "note.md")

    symlinked = tmp_path / "link-root"
    symlinked.symlink_to(real_root)
    with pytest.raises(FileNotFoundError):
        read_global(symlinked, "note.md")

    with pytest.raises(PermissionError):
        read_global(real_root, "../escape")
