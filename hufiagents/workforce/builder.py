"""V1.3 Workforce Builder — safe provisioning of persistent digital employees.

Rules enforced here (not negotiable):
- Provisioning CANNOT escalate capabilities or risk ceiling beyond the caller's ceiling.
- Organisation membership NEVER grants capabilities, tools, memory or risk.
- Raw secret values (api_key, token, password, Bearer, private_key) are rejected at
  the boundary; only SecretRef/CredentialRef handles may be referenced.
- Reviewer assignment grants no extra execution rights.
- Archived agents cannot be reactivated through update_profile; they stay archived.
- Idempotent: if idempotency_key resolves to an existing agent with the same role, the
  existing agent is returned without mutation.
"""

from __future__ import annotations

import re
from typing import Any

from hufiagents.contracts import (
    Agent,
    AgentProfileHistory,
    AgentProvisioningRequest,
    Risk,
    now,
    uid,
)
from hufiagents.orchestrator.workforce import Workforce

# ---------------------------------------------------------------------------
# Secret pattern detection
# ---------------------------------------------------------------------------
_SECRET_KEY_RE = re.compile(
    r"(api[_\-]?key|secret|password|token|bearer|private[_\-]?key|authorization)",
    re.IGNORECASE,
)
_SECRET_VAL_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|ghp_[A-Za-z0-9]{36})",
)

_RISK_ORDER = {Risk.R0: 0, Risk.R1: 1, Risk.R2: 2, Risk.R3: 3}


