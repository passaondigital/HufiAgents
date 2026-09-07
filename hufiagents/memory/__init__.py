"""Explicit scope ownership and an optional read-only canonical knowledge bridge."""

from hufiagents.contracts import MemoryRecord
from hufiagents.tools.workspace import Workspace


class Memory:
    def __init__(self, store):
        self.store = store

    def put(self, layer, owner_id, key, value, *, actor):
        if layer not in {"task_context", "project_knowledge", "agent_memory"}:
            raise PermissionError("unknown memory layer")
        with self.store.transaction() as tx:
            if layer == "task_context":
                task = tx.tasks.get(owner_id)
                permitted = actor in {"system", task.assigned_agent_id, "reviewer"}
            elif layer == "agent_memory":
                permitted = actor == owner_id
            else:
                tasks = tx.tasks.list(mission_id=owner_id)
                permitted = actor == "system" or any(t.assigned_agent_id == actor for t in tasks)
            if not permitted:
                raise PermissionError("memory owner mismatch")
            repository = getattr(tx, layer)
            return repository.add(MemoryRecord(owner_id=owner_id, key=key, value=value))


def read_global(root, target):
    # Deliberately avoid Workspace's mkdir: this bridge never mutates its source.
    if not root.is_dir() or root.is_symlink():
        raise FileNotFoundError("global knowledge root unavailable")
    bridge = object.__new__(Workspace)
    bridge.root = root.resolve()
    return bridge.read(target)
