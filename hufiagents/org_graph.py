"""Typed company graph services.  Membership is additive and never identity."""
# The compact service functions intentionally keep transaction operations together.
# ruff: noqa: E501

import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from hufiagents.contracts import (
    Agent,
    AgentProvisioningRequest,
    ChatRoom,
    CredentialRef,
    GraphProject,
    GraphRelationship,
    OrganizationUnit,
    Resource,
    Risk,
    Team,
)

RELATIONSHIPS = {
    "reports_to",
    "member_of_team",
    "member_of_unit",
    "unit_belongs_to",
    "works_on_project",
    "responsible_for_resource",
    "may_use_resource",
    "reviews",
    "backup_for",
}

RISK_RANK = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


def _active(tx, relation):
    return tx.relationships.list(relationship_type=relation, removed_at=None, limit=10000)


def create_org_unit(
    tx,
    name,
    unit_type="DEPARTMENT",
    description="",
    parent_unit_id=None,
    project_id=None,
    metadata=None,
    stable_key=None,
):
    parent = None
    if parent_unit_id:
        parent = tx.organization_units.get(parent_unit_id)
        current = parent_unit_id
        seen = set()
        while current:
            if current in seen:
                raise ValueError("unit hierarchy cycle")
            seen.add(current)
            parent_unit = tx.organization_units.get(current)
            current = parent_unit.parent_unit_id
    local_key = stable_key or re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    if not local_key:
        raise ValueError("organization unit requires a language-neutral stable key")
    if parent and "/" not in local_key:
        local_key = f"{parent.stable_key}/{local_key}"
    if tx.organization_units.list(stable_key=local_key, limit=1):
        raise ValueError("organization unit stable key already exists")
    unit = tx.organization_units.add(
        OrganizationUnit(
            stable_key=local_key,
            name=name,
            unit_type=unit_type,
            description=description,
            parent_unit_id=parent_unit_id,
            project_id=project_id,
            metadata=metadata or {},
        )
    )
    tx.log("org_unit_created", unit_id=unit.id, name=unit.name, unit_type=unit.unit_type)
    return unit


def update_org_unit_parent(tx, unit_id, parent_unit_id):
    """Move a unit only when the stored parent chain remains acyclic."""
    unit = tx.organization_units.get(unit_id)
    current = parent_unit_id
    seen = {unit.id}
    while current:
        if current in seen:
            raise ValueError("unit hierarchy cycle")
        seen.add(current)
        current = tx.organization_units.get(current).parent_unit_id
    unit.parent_unit_id = parent_unit_id
    unit.updated_at = datetime.now(UTC)
    tx.organization_units.save(unit)
    return unit


def org_unit_descendants(tx, unit_id, limit=1000):
    """Bounded, cycle-safe breadth-first hierarchy traversal."""
    units = tx.organization_units.list(limit=limit)
    children = {}
    for unit in units:
        children.setdefault(unit.parent_unit_id, []).append(unit)
    result, queue, seen = [], [unit_id], {unit_id}
    while queue and len(result) < limit:
        parent_id = queue.pop(0)
        for child in children.get(parent_id, []):
            if child.id in seen:
                continue
            seen.add(child.id)
            result.append(child)
            queue.append(child.id)
    return result


def archive_org_unit(tx, unit_id):
    unit = tx.organization_units.get(unit_id)
    unit.status, unit.archived_at = "archived", datetime.now(UTC)
    tx.organization_units.save(unit)
    tx.log("org_unit_archived", unit_id=unit_id)
    return unit


def create_team(tx, name, description=""):
    team = tx.teams.add(Team(name=name, description=description))
    tx.log("team_created", team_id=team.id, name=team.name)
    return team


def archive_team(tx, team_id):
    team = tx.teams.get(team_id)
    team.status, team.archived_at = "archived", datetime.now(UTC)
    tx.teams.save(team)
    tx.log("team_archived", team_id=team_id)
    return team


def create_project(tx, name, description="", repository_ref=None):
    return tx.graph_projects.add(
        GraphProject(name=name, description=description, repository_ref=repository_ref)
    )


def create_resource(tx, name, resource_type="other", description="", metadata=None):
    return tx.resources.add(
        Resource(
            name=name, resource_type=resource_type, description=description, metadata=metadata or {}
        )
    )


def create_room(tx, room_type, host_type, host_id, name):
    room = tx.chat_rooms.add(
        ChatRoom(room_type=room_type, host_type=host_type, host_id=host_id, name=name)
    )
    tx.log("room_created", room_id=room.id, room_type=room_type, host_id=host_id)
    return room


