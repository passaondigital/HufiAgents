from pathlib import Path

import yaml

from hufiagents.contracts import Risk


class Policy:
    def __init__(self, path: Path):
        data = yaml.safe_load(path.read_text()) if path.exists() else {}
        self.r2_auto_allow = set((data or {}).get("r2_auto_allow", []))

    def decide(self, risk, task, agent, tool, action):
        if tool not in task.allowed_tools or tool not in agent.capabilities.get("tools", []):
            return "denied"
        # Agent ceiling is an immutable upper bound; human approval cannot escalate an agent.
        if risk > agent.default_risk_ceiling:
            return "denied"
        if risk in {Risk.R3, Risk.R4}:
            return "approval_required"
        if risk > task.risk_ceiling:
            return "denied"
        if risk == Risk.R2 and f"{tool}.{action}" not in self.r2_auto_allow:
            return "reviewer_gate"
        return "auto_allow"
