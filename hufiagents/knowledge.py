"""Persistent V1.2 skills, scoped memory, context assembly and learning."""

from collections.abc import Iterable

from hufiagents.contracts import LearningRecord, ScopedMemory, Skill, now
from hufiagents.redaction import redact


def _safe(value):
    return redact(value)


class KnowledgeService:
    def __init__(self, store):
        self.store = store

    def create_skill(self, skill: Skill, *, actor="system"):
        skill = skill.model_copy(
            update={"description": _safe(skill.description), "steps": _safe(skill.steps)}
        )
        with self.store.transaction() as tx:
            tx.skills.add(skill)
            tx.log("skill_created", actor=actor, skill_id=skill.id, name=skill.name)
        return skill

    def select_skills(self, query: str, *, scope_ids=(), limit=5):
        words = set(query.lower().split())
        with self.store.transaction() as tx:
            items = [
                s
                for s in tx.skills.list(status="approved", limit=10000)
                if s.scope_type == "global" or s.scope_id in set(scope_ids)
            ]
            items.sort(
                key=lambda s: (
                    len(words & set((s.name + " " + s.description).lower().split())),
                    s.updated_at,
                ),
                reverse=True,
            )
            chosen = items[:limit]
            for skill in chosen:
                skill.last_used_at = now()
                skill.success_count += 1
                tx.skills.save(skill)
                tx.log("skill_selected", actor="system", skill_id=skill.id)
            return chosen

    def create_memory(self, memory: ScopedMemory, *, actor="system"):
        safe = memory.model_copy(
            update={"summary": _safe(memory.summary), "content": _safe(memory.content)}
        )
        with self.store.transaction() as tx:
            tx.scoped_memories.add(safe)
            tx.log(
                "memory_created",
                actor=actor,
                memory_id=safe.id,
                scope_type=safe.scope_type,
                scope_id=safe.scope_id,
            )
        return safe

    def relevant_memories(self, query: str, *, scopes: Iterable[tuple[str, str | None]], limit=10):
        allowed = set(scopes)
        words = set(query.lower().split())
        with self.store.transaction() as tx:
            rows = [
                m
                for m in tx.scoped_memories.list(limit=10000)
                if (m.scope_type, m.scope_id) in allowed
                or (m.scope_type == "shared" and (m.scope_type, m.scope_id) in allowed)
            ]
            rows.sort(
                key=lambda m: (
                    len(words & set((m.summary + " " + m.content).lower().split())),
                    m.importance,
                    m.updated_at,
                ),
                reverse=True,
            )
            rows = rows[:limit]
            for m in rows:
                m.last_used_at = now()
                tx.scoped_memories.save(m)
                tx.log("memory_read", actor="system", memory_id=m.id, scope_type=m.scope_type)
            return rows

    def assemble_context(
        self,
        intent: str,
        *,
        scopes=(),
        agent_id=None,
        max_memory_items=10,
        max_skill_items=5,
        max_context_chars=12000,
        max_context_tokens_estimate=3000,
    ):
        memories = self.relevant_memories(intent, scopes=scopes, limit=max_memory_items)
        skills = self.select_skills(
            intent, scope_ids=[sid for _, sid in scopes], limit=max_skill_items
        )
        parts = ["MISSION: " + intent]
        if memories:
            parts.append("MEMORY:\n" + "\n".join(f"- {m.summary}: {m.content}" for m in memories))
        if skills:
            parts.append(
                "SKILLS:\n"
                + "\n".join(f"- {s.name}: " + "; ".join(str(x) for x in s.steps) for s in skills)
            )
        text = "\n\n".join(parts)
        compacted = len(text) > max_context_chars or len(text) // 4 > max_context_tokens_estimate
        if compacted:
            text = text[:max_context_chars][: max_context_tokens_estimate * 4]
            with self.store.transaction() as tx:
                tx.log(
                    "context_compacted",
                    actor="system",
                    max_context_chars=max_context_chars,
                    max_context_tokens_estimate=max_context_tokens_estimate,
                )
        return {
            "text": text,
            "memory_ids": [m.id for m in memories],
            "skill_ids": [s.id for s in skills],
            "compacted": compacted,
        }

    def learn(
        self,
        mission_id: str,
        *,
        candidate: Skill | None = None,
        memory: ScopedMemory | None = None,
        actor="system",
    ):
        with self.store.transaction() as tx:
            mission = tx.missions.get(mission_id)
            tasks = tx.tasks.list(mission_id=mission_id, limit=10000)
            approved = bool(tasks) and all(
                tx.reviews.list(task_id=t.id, limit=10000)[-1].verdict == "approve"
                for t in tasks
                if tx.reviews.list(task_id=t.id, limit=10000)
            )
            if mission.status.value != "completed" or not approved:
                rec = LearningRecord(
                    mission_id=mission_id,
                    outcome="skipped",
                    reason="mission must be completed and reviewer-approved",
                )
                tx.learning_records.add(rec)
                tx.log("learning_skipped", actor=actor, mission_id=mission_id, reason=rec.reason)
                return rec
            if candidate and candidate.source == "learned":
                candidate.status = "draft"
                candidate = candidate.model_copy(
                    update={
                        "description": _safe(candidate.description),
                        "steps": _safe(candidate.steps),
                    }
                )
                tx.skills.add(candidate)
                rec = LearningRecord(
                    mission_id=mission_id, outcome="skill_proposed", target_id=candidate.id
                )
                tx.log(
                    "skill_created",
                    actor=actor,
                    mission_id=mission_id,
                    skill_id=candidate.id,
                    status="draft",
                )
            elif memory:
                memory = memory.model_copy(
                    update={"summary": _safe(memory.summary), "content": _safe(memory.content)}
                )
                tx.scoped_memories.add(memory)
                rec = LearningRecord(
                    mission_id=mission_id, outcome="memory_created", target_id=memory.id
                )
                tx.log("memory_created", actor=actor, mission_id=mission_id, memory_id=memory.id)
            else:
                rec = LearningRecord(
                    mission_id=mission_id, outcome="skipped", reason="no reusable candidate"
                )
                tx.log("learning_skipped", actor=actor, mission_id=mission_id, reason=rec.reason)
            tx.learning_records.add(rec)
            tx.log("learning_completed", actor=actor, mission_id=mission_id, outcome=rec.outcome)
            return rec