def add_relationship(
    tx, relationship_type, source_type, source_id, target_type, target_id, primary=False
):
    if relationship_type not in RELATIONSHIPS:
        raise ValueError("unsupported relationship type")
    if source_type == target_type and source_id == target_id:
        raise ValueError("self relationships are not allowed")
    if relationship_type == "reports_to":
        if source_type != "agent" or target_type != "agent":
            raise ValueError("reports_to requires agent nodes")
        # Walk target's reporting chain to prevent obvious cycles.
        current = target_id
        seen = {source_id}
        while current:
            if current in seen:
                raise ValueError("reporting cycle")
            seen.add(current)
            edges = [e for e in _active(tx, "reports_to") if e.source_id == current and e.primary]
            current = edges[0].target_id if edges else None
    if relationship_type == "unit_belongs_to":
        current = target_id
        seen = {source_id}
        while current:
            if current in seen:
                raise ValueError("unit hierarchy cycle")
            seen.add(current)
            edges = [e for e in _active(tx, "unit_belongs_to") if e.source_id == current]
            current = edges[0].target_id if edges else None
    if relationship_type == "member_of_team":
        team = tx.teams.get(target_id)
        agent = next((a for a in tx.agents.list(id=source_id)), None)
        if team.status == "archived" or (agent and agent.status != "active"):
            raise ValueError("archived nodes cannot gain memberships")
    if relationship_type == "member_of_unit":
        unit = tx.organization_units.get(target_id)
        agent = next((a for a in tx.agents.list(id=source_id)), None)
        if unit.status == "archived" or (agent and agent.status != "active"):
            raise ValueError("archived nodes cannot gain memberships")
    edge = tx.relationships.add(
        GraphRelationship(
            relationship_type=relationship_type,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            primary=primary,
        )
    )
    tx.log(
        "relationship_created",
        relationship_id=edge.id,
        relationship_type=relationship_type,
        source_id=source_id,
        target_id=target_id,
    )
    return edge


def validate_child_agent_boundary(parent_agent: Agent, child_req: AgentProvisioningRequest):
    """Enforces absolute security rule: visual / org hierarchy never grants privileges.

    Child risk ceiling <= parent risk ceiling.
    Child capabilities ⊆ parent capabilities.
    Child external budget <= parent external budget.
    """
    p_risk = RISK_RANK.get(str(parent_agent.risk_ceiling), 1)
    c_risk = RISK_RANK.get(str(child_req.risk_ceiling), 1)
    if c_risk > p_risk:
        raise PermissionError(
            f"child risk ceiling ({child_req.risk_ceiling}) cannot exceed parent risk ceiling ({parent_agent.risk_ceiling})"
        )

    parent_tools = set(parent_agent.capabilities.get("tools", []))
    child_tools = set(child_req.capabilities.get("tools", []))
    if child_tools and not child_tools.issubset(parent_tools):
        excess = child_tools - parent_tools
        raise PermissionError(f"child capabilities expand parent tools: {excess}")

    parent_providers = set(parent_agent.capabilities.get("providers", []))
    child_providers = set(child_req.capabilities.get("providers", []))
    if child_providers and not child_providers.issubset(parent_providers):
        excess = child_providers - parent_providers
        raise PermissionError(f"child providers expand parent providers: {excess}")

    parent_budget = parent_agent.capabilities.get("external_budget", 0)
    if child_req.external_budget > parent_budget:
        raise PermissionError(
            f"child budget ({child_req.external_budget}) exceeds parent budget ({parent_budget})"
        )