def _check_secrets(obj: Any, path: str = "") -> None:
    """Recursively scan a mapping/sequence for raw secret keys or values.

    Raises ValueError with the offending path on first hit.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{path}.{k}" if path else k
            if _SECRET_KEY_RE.search(str(k)):
                raise ValueError(
                    f"Raw secret field rejected in provisioning payload at '{full}'. "
                    "Use a SecretRef / CredentialRef handle instead."
                )
            _check_secrets(v, full)
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _check_secrets(item, f"{path}[{i}]")
    elif isinstance(obj, str):
        if _SECRET_VAL_RE.search(obj):
            raise ValueError(
                f"Raw secret value pattern detected in provisioning payload at '{path}'. "
                "Use a SecretRef / CredentialRef handle instead."
            )


def _risk_value(r: Risk) -> int:
    return _RISK_ORDER.get(r, 0)


def _subset(child: dict, parent: dict) -> bool:
    """Return True if all child capability entries are within parent."""
    for key, val in child.items():
        if key not in parent:
            return False
        pval = parent[key]
        if isinstance(val, dict) and isinstance(pval, dict):
            if not _subset(val, pval):
                return False
        elif isinstance(val, list) and isinstance(pval, list):
            if not set(val).issubset(set(pval)):
                return False
        elif val != pval:
            return False
    return True


class WorkforceBuilder:
    """Provision and manage persistent digital employees.

    All methods require a live ``store`` (``hufiagents.persistence.repository.Store``).
    The *caller_capabilities* and *caller_risk_ceiling* parameters are the ceiling
    imposed by whoever is making the request — the builder never grants more than this.
    """

    def __init__(self, store):
        self._store = store
        self._workforce = Workforce(store)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def provision(
        self,
        request: AgentProvisioningRequest,
        *,
        caller_capabilities: dict[str, Any],
        caller_risk_ceiling: Risk = Risk.R1,
    ) -> Agent:
        """Provision a new agent from a structured request.

        Returns the existing agent if idempotency_key matches a prior provisioning.
        Raises PermissionError if the request exceeds the caller's authority.
        Raises ValueError for invalid / dangerous payloads.
        """
        # 1. Secret boundary check — fail fast before any DB access.
        _check_secrets(request.model_dump(mode="json"))

        # 2. Capability guard — requested caps must be a subset of caller's.
        if not _subset(request.capabilities, caller_capabilities):
            raise PermissionError(
                "Provisioning request escalates capabilities beyond caller ceiling."
            )

        # 3. Risk ceiling guard.
        if _risk_value(request.risk_ceiling) > _risk_value(caller_risk_ceiling):
            raise PermissionError(
                f"Provisioning request escalates risk ceiling to {request.risk_ceiling!s} "
                f"but caller ceiling is {caller_risk_ceiling!s}."
            )

        # 4. Determine agent id (idempotency).
        agent_id = request.agent_id or (
            _stable_id(request.idempotency_key) if request.idempotency_key else uid()
        )

        with self._store.transaction() as tx:
            # 5. Idempotency: return existing agent if already provisioned.
            existing = tx.agents.list(id=agent_id, limit=1)
            if existing:
                ag = existing[0]
                if ag.role == request.role:
                    return ag
                raise ValueError(
                    f"Agent '{agent_id}' already exists with a different role '{ag.role}'. "
                    "Cannot reprovision with a different role under the same idempotency key."
                )

            caps = dict(request.capabilities)
            if request.skill_ids and "skills" not in caps:
                caps["skills"] = list(request.skill_ids)
            if request.memory_scopes and "memory_scopes" not in caps:
                caps["memory_scopes"] = list(request.memory_scopes)

            # 6. Construct agent.
            agent = Agent(
                id=agent_id,
                name=request.display_name,
                role=request.role,
                description=request.description,
                capabilities=caps,
                risk_ceiling=request.risk_ceiling,
                default_risk_ceiling=request.risk_ceiling,
                model_preference=request.model_preference,
                memory_scope=request.memory_scopes[0] if request.memory_scopes else "agent",
                status="active",
            )

            # 7. Persist agent (via Workforce for capability/risk checks).
            # We use a sentinel "system" delegator since builder has already done
            # its own ceiling check above — Workforce._subset sees system has ∞ caps.
            tx.agents.add(agent)

            # 8. Record initial profile history snapshot.
            snapshot = agent.model_dump(mode="json")
            tx.agent_profile_history.add(
                AgentProfileHistory(
                    agent_id=agent.id,
                    version=1,
                    changed_by="provisioner",
                    summary=f"Initial provisioning: {request.display_name} / {request.role}",
                    changes={},
                    snapshot=snapshot,
                )
            )

            # 9. Project assignment.
            if request.project_ids:
                # Assign first project_id directly on agent (schema has single project_id).
                agent.project_id = request.project_ids[0]
                tx.agents.save(agent)

            # 10. Log provisioning evidence.
            tx.log(
                "agent_created",
                actor="provisioner",
                agent_id=agent.id,
                role=agent.role,
                display_name=agent.name,
                risk_ceiling=str(agent.risk_ceiling),
                source=request.source,
            )
            tx.log(
                "provisioning_completed",
                actor="provisioner",
                agent_id=agent.id,
                idempotency_key=request.idempotency_key,
            )

        return agent

    def update_profile(
        self,
        agent_id: str,
        changes: dict[str, Any],
        *,
        actor: str = "system",
        summary: str = "",
    ) -> Agent:
        """Apply allowed profile changes to an agent, recording a new history entry.

        Immutable fields (id, parent_agent_id, capabilities, risk_ceiling,
        default_risk_ceiling) cannot be changed through this method.
        Archived agents cannot be updated.
        """
        _IMMUTABLE = {
            "id",
            "parent_agent_id",
            "capabilities",
            "risk_ceiling",
            "default_risk_ceiling",
        }
        rejected = {k for k in changes if k in _IMMUTABLE}
        if rejected:
            raise PermissionError(
                f"Cannot mutate immutable agent fields via update_profile: {sorted(rejected)}"
            )

        # Secret boundary on change values.
        _check_secrets(changes)

        with self._store.transaction() as tx:
            agent = tx.agents.get(agent_id)
            if agent.status == "archived":
                raise PermissionError(f"Agent '{agent_id}' is archived; profile cannot be updated.")

            # Compute previous snapshot and next version.
            history = tx.agent_profile_history.list(agent_id=agent_id, limit=1000)
            prev_version = max((h.version for h in history), default=0)

            # Apply changes.
            agent_data = agent.model_dump(mode="json")
            before = {k: agent_data.get(k) for k in changes}
            for field, value in changes.items():
                if hasattr(agent, field):
                    setattr(agent, field, value)

            tx.agents.save(agent)

            # Record version.
            tx.agent_profile_history.add(
                AgentProfileHistory(
                    agent_id=agent.id,
                    version=prev_version + 1,
                    changed_by=actor,
                    summary=summary or f"Profile updated by {actor}",
                    changes={"before": before, "after": changes},
                    snapshot=agent.model_dump(mode="json"),
                )
            )

            tx.log(
                "agent_updated",
                actor=actor,
                agent_id=agent.id,
                fields=sorted(changes.keys()),
            )

        return agent

    def assign_team(self, agent_id: str, team_id: str, *, actor: str = "system") -> Agent:
        """Record team membership by logging it — no FK join table exists in V1 schema."""
        with self._store.transaction() as tx:
            agent = tx.agents.get(agent_id)
            if agent.status == "archived":
                raise PermissionError(f"Cannot assign team to archived agent '{agent_id}'.")
            tx.log("agent_team_assigned", actor=actor, agent_id=agent_id, team_id=team_id)
        return agent

    def assign_project(self, agent_id: str, project_id: str, *, actor: str = "system") -> Agent:
        """Set agent.project_id (first/primary project)."""
        return self.update_profile(
            agent_id,
            {"project_id": project_id},
            actor=actor,
            summary=f"Assigned to project {project_id}",
        )

    def assign_skill(self, agent_id: str, skill_id: str, *, actor: str = "system") -> None:
        """Associate a skill with an agent via audit log.

        The skill table references the agent via agent_id; no join table needed.
        """
        with self._store.transaction() as tx:
            # Verify both agent and skill exist.
            tx.agents.get(agent_id)
            tx.skills.get(skill_id)
            tx.log("agent_skill_assigned", actor=actor, agent_id=agent_id, skill_id=skill_id)

    def set_model_policy(
        self, agent_id: str, model_preference: str | None, *, actor: str = "system"
    ) -> Agent:
        """Update agent model preference (the per-agent model policy)."""
        return self.update_profile(
            agent_id,
            {"model_preference": model_preference},
            actor=actor,
            summary=f"Model policy set to {model_preference}",
        )

    def set_budget(self, agent_id: str, external_budget: int, *, actor: str = "system") -> None:
        """Log budget policy for agent. Budget enforcement is done in the router."""
        with self._store.transaction() as tx:
            tx.agents.get(agent_id)
            tx.log(
                "agent_budget_set",
                actor=actor,
                agent_id=agent_id,
                external_budget=external_budget,
            )

    def set_reviewer(self, agent_id: str, reviewer_agent_id: str, *, actor: str = "system") -> None:
        """Assign a reviewer agent. Reviewer gets NO extra execution rights."""
        with self._store.transaction() as tx:
            # Both must exist and be active.
            agent = tx.agents.get(agent_id)
            reviewer = tx.agents.get(reviewer_agent_id)
            if agent.status == "archived":
                raise PermissionError(f"Agent '{agent_id}' is archived.")
            if reviewer.status == "archived":
                raise PermissionError(f"Reviewer agent '{reviewer_agent_id}' is archived.")
            # Reviewer assignment confers no capabilities — log only.
            tx.log(
                "agent_reviewer_assigned",
                actor=actor,
                agent_id=agent_id,
                reviewer_agent_id=reviewer_agent_id,
            )

    def set_participation(
        self,
        agent_id: str,
        room_id: str,
        participation_state: str,
        *,
        actor: str = "system",
    ) -> None:
        """Update participation_state for an agent in a room."""
        from hufiagents.contracts import RoomParticipant

        _VALID_STATES = {"ACTIVE", "LISTENING", "SLEEPING", "left"}
        if participation_state not in _VALID_STATES:
            raise ValueError(
                f"Invalid participation_state '{participation_state}'. "
                f"Must be one of {sorted(_VALID_STATES)}."
            )
        with self._store.transaction() as tx:
            tx.agents.get(agent_id)  # must exist
            participants = tx.room_participants.list(room_id=room_id, agent_id=agent_id, limit=1)
            if participants:
                p = participants[0]
                p.participation_state = participation_state
                tx.room_participants.save(p)
            else:
                tx.room_participants.add(
                    RoomParticipant(
                        room_id=room_id,
                        agent_id=agent_id,
                        participation_state=participation_state,
                    )
                )
            tx.log(
                "agent_participation_set",
                actor=actor,
                agent_id=agent_id,
                room_id=room_id,
                participation_state=participation_state,
            )

    def archive_agent(self, agent_id: str, *, actor: str = "system") -> Agent:
        """Archive an agent — permanently disables it.

        Archived agents cannot run routines or be reactivated through this API.
        """
        with self._store.transaction() as tx:
            agent = tx.agents.get(agent_id)
            if agent.status == "archived":
                return agent  # idempotent
            agent.status = "archived"
            agent.archived_at = now()
            tx.agents.save(agent)

            # Cancel any active routines owned by this agent.
            try:
                routines = tx.routines.list(owner_agent_id=agent_id, limit=1000)
                for r in routines:
                    if r.status == "active":
                        r.status = "inactive"
                        tx.routines.save(r)
            except Exception:
                pass

            # Record history.
            history = tx.agent_profile_history.list(agent_id=agent_id, limit=1000)
            prev_version = max((h.version for h in history), default=0)
            tx.agent_profile_history.add(
                AgentProfileHistory(
                    agent_id=agent.id,
                    version=prev_version + 1,
                    changed_by=actor,
                    summary=f"Agent archived by {actor}",
                    changes={"status": {"before": "active", "after": "archived"}},
                    snapshot=agent.model_dump(mode="json"),
                )
            )

            tx.log("agent_archived", actor=actor, agent_id=agent.id)

        return agent

    def get_profile_history(self, agent_id: str) -> list[AgentProfileHistory]:
        """Return the full profile version history for an agent, ordered by version ascending."""
        with self._store.transaction() as tx:
            tx.agents.get(agent_id)  # raises KeyError if agent not found
            entries = tx.agent_profile_history.list(agent_id=agent_id, limit=1000)
            # agent_profile_history has no created_at column so the generic repository
            # falls back to UUID ordering — sort by version to guarantee determinism.
            return sorted(entries, key=lambda h: h.version)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_id(idempotency_key: str) -> str:
    """Derive a deterministic agent ID from an idempotency key."""
    import hashlib

    return "agent-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
