from hufiagents.contracts import Agent


class AgentRegistry:
    def __init__(self, store):
        self.store = store

    def seed(self):
        entries = [
            Agent(
                id="builder",
                role="Bounded workspace builder",
                capabilities={
                    "tools": ["files", "shell", "git"],
                    "providers": ["fake", "hufi-local-router", "ollama"],
                },
            ),
            Agent(
                id="reviewer",
                role="Independent mechanical acceptance reviewer",
                capabilities={"tools": ["files"], "providers": []},
            ),
        ]
        with self.store.transaction() as tx:
            for entry in entries:
                if not tx.agents.list(id=entry.id):
                    tx.agents.add(entry)
                    tx.log("agent_registered", actor=entry.id)

    def get(self, identifier):
        with self.store.transaction() as tx:
            agent = tx.agents.get(identifier)
            if agent.status != "active":
                raise PermissionError("agent disabled")
            return agent
