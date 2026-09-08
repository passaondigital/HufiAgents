from hufiagents.contracts import ReviewResult

# Bounded, high-confidence phrases a model uses when it refuses or reports an
# incident instead of delivering a usable result. Deliberately narrow (real
# refusal language, not everyday words like "kann") to avoid flagging
# legitimate results that merely mention limits or risks in passing. Product
# QA (docs/product/PRODUCT-FLOW-FINDINGS.md, MUSS 2) found a model refusal
# rendered identically to a real success ("Fertig") because "nonempty" text
# is not the same as an accepted deliverable -- this criterion is the
# mechanical, backend-owned fix, not a frontend string check.
_REFUSAL_MARKERS = (
    "kritischer sicherheitsvorfall",
    "wird nicht ausgeführt",
    "lehne diese anfrage ab",
    "kann ich nicht ausführen",
    "kann ich nicht tun",
    "verstößt gegen meine richtlinien",
    "i cannot comply",
    "i will not execute",
    "i refuse to",
    "i cannot assist with this request",
    "as an ai, i cannot",
)


def _looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


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
                elif kind == "not_refusal":
                    ok = not _looks_like_refusal(task.result or "")
                else:
                    ok = False
            except (OSError, ValueError):
                ok = False
            if not ok:
                findings.append(
                    {
                        "severity": "P1" if kind == "not_refusal" else "P2",
                        "summary": f"criterion failed: {kind}",
                        "evidence": criterion,
                    }
                )
        return ReviewResult(
            task_id=task.id, verdict="revise" if findings else "approve", findings=findings
        )
