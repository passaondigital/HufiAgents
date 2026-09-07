from hufiagents.contracts import ReviewResult


class Reviewer:
    def review(self, task, workspace, artifact, calls):
        findings = []
        if any(
            call.tool not in task.allowed_tools or call.risk_class > task.risk_ceiling
            for call in calls
        ):
            return ReviewResult(
                task_id=task.id,
                verdict="reject",
                findings=[
                    {"severity": "P1", "summary": "tool scope violation", "evidence": task.id}
                ],
            )
        for criterion in task.acceptance_criteria:
            kind = criterion["type"]
            try:
                if kind == "nonempty":
                    ok = bool((task.result or "").strip())
                elif kind == "file_exists":
                    ok = bool(workspace.read(artifact).strip())
                elif kind == "contains":
                    ok = str(criterion.get("value", "")) in (task.result or "")
                elif kind == "exit_code":
                    results = [call for call in calls if call.exit_code is not None]
                    ok = bool(results) and all(
                        c.exit_code == criterion.get("value", 0) for c in results
                    )
                else:
                    ok = False
            except (OSError, ValueError):
                ok = False
            if not ok:
                findings.append(
                    {
                        "severity": "P2",
                        "summary": f"criterion failed: {kind}",
                        "evidence": criterion,
                    }
                )
        return ReviewResult(
            task_id=task.id, verdict="revise" if findings else "approve", findings=findings
        )
