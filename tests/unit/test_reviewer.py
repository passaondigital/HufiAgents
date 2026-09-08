"""Reviewer mechanical acceptance checks, including the `not_refusal`
criterion added for docs/product/PRODUCT-FLOW-FINDINGS.md MUSS 2: a model
refusal is non-empty text and must not mechanically pass as a real result.
"""

import tempfile
from pathlib import Path

from hufiagents.contracts import Risk, Task
from hufiagents.orchestrator.reviewer import Reviewer
from hufiagents.tools.workspace import Workspace


def make_task(result, acceptance_criteria=None, allowed_tools=None):
    return Task(
        mission_id="m1",
        objective="do it",
        result=result,
        acceptance_criteria=acceptance_criteria
        or [{"type": "nonempty"}, {"type": "file_exists"}, {"type": "not_refusal"}],
        allowed_tools=allowed_tools or ["files"],
        risk_ceiling=Risk.R1,
    )


def make_workspace_with_artifact(artifact, content):
    tmp = Path(tempfile.mkdtemp())
    workspace = Workspace(tmp)
    workspace.create(artifact, content)
    return workspace


def test_normal_result_is_approved():
    task = make_task("Hier ist der fertige Statusbericht: alles im grünen Bereich.")
    workspace = make_workspace_with_artifact("a.md", task.result)
    review = Reviewer().review(task, workspace, "a.md", [])
    assert review.verdict == "approve"
    assert review.findings == []


def test_refusal_in_german_is_not_approved():
    task = make_task("🚨 KRITISCHER SICHERHEITSVORFALL: Diese Aktion wird nicht ausgeführt.")
    workspace = make_workspace_with_artifact("a.md", task.result)
    review = Reviewer().review(task, workspace, "a.md", [])
    assert review.verdict != "approve"
    assert any(f["evidence"].get("type") == "not_refusal" for f in review.findings)


def test_refusal_in_english_is_not_approved():
    task = make_task("I cannot assist with this request as it is unsafe.")
    workspace = make_workspace_with_artifact("a.md", task.result)
    review = Reviewer().review(task, workspace, "a.md", [])
    assert review.verdict != "approve"


def test_legitimate_result_mentioning_limits_still_passes():
    # Guards against the refusal check being too broad: everyday words like
    # "kann" must not trip it just because they co-occur with unrelated text.
    task = make_task(
        "Der Report zeigt: das Deployment kann jederzeit ausgerollt werden, alle Tests sind grün."
    )
    workspace = make_workspace_with_artifact("a.md", task.result)
    review = Reviewer().review(task, workspace, "a.md", [])
    assert review.verdict == "approve"


def test_empty_result_still_fails_nonempty_not_refusal():
    task = make_task("")
    workspace = make_workspace_with_artifact("a.md", "")
    review = Reviewer().review(task, workspace, "a.md", [])
    assert review.verdict != "approve"
    kinds = {f["evidence"].get("type") for f in review.findings}
    assert "nonempty" in kinds
