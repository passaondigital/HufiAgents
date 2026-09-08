import pytest

from hufiagents.contracts import Agent, AgentMessage, Risk
from hufiagents.orchestrator.workforce import Workforce
from hufiagents.persistence.repository import Store


def _agent(identifier, parent=None, *, risk=Risk.R1):
    return Agent(
        id=identifier,
        name=identifier,
        role="test",
        parent_agent_id=parent,
        capabilities={"tools": ["files"], "providers": ["fake"]},
        risk_ceiling=risk,
    )


def test_only_direct_child_can_be_delegated_and_archived_agent_cannot_send():
    store = Store("sqlite:///:memory:")
    workforce = Workforce(store)
    workforce.create_agent(_agent("lead"))
    workforce.create_agent(_agent("child", "lead"), delegator_id="lead")
    workforce.create_agent(_agent("other"))

    with pytest.raises(PermissionError, match="not a child"):
        workforce.delegate_task(parent_agent_id="lead", child_agent_id="other", objective="escape")
    workforce.archive_agent("child")
    with pytest.raises(PermissionError, match="sender is not active"):
        workforce.send_message(
            AgentMessage(from_agent_id="child", to_agent_id="lead", content="resume")
        )


def test_result_cannot_be_spoofed_by_parent_or_sibling():
    store = Store("sqlite:///:memory:")
    workforce = Workforce(store)
    workforce.create_agent(_agent("lead"))
    workforce.create_agent(_agent("child", "lead"), delegator_id="lead")
    workforce.create_agent(_agent("sibling", "lead"), delegator_id="lead")
    delegation = workforce.delegate_task(
        parent_agent_id="lead", child_agent_id="child", objective="read"
    )

    with pytest.raises(PermissionError, match="only delegated child"):
        workforce.receive_agent_result(delegation.id, agent_id="sibling", result="forged")
    with pytest.raises(PermissionError, match="only delegated child"):
        workforce.receive_agent_result(delegation.id, agent_id="lead", result="forged")
