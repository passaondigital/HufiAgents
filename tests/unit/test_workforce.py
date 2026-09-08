from hufiagents.contracts import Agent
from hufiagents.orchestrator.workforce import Workforce
from hufiagents.persistence.repository import Store


def agent(identifier, *, capabilities=None, risk_ceiling="R1", parent_agent_id=None):
    return Agent(
        id=identifier,
        name=identifier,
        role="specialist",
        capabilities=capabilities or {"tools": ["files"], "providers": ["fake"]},
        risk_ceiling=risk_ceiling,
        parent_agent_id=parent_agent_id,
    )


def test_spawn_delegation_message_and_fan_in_are_durable():
    store = Store("sqlite:///:memory:")
    workforce = Workforce(store)
    workforce.create_agent(agent("lead", risk_ceiling="R2"))
    workforce.create_agent(agent("security", parent_agent_id="lead"), delegator_id="lead")
    workforce.create_agent(agent("product", parent_agent_id="lead"), delegator_id="lead")

    delegations = workforce.fan_out(
        parent_agent_id="lead",
        child_agent_ids=["security", "product"],
        objective="Assess HufManager sales readiness",
    )
    assert len(delegations) == 2
    received = workforce.receive_messages("security")
    assert received[0].delegation_id == delegations[0].id

    workforce.receive_agent_result(
        delegations[0].id, agent_id="security", result="No critical issue"
    )
    workforce.receive_agent_result(delegations[1].id, agent_id="product", result="UX needs polish")
    summary = workforce.fan_in([item.id for item in delegations])
    assert summary["parent_agent_id"] == "lead"
    assert "security / completed" in summary["report"]
    with store.transaction() as tx:
        assert len(tx.agent_messages.list(limit=20)) == 4
        assert {event.event_type for event in tx.audit.list(limit=50)} >= {
            "agent_created",
            "task_delegated",
            "delegation_result_received",
            "fan_in_completed",
        }


def test_spawn_cannot_expand_delegator_permissions_or_ceiling():
    store = Store("sqlite:///:memory:")
    workforce = Workforce(store)
    workforce.create_agent(agent("lead", risk_ceiling="R1"))
    try:
        workforce.create_agent(
            agent("escape", capabilities={"tools": ["shell"]}, parent_agent_id="lead"),
            delegator_id="lead",
        )
    except PermissionError as exc:
        assert "capabilities" in str(exc)
    else:
        raise AssertionError("capability escalation was accepted")
    try:
        workforce.create_agent(
            agent("risk", risk_ceiling="R2", parent_agent_id="lead"), delegator_id="lead"
        )
    except PermissionError as exc:
        assert "risk ceiling" in str(exc)
    else:
        raise AssertionError("risk escalation was accepted")
