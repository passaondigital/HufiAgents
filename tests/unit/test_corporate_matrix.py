"""Unit coverage for the V1.4A corporate matrix and security boundaries."""

import pytest

from hufiagents.contracts import (
    Agent,
    AgentProvisioningRequest,
    Mission,
    OwnerOutcomeContract,
    Risk,
    ScopedMemory,
    State,
    Task,
    WorkArtifact,
)
from hufiagents.corporate_router import CorporateRouter
from hufiagents.org_graph import (
    add_relationship,
    archive_org_unit,
    bootstrap_corporate_matrix,
    create_org_unit,
    org_unit_descendants,
    update_org_unit_parent,
    validate_child_agent_boundary,
)
from hufiagents.persistence.repository import Store


@pytest.fixture()
def store(tmp_path):
    value = Store(f"sqlite:///{tmp_path}/matrix.sqlite3")
    yield value
    value.close()


def test_recursive_units_duplicate_names_and_cycle_prevention(store):
    with store.transaction() as tx:
        group = create_org_unit(tx, "Test Group", unit_type="GROUP", stable_key="test")
        first = create_org_unit(tx, "First", parent_unit_id=group.id, stable_key="first")
        second = create_org_unit(tx, "Second", parent_unit_id=group.id, stable_key="second")
        eng_a = create_org_unit(tx, "Engineering", parent_unit_id=first.id)
        eng_b = create_org_unit(tx, "Engineering", parent_unit_id=second.id)
        assert eng_a.stable_key != eng_b.stable_key
        with pytest.raises(ValueError, match="stable key already exists"):
            create_org_unit(tx, "Duplicate", parent_unit_id=first.id, stable_key="engineering")
        with pytest.raises(ValueError, match="unit hierarchy cycle"):
            update_org_unit_parent(tx, group.id, eng_a.id)


def test_traversal_is_cycle_safe_for_corrupt_rows(store):
    with store.transaction() as tx:
        root = create_org_unit(tx, "Root", stable_key="root")
        child = create_org_unit(tx, "Child", parent_unit_id=root.id)
        # Simulate corruption below the service boundary; traversal must terminate.
        root.parent_unit_id = child.id
        tx.organization_units.save(root)
        assert [item.id for item in org_unit_descendants(tx, root.id)] == [child.id]


def test_org_unit_archiving(store):
    with store.transaction() as tx:
        unit = create_org_unit(tx, "Temp Team", unit_type="TEAM")
        archived = archive_org_unit(tx, unit.id)
        assert archived.status == "archived"
        assert archived.archived_at is not None


def test_matrix_membership_is_independent_of_reporting(store):
    with store.transaction() as tx:
        trust = create_org_unit(tx, "Trust", unit_type="SHARED_SERVICE")
        project_unit = create_org_unit(tx, "Product", unit_type="BUSINESS_UNIT")
        tx.agents.add(Agent(id="sentinel", role="Sentinel", capabilities={"tools": []}))
        tx.agents.add(Agent(id="lead", role="Lead", capabilities={"tools": []}))
        add_relationship(tx, "reports_to", "agent", "sentinel", "agent", "lead", primary=True)
        add_relationship(tx, "member_of_unit", "agent", "sentinel", "unit", trust.id)
        add_relationship(tx, "member_of_unit", "agent", "sentinel", "unit", project_unit.id)
        memberships = tx.relationships.list(
            relationship_type="member_of_unit", source_id="sentinel"
        )
        assert {item.target_id for item in memberships} == {trust.id, project_unit.id}


def test_child_agent_boundaries(store):
    parent = Agent(
        id="parent",
        role="Parent",
        capabilities={"tools": ["files"], "providers": ["fake"], "external_budget": 0},
        risk_ceiling=Risk.R1,
    )
    invalid = (
        AgentProvisioningRequest(display_name="Risk", role="Worker", risk_ceiling=Risk.R2),
        AgentProvisioningRequest(
            display_name="Tool",
            role="Worker",
            capabilities={"tools": ["shell"]},
            risk_ceiling=Risk.R1,
        ),
        AgentProvisioningRequest(
            display_name="Provider",
            role="Worker",
            capabilities={"providers": ["paid"]},
            risk_ceiling=Risk.R1,
        ),
        AgentProvisioningRequest(
            display_name="Budget", role="Worker", external_budget=1, risk_ceiling=Risk.R1
        ),
    )
    for request in invalid:
        with pytest.raises(PermissionError):
            validate_child_agent_boundary(parent, request)
    validate_child_agent_boundary(
        parent,
        AgentProvisioningRequest(
            display_name="Valid",
            role="Worker",
            capabilities={"tools": ["files"], "providers": ["fake"]},
            risk_ceiling=Risk.R1,
        ),
    )


def test_bootstrap_is_idempotent_and_uses_stable_paths(store):
    bootstrap_corporate_matrix(store)
    bootstrap_corporate_matrix(store)
    with store.transaction() as tx:
        units = tx.organization_units.list(limit=1000)
        keys = [unit.stable_key for unit in units]
        assert len(keys) == len(set(keys))
        assert "hufi-group/business/hufiagents/engineering/runtime" in keys
        assert tx.agents.get("hufiboss").risk_ceiling == Risk.R0
        assert tx.agents.get("mr_equi").parent_agent_id == "hufiboss"


