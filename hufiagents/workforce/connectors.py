"""WF-7 connector registry and least-privilege agent grants."""

from hufiagents.contracts import AgentConnectorAccess, ConnectorRegistration, Risk, now


def _risk_at_most(requested: Risk, ceiling: Risk) -> bool:
    return int(requested[1:]) <= int(ceiling[1:])


class ConnectorRegistry:
    def __init__(self, store):
        self.store = store

    def register(self, connector: ConnectorRegistration) -> ConnectorRegistration:
        if any(value not in {risk.value for risk in Risk} for value in connector.risk_mapping.values()):
            raise ValueError("connector risk mapping contains an unknown risk")
        with self.store.transaction() as tx:
            tx.connectors.add(connector)
            tx.log("connector_registered", connector_id=connector.id, connector=connector.name)
        return connector

    def register_github(self, *, configured: bool, healthy: bool) -> ConnectorRegistration:
        """GitHub's V1 write capability remains draft-PR only (R2)."""
        return self.register(ConnectorRegistration(
            name="github", version="v1", capabilities=["repo.read", "pull_request.draft.create"],
            modes=["read", "write"], auth_state="configured" if configured else "unconfigured",
            permissions=["configured_repository_only", "draft_pr_only"],
            risk_mapping={"repo.read": "R1", "pull_request.draft.create": "R2"},
            health="healthy" if healthy else "unknown", enabled=configured,
        ))

    def grant(self, access: AgentConnectorAccess) -> AgentConnectorAccess:
        with self.store.transaction() as tx:
            agent, connector = tx.agents.get(access.agent_id), tx.connectors.get(access.connector_id)
            if not connector.enabled or connector.auth_state != "configured":
                raise PermissionError("connector is not configured and enabled")
            if not set(access.capabilities).issubset(connector.capabilities):
                raise PermissionError("agent connector capability exceeds registration")
            if not set(access.modes).issubset(connector.modes):
                raise PermissionError("agent connector mode exceeds registration")
            if not _risk_at_most(access.risk_ceiling, agent.risk_ceiling):
                raise PermissionError("connector grant exceeds agent risk ceiling")
            for capability in access.capabilities:
                mapped = Risk(connector.risk_mapping.get(capability, "R4"))
                if not _risk_at_most(mapped, access.risk_ceiling):
                    raise PermissionError("connector capability exceeds grant risk ceiling")
            tx.agent_connector_access.add(access)
            tx.log("connector_access_granted", actor=agent.id, connector_id=connector.id,
                   access_id=access.id, capabilities=access.capabilities)
        return access

    def revoke(self, access_id: str) -> AgentConnectorAccess:
        with self.store.transaction() as tx:
            access = tx.agent_connector_access.get(access_id)
            access.status, access.updated_at = "revoked", now()
            tx.agent_connector_access.save(access)
            tx.log("connector_access_revoked", actor=access.agent_id, connector_id=access.connector_id,
                   access_id=access.id)
            return access
