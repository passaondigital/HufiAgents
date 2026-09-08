"""Planner defaults for a plain chat-created mission (no explicit `steps`),
tightened per docs/product/PRODUCT-FLOW-FINDINGS.md MUSS 3: the mission-level
risk_ceiling and the default task's allowed_tools must not be a tighter
artificial cap than what the shipped default agent ("builder") already
declares -- see hufiagents/orchestrator/registry.py.
"""

from hufiagents.contracts import Risk
from hufiagents.orchestrator.planner import MissionCreate, Planner


def test_default_mission_risk_ceiling_is_r2_not_r1():
    request = MissionCreate(outcome="Analysiere HufManager.")
    assert request.risk_ceiling == Risk.R2


def test_explicit_risk_ceiling_still_overrides_default():
    request = MissionCreate(outcome="Nur lesen.", risk_ceiling=Risk.R0)
    assert request.risk_ceiling == Risk.R0


def test_default_single_task_gets_builder_capable_tools_and_refusal_check():
    request = MissionCreate(outcome="Analysiere HufManager.")
    mission, tasks = Planner().plan(request)
    assert len(tasks) == 1
    task, operations = tasks[0]
    assert operations == []
    assert set(task.allowed_tools) == {"files", "shell", "git"}
    criterion_types = {c["type"] for c in task.acceptance_criteria}
    assert {"nonempty", "file_exists", "not_refusal"} <= criterion_types
    assert task.risk_ceiling == Risk.R2
    assert mission.risk_ceiling == Risk.R2


def test_explicit_steps_are_not_overridden():
    from hufiagents.orchestrator.planner import TaskSpec

    request = MissionCreate(
        outcome="custom",
        risk_ceiling=Risk.R1,
        steps=[TaskSpec(objective="custom step", allowed_tools=["files"])],
    )
    _, tasks = Planner().plan(request)
    task, _ = tasks[0]
    assert task.allowed_tools == ["files"]
    assert task.risk_ceiling == Risk.R1
