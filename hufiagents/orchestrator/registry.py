from hufiagents.contracts import Agent, Risk
from hufiagents.org_graph import bootstrap_corporate_matrix


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
            Agent(
                id="integrator",
                role="Bounded git push / draft-PR workflow",
                capabilities={
                    "tools": ["files", "shell", "git", "github"],
                    "providers": ["fake", "hufi-local-router", "ollama"],
                },
                default_risk_ceiling=Risk.R2,
                risk_ceiling=Risk.R2,
            ),
            Agent(
                id="hufi_chief",
                role="Mission intake, prioritisation, coordination",
                capabilities={"tools": [], "providers": ["fake", "hufi-local-router", "ollama"]},
                risk_ceiling=Risk.R0,
            ),
            Agent(
                id="project_lead",
                role="Per-project coordination across HufiAgents/HufManager",
                capabilities={"tools": [], "providers": []},
            ),
            Agent(
                id="security",
                role="Sandbox, credential and risk-policy enforcement",
                capabilities={"tools": [], "providers": []},
            ),
        ]
        with self.store.transaction() as tx:
            for entry in entries:
                existing = tx.agents.list(id=entry.id)
                if not existing:
                    tx.agents.add(entry)
                    tx.log("agent_registered", actor=entry.id)
                elif entry.id == "hufi_chief":
                    chief = existing[0]
                    chief.capabilities["providers"] = entry.capabilities["providers"]
                    chief.risk_ceiling = Risk.R0
                    chief.default_risk_ceiling = Risk.R0
                    tx.agents.save(chief)
                    tx.log("agent_registered_updated", actor=entry.id, agent_id=entry.id)

        # Bootstrap the bounded Corporate Matrix after the legacy registry.
        bootstrap_corporate_matrix(self.store)

    def get(self, identifier):
        with self.store.transaction() as tx:
            agent = tx.agents.get(identifier)
            if agent.status != "active":
                raise PermissionError("agent disabled")
            return agent
