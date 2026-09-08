"""Bounded deterministic decomposition; providers implement deliverables, not policy."""

from typing import Any

from pydantic import Field, field_validator

from hufiagents.contracts import Contract, Mission, Risk, Task


class Operation(Contract):
    tool: str
    action: str
    target: str = "workspace"
    params: dict[str, Any] = Field(default_factory=dict)


class TaskSpec(Contract):
    objective: str = Field(min_length=1, max_length=8000)
    expected_output: str = "result.md"
    # `not_refusal` is a default (not opt-in) mechanical check: a model
    # refusal/incident report is non-empty text and would otherwise pass
    # "nonempty" and read to the user as a real success (docs/product/
    # PRODUCT-FLOW-FINDINGS.md, MUSS 2). See reviewer.py's Reviewer.review().
    acceptance_criteria: list[dict[str, Any]] = Field(
        default_factory=lambda: [
            {"type": "nonempty"},
            {"type": "file_exists"},
            {"type": "not_refusal"},
        ]
    )
    # Matches the shipped default agent's ("builder") own declared
    # capabilities (hufiagents/orchestrator/registry.py) -- a plain chat
    # mission with no explicit steps could not actually use the shell/git
    # tools builder is allowed to use, because this allowlist stayed
    # narrower than the agent's own capabilities. Raising the risk_class of
    # any individual tool call is still gated by Reviewer/Risk-Engine per
    # docs/ARCHITECTURE.md Sec8 -- this only stops the task-level allowlist
    # from being a *tighter* artificial ceiling than the agent already has.
    allowed_tools: list[str] = Field(default_factory=lambda: ["files", "shell", "git"])
    agent_id: str | None = None
    project_id: str | None = None
    dry_run: bool = False
    preferred_provider: str | None = None
    retry_limit: int = Field(2, ge=0, le=5)
    budget_seconds: int = Field(300, ge=1, le=3600)
    budget_tokens: int = Field(512, ge=1, le=8192)
    operations: list[Operation] = Field(default_factory=list, max_length=10)

    @field_validator("acceptance_criteria")
    @classmethod
    def known_criteria(cls, value):
        allowed = {"nonempty", "file_exists", "contains", "exit_code", "not_refusal"}
        if not value or any(item.get("type") not in allowed for item in value):
            raise ValueError("acceptance criteria must use supported mechanical checks")
        return value


class MissionCreate(Contract):
    outcome: str = Field(min_length=1, max_length=16000)
    constraints: dict[str, Any] = Field(default_factory=dict)
    # R1 previously meant a mission's *ceiling* could never even reach R2/R3,
    # regardless of what an assigned agent or the workforce/delegation layer
    # was otherwise allowed to do -- product QA found this made the chat UI's
    # own hardcoded "R1" a redundant second lock on top of this default, and
    # collapsing both effectively made R2/R3 policy-gated/approval actions
    # unreachable from a normal chat message (docs/product/
    # PRODUCT-FLOW-FINDINGS.md, MUSS 3). R2 is still safe as a *default*: R2
    # tool calls remain policy-gated (config/risk_policy.yaml) and are denied
    # outright for any agent below R2 (the shipped "builder" agent stays R1
    # effective, per registry.py) -- this only stops the mission-level
    # ceiling from being a tighter artificial cap than the actual policy
    # layer already enforces. R3/R4 still always require Pascal approval
    # regardless of this default (docs/ARCHITECTURE.md Sec8).
    risk_ceiling: Risk = Risk.R2
    steps: list[TaskSpec] = Field(default_factory=list, max_length=20)


class Planner:
    def plan(self, request: MissionCreate):
        mission = Mission(
            outcome=request.outcome,
            constraints=request.constraints,
            risk_ceiling=request.risk_ceiling,
        )
        specs = request.steps or [TaskSpec(objective=request.outcome)]
        tasks = []
        for spec in specs:
            task = Task(
                mission_id=mission.id,
                risk_ceiling=request.risk_ceiling,
                assigned_agent_id=spec.agent_id,
                **spec.model_dump(exclude={"operations", "agent_id"}),
            )
            if tasks:
                task.dependencies = [tasks[-1][0].id]
            tasks.append((task, spec.operations))
        return mission, tasks