def test_security_route_uses_persisted_capability_not_membership_alone(store):
    bootstrap_corporate_matrix(store)
    with store.transaction() as tx:
        trust = next(
            unit for unit in tx.organization_units.list(limit=1000) if unit.name == "HufiTrust"
        )
        tx.agents.add(
            Agent(
                id="trust_decoy",
                role="No security capability",
                capabilities={"providers": ["fake"], "roles": ["sales"]},
            )
        )
        add_relationship(tx, "member_of_unit", "agent", "trust_decoy", "unit", trust.id)
    route = CorporateRouter.resolve_route("Prüfe HufiAgents auf Sicherheitsprobleme", store)
    assert route["target_unit"] == "HufiTrust"
    assert route["assigned_agent_id"] == "trust_security"
    assert route["reason"].startswith("persisted responsibilities")


def test_owner_input_artifact_cannot_complete_outcome(store):
    mission = Mission(outcome="Create provider report")
    task = Task(
        mission_id=mission.id,
        objective="Provider QA",
        assigned_agent_id="provider_qa",
        workstream_key="provider_qa",
        deliverable_key="provider_report",
        status=State.completed,
    )
    contract = OwnerOutcomeContract(
        mission_id=mission.id,
        required_roles=["provider_qa"],
        required_workstreams=["provider_qa"],
        required_deliverables=["provider_report"],
        required_reviews=["independent_review"],
        required_evidence=["task_evidence"],
    )
    with store.transaction() as tx:
        tx.missions.add(mission)
        tx.tasks.add(task)
        tx.owner_outcome_contracts.add(contract)
        tx.work_artifacts.add(
            WorkArtifact(
                mission_id=mission.id,
                deliverable_key="provider_report",
                name="Provider Report",
                origin="OWNER_INPUT",
            )
        )
        tx.refresh_mission(mission.id)
        assert tx.missions.get(mission.id).status == State.blocked
        assert tx.owner_outcome_contracts.get(contract.id).status == "PARTIAL"


def test_shared_service_agent_has_cross_project_work_without_duplicate_identity(store):
    bootstrap_corporate_matrix(store)
    with store.transaction() as tx:
        agents = tx.agents.list(id="trust_security")
        projects = tx.relationships.list(
            relationship_type="works_on_project", source_id="trust_security"
        )
        assert len(agents) == 1
        assert {item.target_id for item in projects} == {
            "project-hufiagents",
            "project-hufiapp",
        }
        tx.scoped_memories.add(
            ScopedMemory(
                scope_type="project",
                scope_id="project-hufiagents",
                summary="A",
                content="HufiAgents only",
            )
        )
        tx.scoped_memories.add(
            ScopedMemory(
                scope_type="project",
                scope_id="project-hufiapp",
                summary="B",
                content="HufiApp only",
            )
        )
        assert len(tx.scoped_memories.list(scope_id="project-hufiagents")) == 1
        assert len(tx.scoped_memories.list(scope_id="project-hufiapp")) == 1


def test_missing_deliverable_review_or_evidence_prevents_completion(store):
    mission = Mission(outcome="Missing review test")
    task = Task(
        mission_id=mission.id,
        objective="QA Task",
        assigned_agent_id="qa_agent",
        workstream_key="qa",
        deliverable_key="qa_report",
        status=State.completed,
    )
    contract = OwnerOutcomeContract(
        mission_id=mission.id,
        required_roles=["qa_agent"],
        required_workstreams=["qa"],
        required_deliverables=["qa_report"],
        required_reviews=["independent_review"],
        required_evidence=["task_evidence"],
    )
    with store.transaction() as tx:
        tx.missions.add(mission)
        tx.tasks.add(task)
        tx.owner_outcome_contracts.add(contract)
        # Add generated artifact, but NO review or evidence
        tx.work_artifacts.add(
            WorkArtifact(
                mission_id=mission.id,
                task_id=task.id,
                deliverable_key="qa_report",
                name="QA Report",
                origin="AGENT_GENERATED",
            )
        )
        tx.refresh_mission(mission.id)
        # Independent review missing -> should be blocked / PARTIAL
        assert tx.missions.get(mission.id).status == State.blocked
        assert tx.owner_outcome_contracts.get(contract.id).status == "PARTIAL"


def test_project_request_with_no_eligible_agent_fails_closed(store):
    bootstrap_corporate_matrix(store)
    with pytest.raises(PermissionError, match="no eligible agent"):
        CorporateRouter.resolve_route("Bearbeite streng geheimes Projekt EquiMeteo", store)


def test_company_pulse_and_unread_events(store):
    from hufiagents.contracts import AuditEvent, Mission, WorkforceEvent, now
    from hufiagents.evidence import get_company_pulse, get_company_workforce

    bootstrap_corporate_matrix(store)
    with store.transaction() as tx:
        m = Mission(outcome="Test mission")
        tx.missions.add(m)
        event = WorkforceEvent(
            mission_id=m.id,
            agent_id="hufiboss",
            unit_id=None,
            event_type="TASK_STARTED",
            safe_summary="Task started",
        )
        tx.workforce_events.add(event)
        tx.audit.append(
            AuditEvent(
                event_type="model_call",
                detail={"provider": "paid-openai", "cost": "0.15"},
            )
        )
        tx.audit.append(
            AuditEvent(
                event_type="model_call",
                detail={"provider": "fake", "cost": 0},
            )
        )
        pulse = get_company_pulse(tx)
        assert pulse["paid_model_calls"] == 1
        assert pulse["external_model_cost"] == 0.15

        workforce = get_company_workforce(tx)
        boss = next(w for w in workforce["workers"] if w["agent_id"] == "hufiboss")
        assert boss["unread_event_count"] == 1

        # Mark read
        evt = tx.workforce_events.get(event.id)
        evt.read_at = now()
        tx.workforce_events.save(evt)
        workforce_after = get_company_workforce(tx)
        boss_after = next(w for w in workforce_after["workers"] if w["agent_id"] == "hufiboss")
        assert boss_after["unread_event_count"] == 0
