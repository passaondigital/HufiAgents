from hufiagents.contracts import Agent, Risk


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
            # R2 ceiling, opt-in per task (Planner/TaskSpec.agent_id). `builder`
            # keeps its existing R1 ceiling unchanged -- this is an additive
            # capability, not an expansion of the shipped default agent.
            Agent(
                id="integrator",
                role="Bounded git push / draft-PR workflow",
                capabilities={
                    "tools": ["files", "shell", "git", "github"],
                    "providers": ["fake", "hufi-local-router", "ollama"],
                },
                default_risk_ceiling=Risk.R2,
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
