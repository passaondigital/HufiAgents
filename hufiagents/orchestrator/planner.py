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
    acceptance_criteria: list[dict[str, Any]] = Field(
        default_factory=lambda: [{"type": "nonempty"}, {"type": "file_exists"}]
    )
    allowed_tools: list[str] = Field(default_factory=lambda: ["files"])
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
        allowed = {"nonempty", "file_exists", "contains", "exit_code"}
        if not value or any(item.get("type") not in allowed for item in value):
            raise ValueError("acceptance criteria must use supported mechanical checks")
        return value


class MissionCreate(Contract):
    outcome: str = Field(min_length=1, max_length=16000)
    constraints: dict[str, Any] = Field(default_factory=dict)
    risk_ceiling: Risk = Risk.R1
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