def bootstrap_corporate_matrix(store):
    """Seed a small, useful and idempotent corporate graph."""
    with store.transaction() as tx:
        units = {unit.stable_key: unit for unit in tx.organization_units.list(limit=1000)}

        def ensure_unit(key, name, unit_type, parent=None, responsibilities=()):
            if key in units:
                return units[key]
            existing = tx.organization_units.list(stable_key=key, limit=1)
            if existing:
                units[key] = existing[0]
                return existing[0]
            unit = create_org_unit(
                tx,
                name,
                unit_type=unit_type,
                parent_unit_id=parent.id if parent else None,
                stable_key=key,
                metadata={"responsibilities": list(responsibilities)},
            )
            units[key] = unit
            return unit

        group = ensure_unit("hufi-group", "Hufi Group", "GROUP")
        trust = ensure_unit(
            "hufi-group/shared/hufi-trust",
            "HufiTrust",
            "SHARED_SERVICE",
            group,
            ("security", "qa", "redteam", "privacy", "release", "evidence", "compliance"),
        )
        ensure_unit(
            "hufi-group/shared/hufi-sales",
            "HufiSales",
            "SHARED_SERVICE",
            group,
            ("sales", "market", "lead", "conversion", "partnership"),
        )
        ensure_unit(
            "hufi-group/shared/hufi-support",
            "HufiSupport",
            "SHARED_SERVICE",
            group,
            ("support", "customer-success", "onboarding", "documentation", "feedback"),
        )
        business_units = {}
        for key, name in (
            ("hufiagents", "HufiAgents"),
            ("hufmanager", "HufManager"),
            ("hufiapp", "HufiApp"),
            ("equimeteo", "EquiMeteo"),
        ):
            business_units[key] = ensure_unit(
                f"hufi-group/business/{key}", name, "BUSINESS_UNIT", group, (key,)
            )
        ha = business_units["hufiagents"]
        product = ensure_unit(
            "hufi-group/business/hufiagents/product", "Product", "DEPARTMENT", ha, ("product", "qa")
        )
        engineering = ensure_unit(
            "hufi-group/business/hufiagents/engineering",
            "Engineering",
            "DEPARTMENT",
            ha,
            ("engineering", "software", "runtime", "browser"),
        )
        ensure_unit(
            "hufi-group/business/hufiagents/operations",
            "Operations",
            "DEPARTMENT",
            ha,
            ("operations", "release"),
        )
        for key, name, responsibility in (
            ("runtime", "Runtime", "runtime"),
            ("browser", "Browser", "browser"),
            ("agent-intelligence", "Agent Intelligence", "agent-intelligence"),
        ):
            ensure_unit(
                f"{engineering.stable_key}/{key}", name, "TEAM", engineering, (responsibility,)
            )
        qa = ensure_unit(
            f"{product.stable_key}/quality-assurance",
            "Quality Assurance",
            "TEAM",
            product,
            ("qa", "provider-qa", "client-qa", "partner-qa", "cross-role-qa"),
        )

        existing_agents = {a.id: a for a in tx.agents.list(limit=1000)}

        def ensure_agent(agent_id, name, role, roles, parent=None):
            if agent_id in existing_agents:
                return existing_agents[agent_id]
            agent = tx.agents.add(
                Agent(
                    id=agent_id,
                    name=name,
                    role=role,
                    parent_agent_id=parent,
                    capabilities={
                        "tools": [] if agent_id in {"hufiboss", "mr_equi"} else ["files"],
                        "providers": ["fake", "hufi-local-router", "ollama"],
                        "roles": list(roles),
                        "external_budget": 0,
                        "data_scopes": ["hufiagents"],
                    },
                    risk_ceiling=Risk.R0 if agent_id in {"hufiboss", "mr_equi"} else Risk.R1,
                )
            )
            existing_agents[agent_id] = agent
            tx.log("agent_registered", actor=agent_id)
            return agent

        ensure_agent(
            "hufiboss", "HufiBoss", "Owner interface and executive coordinator", ("intake",)
        )
        ensure_agent(
            "mr_equi",
            "Mr. Equi",
            "Portfolio and corporate matrix coordinator",
            ("routing",),
            "hufiboss",
        )
        qa_agents = (
            ("provider_qa", "Provider QA", "Provider experience validator", "provider-qa"),
            ("client_qa", "Client QA", "Client experience validator", "client-qa"),
            ("partner_qa", "Partner QA", "Partner experience validator", "partner-qa"),
            ("cross_role_qa", "Cross-Role QA", "Cross-role scenario validator", "cross-role-qa"),
            ("trust_security", "HufiTrust Sentinel", "Security and evidence reviewer", "security"),
        )
        for agent_id, name, role, capability_role in qa_agents:
            agent = ensure_agent(agent_id, name, role, (capability_role, "qa"), "mr_equi")
            target = trust if agent_id == "trust_security" else qa
            if not tx.relationships.list(
                relationship_type="member_of_unit", source_id=agent.id, target_id=target.id, limit=1
            ):
                add_relationship(tx, "member_of_unit", "agent", agent.id, "unit", target.id)

        builder = existing_agents.get("builder")
        runtime = units["hufi-group/business/hufiagents/engineering/runtime"]
        if builder and not tx.relationships.list(
            relationship_type="member_of_unit", source_id=builder.id, target_id=runtime.id, limit=1
        ):
            add_relationship(tx, "member_of_unit", "agent", builder.id, "unit", runtime.id)

        projects = {project.id: project for project in tx.graph_projects.list(limit=1000)}
        for project_id, name in (
            ("project-hufiagents", "HufiAgents"),
            ("project-hufiapp", "HufiApp"),
        ):
            if project_id not in projects:
                projects[project_id] = tx.graph_projects.add(
                    GraphProject(id=project_id, name=name, description=f"{name} work matrix")
                )
        for agent_id, project_id in (
            ("trust_security", "project-hufiagents"),
            ("trust_security", "project-hufiapp"),
            ("builder", "project-hufiagents"),
        ):
            if agent_id in existing_agents and not tx.relationships.list(
                relationship_type="works_on_project",
                source_id=agent_id,
                target_id=project_id,
                limit=1,
            ):
                add_relationship(tx, "works_on_project", "agent", agent_id, "project", project_id)

        if not tx.relationships.list(
            relationship_type="reports_to", source_id="mr_equi", target_id="hufiboss", limit=1
        ):
            add_relationship(
                tx, "reports_to", "agent", "mr_equi", "agent", "hufiboss", primary=True
            )


