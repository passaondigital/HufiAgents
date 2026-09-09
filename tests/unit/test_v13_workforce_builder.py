"""Unit tests — V1.3 Workforce Builder.

Priority:
  1. Privilege escalation blocked (capability + risk)
  2. Secret rejection
  3. Model policy precedence in router
  4. Golden provisioning
  5. Idempotency
  6. Archive blocks routines
  7. Immutable field protection
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from hufiagents.contracts import Agent, AgentProvisioningRequest, Risk
from hufiagents.providers.router import select_provider
from hufiagents.workforce.builder import WorkforceBuilder, _check_secrets, _stable_id

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _store_with_agent(agent: Agent):
    """Build a minimal mock store that returns `agent` on tx.agents.get()."""
    tx = MagicMock()
    tx.agents.get.return_value = agent
    tx.agents.list.return_value = []
    tx.agents.add.return_value = agent
    tx.agents.save.return_value = agent
    tx.agent_profile_history.list.return_value = []
    tx.agent_profile_history.add.return_value = MagicMock()
    tx.routines.list.return_value = []
    tx.log.return_value = None

    store = MagicMock()
    store.transaction.return_value.__enter__.return_value = tx
    store.transaction.return_value.__exit__.return_value = False
    return store, tx


@dataclass
class FakeHealth:
    available: bool = True


def _make_agent(**kw) -> Agent:
    defaults = dict(
        id="a1",
        role="engineer",
        capabilities={"providers": ["local"]},
        risk_ceiling=Risk.R1,
        default_risk_ceiling=Risk.R1,
    )
    defaults.update(kw)
    return Agent(**defaults)


# ---------------------------------------------------------------------------
# 1. Secret rejection
# ---------------------------------------------------------------------------


class TestSecretRejection:
    def test_rejects_api_key_field(self):
        with pytest.raises(ValueError, match="api_key"):
            _check_secrets({"api_key": "abc123"})

    def test_rejects_token_field(self):
        with pytest.raises(ValueError, match="token"):
            _check_secrets({"credentials": {"token": "secret"}})

    def test_rejects_password_field(self):
        with pytest.raises(ValueError, match="password"):
            _check_secrets({"password": "hunter2"})

    def test_rejects_bearer_pattern_in_value(self):
        with pytest.raises(ValueError, match="secret value"):
            _check_secrets({"auth": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"})

    def test_rejects_sk_key_in_value(self):
        with pytest.raises(ValueError, match="secret value"):
            _check_secrets({"key": "sk-abcdefghijklmnopqrstuvwxyz12345678"})

    def test_allows_credential_ref(self):
        # SecretRef/handle — plain string not matching patterns is allowed.
        _check_secrets({"credential_ref": "cred://vault/my-db-creds"})

    def test_rejects_nested_list_secret(self):
        with pytest.raises(ValueError):
            _check_secrets({"envs": [{"api_key": "bad"}]})


# ---------------------------------------------------------------------------
# 2. Privilege escalation — capabilities
# ---------------------------------------------------------------------------


class TestCapabilityGuard:
    def _builder_provision(self, request, caller_caps, caller_ceiling=Risk.R1):
        store, tx = _store_with_agent(_make_agent())
        builder = WorkforceBuilder(store)
        return builder.provision(
            request, caller_capabilities=caller_caps, caller_risk_ceiling=caller_ceiling
        )

    def test_escalation_blocked_unknown_provider(self):
        req = AgentProvisioningRequest(
            display_name="Hacker",
            role="hacker",
            capabilities={"providers": ["openai-gpt4"]},
        )
        with pytest.raises(PermissionError, match="capabilities"):
            self._builder_provision(req, caller_caps={"providers": ["local"]})

    def test_escalation_blocked_extra_tool(self):
        req = AgentProvisioningRequest(
            display_name="ToolBot",
            role="tool-bot",
            capabilities={"tools": ["browser", "shell", "sudo"]},
        )
        with pytest.raises(PermissionError, match="capabilities"):
            self._builder_provision(req, caller_caps={"tools": ["browser"]})

    def test_subset_capabilities_allowed(self):
        req = AgentProvisioningRequest(
            display_name="ValidBot",
            role="assistant",
            capabilities={"providers": ["local"]},
        )
        # Should not raise
        agent = self._builder_provision(req, caller_caps={"providers": ["local", "hufi-cloud"]})
        assert agent.role == "assistant"

    def test_empty_capabilities_always_allowed(self):
        req = AgentProvisioningRequest(
            display_name="EmptyBot",
            role="observer",
            capabilities={},
        )
        agent = self._builder_provision(req, caller_caps={})
        assert agent.status == "active"


# ---------------------------------------------------------------------------
# 3. Risk ceiling guard
# ---------------------------------------------------------------------------


class TestRiskCeilingGuard:
    def test_risk_escalation_blocked(self):
        store, _ = _store_with_agent(_make_agent())
        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="HighRisk",
            role="admin",
            risk_ceiling=Risk.R3,
        )
        with pytest.raises(PermissionError, match="risk ceiling"):
            builder.provision(req, caller_capabilities={}, caller_risk_ceiling=Risk.R1)

    def test_equal_risk_ceiling_allowed(self):
        store, tx = _store_with_agent(_make_agent())
        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="SameRisk",
            role="worker",
            risk_ceiling=Risk.R1,
        )
        agent = builder.provision(req, caller_capabilities={}, caller_risk_ceiling=Risk.R1)
        assert agent.risk_ceiling == Risk.R1

    def test_lower_risk_ceiling_allowed(self):
        store, tx = _store_with_agent(_make_agent())
        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="LowRisk",
            role="reader",
            risk_ceiling=Risk.R0,
        )
        agent = builder.provision(req, caller_capabilities={}, caller_risk_ceiling=Risk.R2)
        assert agent.risk_ceiling == Risk.R0


# ---------------------------------------------------------------------------
# 4. Model policy precedence in router
# ---------------------------------------------------------------------------


class TestModelPolicyPrecedence:
    def _health(self, *providers):
        return {p: FakeHealth(available=True) for p in providers}

    def test_task_preference_wins_over_agent(self):
        task = MagicMock()
        task.preferred_provider = "cloud-gpt4"
        agent = _make_agent(
            capabilities={"providers": ["cloud-gpt4", "local"]},
            model_preference="local",
        )
        choice = select_provider(task, agent, self._health("cloud-gpt4", "local"))
        assert choice.provider_id == "cloud-gpt4"
        assert "task preference" in choice.reason

    def test_agent_policy_used_when_no_task_override(self):
        task = MagicMock()
        task.preferred_provider = None
        agent = _make_agent(
            capabilities={"providers": ["cloud-gpt4", "local"]},
            model_preference="cloud-gpt4",
        )
        choice = select_provider(task, agent, self._health("cloud-gpt4", "local"))
        assert choice.provider_id == "cloud-gpt4"
        assert "agent model policy" in choice.reason

    def test_default_used_when_no_task_no_agent_policy(self):
        task = MagicMock()
        task.preferred_provider = None
        agent = _make_agent(
            capabilities={"providers": ["hufi-local-router"]},
            model_preference=None,
        )
        choice = select_provider(
            task, agent, self._health("hufi-local-router"), default="hufi-local-router"
        )
        assert choice.provider_id == "hufi-local-router"
        assert "local-first" in choice.reason

    def test_agent_policy_outside_whitelist_raises(self):
        task = MagicMock()
        task.preferred_provider = None
        agent = _make_agent(
            capabilities={"providers": ["local"]},
            model_preference="cloud-gpt4",  # not in whitelist
        )
        with pytest.raises(PermissionError, match="whitelist"):
            select_provider(task, agent, self._health("cloud-gpt4", "local"))

    def test_unavailable_provider_raises(self):
        task = MagicMock()
        task.preferred_provider = None
        agent = _make_agent(
            capabilities={"providers": ["local"]},
            model_preference="local",
        )
        with pytest.raises(ConnectionError, match="unavailable"):
            select_provider(task, agent, {"local": FakeHealth(available=False)})


# ---------------------------------------------------------------------------
# 5. Golden provisioning
# ---------------------------------------------------------------------------


class TestGoldenProvisioning:
    def test_golden_provisioning_creates_agent(self):
        store, tx = _store_with_agent(_make_agent(id="will-be-replaced"))
        tx.agents.list.return_value = []  # No existing agent

        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="Pascal the Planner",
            role="planner",
            description="Plans all missions",
            capabilities={"providers": ["local"], "tools": ["files"]},
            risk_ceiling=Risk.R1,
            model_preference="local",
        )
        agent = builder.provision(
            req, caller_capabilities={"providers": ["local"], "tools": ["files"]}
        )
        assert agent.role == "planner"
        assert agent.name == "Pascal the Planner"
        assert agent.status == "active"
        assert agent.risk_ceiling == Risk.R1
        assert tx.agents.add.called
        assert tx.agent_profile_history.add.called
        assert tx.log.called

    def test_idempotency_key_produces_stable_id(self):
        key = "my-unique-employee-42"
        id1 = _stable_id(key)
        id2 = _stable_id(key)
        assert id1 == id2
        assert id1.startswith("agent-")

    def test_idempotent_reprovision_returns_existing(self):
        existing = _make_agent(id="agent-abc", role="planner")
        store, tx = _store_with_agent(existing)
        tx.agents.list.return_value = [existing]  # already exists

        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="Same Agent",
            role="planner",
            idempotency_key="unique-key",
        )
        agent = builder.provision(req, caller_capabilities={})
        # Should return existing, not try to add again
        assert agent.id == existing.id
        assert not tx.agents.add.called

    def test_idempotent_different_role_raises(self):
        existing = _make_agent(id="agent-abc", role="planner")
        store, tx = _store_with_agent(existing)
        tx.agents.list.return_value = [existing]

        builder = WorkforceBuilder(store)
        req = AgentProvisioningRequest(
            display_name="Conflict",
            role="executor",  # different role
            idempotency_key="unique-key",
        )
        with pytest.raises(ValueError, match="different role"):
            builder.provision(req, caller_capabilities={})


# ---------------------------------------------------------------------------
# 6. Immutable field protection
# ---------------------------------------------------------------------------


class TestImmutableFields:
    def test_update_profile_blocks_id_change(self):
        agent = _make_agent()
        store, tx = _store_with_agent(agent)
        builder = WorkforceBuilder(store)
        with pytest.raises(PermissionError, match="immutable"):
            builder.update_profile(agent.id, {"id": "new-id"})

    def test_update_profile_blocks_capabilities_change(self):
        agent = _make_agent()
        store, tx = _store_with_agent(agent)
        builder = WorkforceBuilder(store)
        with pytest.raises(PermissionError, match="immutable"):
            builder.update_profile(agent.id, {"capabilities": {"sudo": True}})

    def test_update_profile_blocks_risk_ceiling_change(self):
        agent = _make_agent()
        store, tx = _store_with_agent(agent)
        builder = WorkforceBuilder(store)
        with pytest.raises(PermissionError, match="immutable"):
            builder.update_profile(agent.id, {"risk_ceiling": "R3"})

    def test_update_profile_allows_description(self):
        agent = _make_agent()
        store, tx = _store_with_agent(agent)
        tx.agent_profile_history.list.return_value = []
        builder = WorkforceBuilder(store)
        builder.update_profile(agent.id, {"description": "Updated description"})
        assert tx.agents.save.called


# ---------------------------------------------------------------------------
# 7. Archive semantics
# ---------------------------------------------------------------------------


class TestArchiveSemantics:
    def test_archived_agent_cannot_be_updated(self):
        agent = _make_agent(status="archived")
        store, tx = _store_with_agent(agent)
        builder = WorkforceBuilder(store)
        with pytest.raises(PermissionError, match="archived"):
            builder.update_profile(agent.id, {"description": "attempt"})

    def test_archive_is_idempotent(self):
        agent = _make_agent(status="archived")
        store, tx = _store_with_agent(agent)
        builder = WorkforceBuilder(store)
        result = builder.archive_agent(agent.id)
        # Should return existing archived agent without calling save again
        assert result.status == "archived"
        assert not tx.agents.save.called

    def test_archive_sets_status_and_logs(self):
        agent = _make_agent(status="active")
        store, tx = _store_with_agent(agent)
        tx.agent_profile_history.list.return_value = []
        tx.routines.list.return_value = []
        builder = WorkforceBuilder(store)
        result = builder.archive_agent(agent.id, actor="admin")
        assert result.status == "archived"
        assert tx.agents.save.called
        tx.log.assert_called_with("agent_archived", actor="admin", agent_id=agent.id)
