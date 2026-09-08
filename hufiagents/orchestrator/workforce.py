"""Durable dynamic-agent coordination; no workforce state lives only in memory."""

from collections.abc import Iterable

from hufiagents.contracts import Agent, AgentMessage, Channel, Delegation, now


def _subset(child, parent):
    """Return whether every requested capability is already granted by parent."""
    if isinstance(child, dict):
        return isinstance(parent, dict) and all(
            key in parent and _subset(value, parent[key]) for key, value in child.items()
        )
    if isinstance(child, list):
        return isinstance(parent, list) and set(child).issubset(parent)
    return child == parent


class Workforce:
    def __init__(self, store):
        self.store = store

    def create_agent(self, agent: Agent, *, delegator_id: str | None = None):
        """Create a bounded child. A delegator can never grant new powers."""
        with self.store.transaction() as tx:
            if tx.agents.list(id=agent.id, limit=1):
                raise ValueError("agent id already exists")
            if delegator_id:
                parent = tx.agents.get(delegator_id)
                if parent.status != "active":
                    raise PermissionError("delegator is not active")
                if agent.parent_agent_id not in {None, delegator_id}:
                    raise PermissionError("child parent must be the delegator")
                if not _subset(agent.capabilities, parent.capabilities):
                    raise PermissionError("child capabilities exceed delegator")
                if agent.risk_ceiling > parent.risk_ceiling:
                    raise PermissionError("child risk ceiling exceeds delegator")
                agent.parent_agent_id = delegator_id
                agent.created_by = delegator_id
            elif agent.parent_agent_id:
                raise PermissionError("a parent agent requires a delegator")
            agent.name = agent.name or agent.id
            # Policy still reads this V1-compatible field.
            agent.default_risk_ceiling = agent.risk_ceiling
            tx.agents.add(agent)
            tx.log(
                "agent_created",
                actor=agent.created_by,
                agent_id=agent.id,
                parent_agent_id=agent.parent_agent_id,
                risk_ceiling=agent.risk_ceiling,
                capabilities=agent.capabilities,
            )
            return agent

    def update_agent(self, identifier: str, changes: dict, *, actor: str = "pascal"):
        forbidden = {
            "id",
            "parent_agent_id",
            "capabilities",
            "risk_ceiling",
            "default_risk_ceiling",
        }
        if forbidden & changes.keys():
            raise PermissionError(
                "identity, lineage and permissions are immutable; create a new agent"
            )
        with self.store.transaction() as tx:
            agent = tx.agents.get(identifier)
            if agent.status == "archived":
                raise ValueError("archived agents cannot be updated")
            for key, value in changes.items():
                if key not in Agent.model_fields:
                    raise ValueError(f"unknown agent field: {key}")
                setattr(agent, key, value)
            tx.agents.save(agent)
            tx.log("agent_updated", actor=actor, agent_id=identifier, fields=sorted(changes))
            return agent

    def archive_agent(self, identifier: str, *, actor: str = "pascal"):
        with self.store.transaction() as tx:
            agent = tx.agents.get(identifier)
            if agent.status == "archived":
                return agent
            agent.status, agent.archived_at = "archived", now()
            tx.agents.save(agent)
            tx.log("agent_archived", actor=actor, agent_id=identifier)
            return agent

    def get_agent(self, identifier: str):
        with self.store.transaction() as tx:
            return tx.agents.get(identifier)

    def list_agents(self, **filters):
        with self.store.transaction() as tx:
            return tx.agents.list(**filters)

    def create_channel(self, channel: Channel, *, actor="pascal"):
        if len(set(channel.member_agent_ids)) != len(channel.member_agent_ids):
            raise ValueError("channel members must be unique")
        with self.store.transaction() as tx:
            for agent_id in channel.member_agent_ids:
                tx.agents.get(agent_id)
            tx.channels.add(channel)
            tx.log(
                "channel_created",
                actor=actor,
                channel_id=channel.id,
                members=channel.member_agent_ids,
            )
            return channel

    def send_message(self, message: AgentMessage):
        if bool(message.to_agent_id) == bool(message.channel_id):
            raise ValueError("message requires exactly one recipient: agent or channel")
        with self.store.transaction() as tx:
            sender = tx.agents.get(message.from_agent_id)
            if sender.status != "active":
                raise PermissionError("sender is not active")
            if message.to_agent_id:
                tx.agents.get(message.to_agent_id)
            else:
                channel = tx.channels.get(message.channel_id)
                if channel.status != "active" or sender.id not in channel.member_agent_ids:
                    raise PermissionError("sender is not an active channel member")
            if message.delegation_id:
                tx.delegations.get(message.delegation_id)
            tx.agent_messages.add(message)
            tx.log(
                "agent_message_sent",
                actor=sender.id,
                mission_id=message.mission_id,
                task_id=message.task_id,
                message_id=message.id,
                to_agent_id=message.to_agent_id,
                channel_id=message.channel_id,
                delegation_id=message.delegation_id,
            )
            return message

    def receive_messages(self, agent_id: str, *, status="unread", limit=100):
        with self.store.transaction() as tx:
            tx.agents.get(agent_id)
            messages = tx.agent_messages.list(to_agent_id=agent_id, status=status, limit=limit)
            for message in messages:
                message.status = "handled"
                tx.agent_messages.save(message)
                tx.log("agent_message_handled", actor=agent_id, message_id=message.id)
            return messages

    def delegate_task(
        self, *, parent_agent_id, child_agent_id, objective, mission_id=None, task_id=None
    ):
        with self.store.transaction() as tx:
            parent, child = tx.agents.get(parent_agent_id), tx.agents.get(child_agent_id)
            if parent.status != "active" or child.status != "active":
                raise PermissionError("delegation requires active agents")
            if child.parent_agent_id != parent.id:
                raise PermissionError("delegation target is not a child of delegator")
            delegation = Delegation(
                parent_agent_id=parent.id,
                child_agent_id=child.id,
                objective=objective,
                mission_id=mission_id,
                task_id=task_id,
            )
            tx.delegations.add(delegation)
            tx.log(
                "task_delegated",
                actor=parent.id,
                mission_id=mission_id,
                task_id=task_id,
                delegation_id=delegation.id,
                child_agent_id=child.id,
                correlation_id=delegation.correlation_id,
            )
        return (
            self.send_message(
                AgentMessage(
                    from_agent_id=parent_agent_id,
                    to_agent_id=child_agent_id,
                    mission_id=mission_id,
                    task_id=task_id,
                    content=objective,
                    correlation_id=delegation.correlation_id,
                    delegation_id=delegation.id,
                )
            )
            and delegation
        )

    def receive_agent_result(self, delegation_id: str, *, agent_id: str, result: str, failed=False):
        with self.store.transaction() as tx:
            delegation = tx.delegations.get(delegation_id)
            if delegation.child_agent_id != agent_id:
                raise PermissionError("only delegated child can return this result")
            if delegation.status in {"completed", "failed", "cancelled"}:
                raise ValueError("delegation is already terminal")
            delegation.status = "failed" if failed else "completed"
            delegation.result, delegation.completed_at = result, now()
            tx.delegations.save(delegation)
            tx.log(
                "delegation_result_received",
                actor=agent_id,
                mission_id=delegation.mission_id,
                task_id=delegation.task_id,
                delegation_id=delegation.id,
                status=delegation.status,
            )
        self.send_message(
            AgentMessage(
                from_agent_id=agent_id,
                to_agent_id=delegation.parent_agent_id,
                mission_id=delegation.mission_id,
                task_id=delegation.task_id,
                content=result,
                correlation_id=delegation.correlation_id,
                delegation_id=delegation.id,
            )
        )
        return delegation

    def fan_out(
        self,
        *,
        parent_agent_id: str,
        child_agent_ids: Iterable[str],
        objective: str,
        mission_id=None,
    ):
        return [
            self.delegate_task(
                parent_agent_id=parent_agent_id,
                child_agent_id=child_id,
                objective=objective,
                mission_id=mission_id,
            )
            for child_id in child_agent_ids
        ]

    def fan_in(self, delegation_ids: Iterable[str]):
        ids = list(delegation_ids)
        if not ids:
            raise ValueError("fan-in requires delegations")
        with self.store.transaction() as tx:
            delegations = [tx.delegations.get(identifier) for identifier in ids]
            parents = {item.parent_agent_id for item in delegations}
            if len(parents) != 1:
                raise ValueError("fan-in delegations must share one parent")
            if any(item.status not in {"completed", "failed", "cancelled"} for item in delegations):
                raise ValueError("fan-in waits for terminal child delegations")
            report = "\n\n".join(
                f"[{item.child_agent_id} / {item.status}]\n{item.result or ''}"
                for item in delegations
            )
            tx.log(
                "fan_in_completed",
                actor=next(iter(parents)),
                delegation_ids=ids,
                completed=sum(item.status == "completed" for item in delegations),
            )
            return {
                "parent_agent_id": next(iter(parents)),
                "report": report,
                "delegations": delegations,
            }