def remove_relationship(tx, relationship_id):
    edge = tx.relationships.get(relationship_id)
    edge.removed_at = datetime.now(UTC)
    tx.relationships.save(edge)
    tx.log(
        "relationship_removed", relationship_id=edge.id, relationship_type=edge.relationship_type
    )
    return edge


def register_credential(tx, connector, label, scopes=None):
    """Register a handle only. Callers must store secret material externally."""
    ref = tx.credential_refs.add(
        CredentialRef(connector=connector, label=label, scopes=scopes or [])
    )
    tx.log("credential_registered", credential_id=ref.id, connector=connector, scopes=ref.scopes)
    return ref


def revoke_credential(tx, credential_id):
    ref = tx.credential_refs.get(credential_id)
    ref.status, ref.revoked_at = "revoked", datetime.now(UTC)
    tx.credential_refs.save(ref)
    tx.log("credential_revoked", credential_id=ref.id, connector=ref.connector)
    return ref


def rotate_credential(tx, credential_id):
    ref = tx.credential_refs.get(credential_id)
    if ref.status != "active":
        raise ValueError("cannot rotate revoked credential")
    ref.rotated_at = datetime.now(UTC)
    tx.credential_refs.save(ref)
    tx.log("credential_rotated", credential_id=ref.id, connector=ref.connector)
    return ref


class CostGovernor:
    """Provider-neutral budget gate. Local aliases always carry zero EUR cost."""

    LOCAL = {"hufi-qwen9-fast", "hufi-qwen9", "hufi-gemma", "hufi-local-router", "fake", "ollama"}

    def __init__(self, external_cost_limit=0.0):
        self.external_cost_limit = float(external_cost_limit)
        self.reserved = 0.0

    def estimate(self, provider, input_tokens=0, output_tokens=0, price_per_1k=0.0):
        return (
            0.0 if provider in self.LOCAL else (input_tokens + output_tokens) / 1000 * price_per_1k
        )

    def reserve(self, provider, input_tokens=0, output_tokens=0, price_per_1k=0.0):
        amount = self.estimate(provider, input_tokens, output_tokens, price_per_1k)
        if self.reserved + amount > self.external_cost_limit:
            raise PermissionError("external cost budget exceeded")
        self.reserved += amount
        return amount


def deterministic_check(kind, target):
    """Small no-LLM checks return structured facts, suitable for Work Evidence."""
    if kind == "http_status":
        import urllib.request

        try:
            with urllib.request.urlopen(target, timeout=5) as response:
                return {"healthy": 200 <= response.status < 400, "status": response.status}
        except Exception as exc:
            return {"healthy": False, "error": type(exc).__name__}
    if kind == "disk_usage":
        usage = shutil.disk_usage(target)
        return {"healthy": usage.free > 0, "free_bytes": usage.free, "total_bytes": usage.total}
    if kind == "file_exists":
        return {"healthy": Path(target).exists(), "path": str(target)}
    if kind == "git_clean":
        result = subprocess.run(
            ["git", "-C", target, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {
            "healthy": result.returncode == 0 and not result.stdout.strip(),
            "clean": not result.stdout.strip(),
        }
    raise ValueError("unsupported deterministic check")
