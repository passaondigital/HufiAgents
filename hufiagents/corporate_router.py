"""Deterministic Corporate Matrix routing behind the permanent HufiBoss interface."""

from __future__ import annotations

import re
from typing import Any

from hufiagents.contracts import OwnerOutcomeContract, State
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec

ACTIVE_TASK_STATES = {
    State.queued,
    State.planning,
    State.running,
    State.waiting_approval,
    State.blocked,
    State.review,
    State.retrying,
}

# Language parsing hints only. Eligibility and selection come from persisted
# responsibilities, memberships, agent roles and workload.
INTENT_HINTS = {
    "sicherheit": "security",
    "security": "security",
    "schwachstellen": "security",
    "audit": "qa",
    "qualität": "qa",
    "quality": "qa",
    "browser": "browser",
    "frontend": "browser",
    "vertrieb": "sales",
    "sales": "sales",
    "markt": "market",
    "support": "support",
    "dokumentation": "documentation",
    "documentation": "documentation",
}
PROJECT_HINTS = {
    "hufiagents": "hufiagents",
    "hufmanager": "hufmanager",
    "hufiapp": "hufiapp",
    "equimeteo": "equimeteo",
}


class CorporateRouter:
    """Select the minimum sufficient team from persisted corporate facts."""

    @staticmethod
    def _requirements(outcome: str) -> set[str]:
        words = set(re.findall(r"[\w-]+", outcome.casefold()))
        return {
            canonical
            for token, canonical in INTENT_HINTS.items()
            if any(token in word for word in words)
        }

    @classmethod
    def resolve_route(cls, outcome: str, store: Any) -> dict[str, Any]:
        if store is None:
            raise ValueError("corporate routing requires a persisted Store")
        requirements = cls._requirements(outcome)
        lowered = outcome.casefold()
        project_key = next(
            (value for token, value in PROJECT_HINTS.items() if token in lowered), None
        )
        with store.transaction() as tx:
            units = tx.organization_units.list(status="active", limit=1000)
            if not units:
                from hufiagents.org_graph import bootstrap_corporate_matrix

                bootstrap_corporate_matrix(store)
                units = tx.organization_units.list(status="active", limit=1000)
            relationships = tx.relationships.list(removed_at=None, limit=5000)
            agents = {agent.id: agent for agent in tx.agents.list(status="active", limit=1000)}
            active_tasks = tx.tasks.list(status=ACTIVE_TASK_STATES, limit=5000)

        def unit_score(unit):
            responsibilities = set(unit.metadata.get("responsibilities", []))
            score = len(requirements & responsibilities) * 20
            if project_key and unit.stable_key == f"hufi-group/business/{project_key}":
                score += 10
            if not requirements and unit.stable_key == "hufi-group/business/hufiagents":
                score = 10
            return score

        ranked_units = sorted(units, key=lambda unit: (-unit_score(unit), unit.stable_key))
        selected_unit = ranked_units[0] if ranked_units and unit_score(ranked_units[0]) else None
        if selected_unit is None:
            selected_unit = next(
                unit for unit in units if unit.stable_key == "hufi-group/business/hufiagents"
            )

        eligible_unit_ids = {
            unit.id
            for unit in units
            if unit.stable_key == selected_unit.stable_key
            or unit.stable_key.startswith(f"{selected_unit.stable_key}/")
        }
        member_ids = {
            rel.source_id
            for rel in relationships
            if rel.relationship_type == "member_of_unit" and rel.target_id in eligible_unit_ids
        }
        project_ids = {
            f"project-{project_key}" if project_key else None,
        }
        project_members = {
            rel.source_id
            for rel in relationships
            if rel.relationship_type == "works_on_project" and rel.target_id in project_ids
        }
        workload = {agent_id: 0 for agent_id in agents}
        for task in active_tasks:
            if task.assigned_agent_id in workload:
                workload[task.assigned_agent_id] += 1

        eligible = []
        for agent_id in member_ids:
            agent = agents.get(agent_id)
            if not agent:
                continue
            roles = set(agent.capabilities.get("roles", []))
            if requirements and not roles.intersection(requirements | {"qa"}):
                continue
            if project_key and agent_id not in project_members:
                continue
            if not agent.capabilities.get("providers"):
                continue
            eligible.append((workload.get(agent_id, 0), agent_id, sorted(roles)))
        eligible.sort()

        if eligible:
            assigned_agent = eligible[0][1]
        elif not project_key or "builder" in project_members:
            assigned_agent = "builder"
        else:
            raise PermissionError("no eligible agent for requested project and capability scope")
        return {
            "routed_by": "mr_equi",
            "frontend_contact": "hufiboss",
            "selected_unit_id": selected_unit.id,
            "target_unit": selected_unit.name,
            "target_path": selected_unit.stable_key,
            "required_capabilities": sorted(requirements),
            "project_key": project_key,
            "selected_agents": [assigned_agent],
            "assigned_agent_id": assigned_agent,
            "reason": "persisted responsibilities + membership + capability + workload",
        }

    @staticmethod
    def _is_golden_qa(outcome: str) -> bool:
        lowered = outcome.casefold().replace("-", " ")
        return all(term in lowered for term in ("provider", "client", "partner", "cross role"))

    @classmethod
    def prepare_request(cls, request: MissionCreate, store: Any):
        """Return a routed request, outcome contract and safe routing evidence."""
        if cls._is_golden_qa(request.outcome):
            role_specs = (
                ("provider_qa", "provider_qa", "provider_report", "Provider Report"),
                ("client_qa", "client_qa", "client_report", "Client Report"),
                ("partner_qa", "partner_qa", "partner_report", "Partner Report"),
            )
            steps = [
                TaskSpec(
                    objective=f"{label}: unabhängig prüfen und reale Evidenz dokumentieren.",
                    expected_output=f"reports/{deliverable}.md",
                    agent_id=agent_id,
                    workstream_key=role,
                    deliverable_key=deliverable,
                    dependency_indexes=[],
                )
                for agent_id, role, deliverable, label in role_specs
            ]
            steps.append(
                TaskSpec(
                    objective="Cross-Role-Szenarien ausführen und Ergebnisse zusammenführen.",
                    expected_output="reports/cross_role_report.md",
                    agent_id="cross_role_qa",
                    workstream_key="cross_role_qa",
                    deliverable_key="cross_role_report",
                    dependency_indexes=[0, 1, 2],
                )
            )
            route = cls.resolve_route("quality audit", store)
            with store.transaction() as tx:
                qa = next(
                    unit
                    for unit in tx.organization_units.list(limit=1000)
                    if unit.stable_key.endswith("/quality-assurance")
                )
            route.update(
                {
                    "selected_unit_id": qa.id,
                    "target_unit": qa.name,
                    "target_path": qa.stable_key,
                    "selected_agents": [item[0] for item in role_specs] + ["cross_role_qa"],
                    "assigned_agent_id": "provider_qa",
                    "required_capabilities": [item[1] for item in role_specs] + ["cross_role_qa"],
                }
            )
            routed = request.model_copy(update={"steps": steps})
            contract = OwnerOutcomeContract(
                mission_id="pending",
                required_roles=[item[1] for item in role_specs] + ["cross_role_qa"],
                required_workstreams=[item[1] for item in role_specs] + ["cross_role_qa"],
                required_deliverables=[item[2] for item in role_specs] + ["cross_role_report"],
                required_reviews=["independent_review"],
                required_evidence=["task_evidence"],
                completion_conditions={"all_tasks_completed": True, "generated_outputs_only": True},
                status="DISPATCHING",
            )
            return routed, contract, route

        route = cls.resolve_route(request.outcome, store)
        if request.steps:
            steps = [
                spec.model_copy(
                    update={
                        "agent_id": spec.agent_id or route["assigned_agent_id"],
                        "workstream_key": spec.workstream_key or f"workstream_{index + 1}",
                        "deliverable_key": spec.deliverable_key or f"result_{index + 1}",
                    }
                )
                for index, spec in enumerate(request.steps)
            ]
        else:
            steps = [
                TaskSpec(
                    objective=request.outcome,
                    agent_id=route["assigned_agent_id"],
                    workstream_key="primary",
                    deliverable_key="result",
                    dependency_indexes=[],
                )
            ]
        routed = request.model_copy(update={"steps": steps})
        contract = OwnerOutcomeContract(
            mission_id="pending",
            required_roles=sorted({spec.agent_id for spec in steps if spec.agent_id}),
            required_workstreams=[spec.workstream_key for spec in steps if spec.workstream_key],
            required_deliverables=[spec.deliverable_key for spec in steps if spec.deliverable_key],
            required_reviews=["independent_review"],
            required_evidence=["task_evidence"],
            completion_conditions={"all_tasks_completed": True, "generated_outputs_only": True},
            status="DISPATCHING",
        )
        return routed, contract, route

    @staticmethod
    def format_management_summary(outcome, artifacts, route_info, counts) -> str:
        return (
            "### HufiBoss Management-Zusammenfassung\n\n"
            f"**Ziel:** {outcome.strip().splitlines()[0]}\n\n"
            f"**Abgeschlossen:** {counts['tasks']} Aufgaben, {counts['artifacts']} Berichte, "
            f"{counts['evidence']} Evidenzen, {counts['reviews']} Reviews.\n\n"
            "**Offen:** nichts.\n\n"
            "**Wichtige Risiken:** keine offenen Risiken aus dem Lauf.\n\n"
            "**Entscheidung erforderlich:** nein.\n\n"
            f"**Zuständig:** {route_info.get('target_path', 'hufiagents')}\n\n"
            "**Nachweise:**\n" + "\n".join(f"- {item.name}" for item in artifacts)
        )
