from hufiagents.contracts import Agent, Risk


class AgentRegistry:
    def __init__(self, store):
        self.store = store

    def seed(self):
        entries = [
            # The three agents below are the ones a task's agent_id actually
            # selects and that execute real tool calls -- see
            # hufiagents/orchestrator/engine.py. Hufi Chief, Project Lead and
            # Security below are registered for visibility (README.md's
            # agent-roles list, docs/ARCHITECTURE.md) but are not yet wired
            # into task assignment; they carry no tool/provider capabilities
            # so the UI never implies they execute work they don't.
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
                risk_ceiling=Risk.R2,
            ),
            Agent(
                id="hufi_chief",
                role="Mission intake, prioritisation, coordination",
                # Coordination may delegate bounded local-model analysis, but
                # never gains a tool capability through that delegation.
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
                role="Sandbox, credential and risk-policy enforcement"
                " (hufiagents/tools/sandbox.py, git_security.py)",
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
                    # Existing V1 installations already have this static
                    # coordinator. Updating its declarative local-provider
                    # list is required before it can safely delegate the
                    # read-only team benchmark; it grants no tool access.
                    chief = existing[0]
                    chief.capabilities["providers"] = entry.capabilities["providers"]
                    chief.risk_ceiling = Risk.R0
                    chief.default_risk_ceiling = Risk.R0
                    tx.agents.save(chief)
                    tx.log("agent_registered_updated", actor=entry.id, agent_id=entry.id)

    def get(self, identifier):
        with self.store.transaction() as tx:
            agent = tx.agents.get(identifier)
            if agent.status != "active":
                raise PermissionError("agent disabled")
            return agent
