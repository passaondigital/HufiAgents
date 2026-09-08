# ruff: noqa: E501
import pytest

from hufiagents.contracts import Agent
from hufiagents.org_graph import (
    CostGovernor,
    add_relationship,
    archive_team,
    create_team,
    deterministic_check,
    register_credential,
)
from hufiagents.persistence.repository import Store


def store(tmp_path):
    return Store(f"sqlite:///{tmp_path}/state.sqlite3")


def test_graph_membership_and_reporting_cycle_rejected(tmp_path):
    db = store(tmp_path)
    with db.transaction() as tx:
        tx.agents.add(Agent(id="a", role="worker", capabilities={}))
        tx.agents.add(Agent(id="b", role="worker", capabilities={}))
        team = create_team(tx, "Sales")
        add_relationship(tx, "member_of_team", "agent", "a", "team", team.id)
        add_relationship(tx, "reports_to", "agent", "a", "agent", "b", primary=True)
        with pytest.raises(ValueError, match="cycle"):
            add_relationship(tx, "reports_to", "agent", "b", "agent", "a", primary=True)
    with db.transaction() as tx:
        archive_team(tx, team.id)
        assert tx.agents.get("a").id == "a"


def test_credential_is_handle_only_and_cost_local_is_free(tmp_path):
    db = store(tmp_path)
    with db.transaction() as tx:
        ref = register_credential(tx, "github", "deploy", ["repo:read"])
        assert not hasattr(ref, "value")
        assert (
            "credential_registered"
            == tx.audit.list(event_type="credential_registered")[0].event_type
        )
    governor = CostGovernor(0)
    assert governor.reserve("hufi-qwen9-fast", 10000, 10000, 1) == 0
    with pytest.raises(PermissionError):
        governor.reserve("external", 1, 1, 1)


def test_healthy_file_check_is_deterministic(tmp_path):
    result = deterministic_check("file_exists", tmp_path)
    assert result["healthy"] is True
