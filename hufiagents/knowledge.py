import re
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

    def select_skills(
        self,
        query: str,
        *,
        scope_ids: Iterable[str | None] = (),
        agent_skill_names: Iterable[str] = (),
        limit: int = 5,
    ) -> list[Skill]:
        words = set(re.findall(r"\w+", query.lower()))
        assigned_names = set(agent_skill_names)
        scope_set = {s for s in scope_ids if s is not None}
        with self.store.transaction() as tx:
            all_skills = [
                s for s in tx.skills.list(status="approved", limit=10000) if s.status == "approved"
            ]
            items = []
            for s in all_skills:
                is_assigned = (
                    s.name in assigned_names
                    or s.id in assigned_names
                    or (s.scope_type == "agent" and s.scope_id in scope_set)
                )
                is_in_scope = s.scope_type == "global" or s.scope_id in scope_set
                if is_assigned or is_in_scope:
                    s_words = set(re.findall(r"\w+", f"{s.name} {s.description}".lower()))
                    overlap = len(words & s_words)
                    if is_assigned or overlap > 0 or not words:
                        items.append((s, overlap, is_assigned))

            items.sort(
                key=lambda item: (
                    item[2],  # is_assigned first
                    item[1],  # word overlap
                    item[0].updated_at,
                ),
                reverse=True,
            )
            chosen = [item[0] for item in items[:limit]]
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

    def relevant_memories(
        self,
        query: str,
        *,
        scopes: Iterable[tuple[str, str | None]],
        limit: int = 10,
    ) -> list[ScopedMemory]:
        allowed = set(scopes)
        words = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
        with self.store.transaction() as tx:
            rows = [
                m
                for m in tx.scoped_memories.list(limit=10000)
                if getattr(m, "status", "approved") == "approved"
                and (
                    (m.scope_type, m.scope_id) in allowed
                    or (m.scope_type == "global" and ("global", None) in allowed)
                    or (m.scope_type == "shared" and any(st == "shared" for st, _ in allowed))
                )
            ]
            scored = []
            for m in rows:
                score_text = f"{m.summary} {m.content} {m.category}".lower()
                m_words = set(re.findall(r"[a-zA-Z0-9]+", score_text))
                overlap = len(words & m_words)
                q = query.strip().lower()
                exact_match = 10 if q and q in score_text else 0
                total_score = overlap + exact_match
                if not words or total_score > 0:
                    scored.append((m, total_score))

            scored.sort(
                key=lambda item: (
                    item[1],  # overlap score + exact match
                    item[0].importance,
                    item[0].updated_at,
                ),
                reverse=True,
            )
            chosen = [item[0] for item in scored[:limit]]
            for m in chosen:
                m.last_used_at = now()
                tx.scoped_memories.save(m)
                tx.log("memory_read", actor="system", memory_id=m.id, scope_type=m.scope_type)
            return chosen

    def assemble_context(
        self,
        intent: str,
        *,
        scopes=(),
        agent_id=None,
        agent_skill_names=(),
        max_memory_items=10,
        max_skill_items=5,
        max_context_chars=12000,
        max_context_tokens_estimate=3000,
    ):
        memories = self.relevant_memories(intent, scopes=scopes, limit=max_memory_items)
        scope_ids = [sid for _, sid in scopes if sid is not None]
        skills = self.select_skills(
            intent,
            scope_ids=scope_ids,
            agent_skill_names=agent_skill_names,
            limit=max_skill_items,
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
            "memories": memories,
            "skills": skills,
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
            review_sets = [tx.reviews.list(task_id=t.id, limit=10000) for t in tasks]
            approved = bool(tasks) and all(
                reviews and reviews[-1].verdict == "approve" for reviews in review_sets
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
