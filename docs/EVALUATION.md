# HufiAgents Evaluation Framework

HufiAgents is judged by measurable outcomes, not by how impressive the agent UI looks.

## Core metrics

- Mission success rate
- Task completion rate
- Pascal interventions per mission
- Recovery rate after failure/restart
- Reviewer catch rate
- Regression rate
- Median mission duration
- p95 mission duration
- Local-model share
- External-model cost
- Policy/security violations
- Repeatability of the same task

## Golden task categories

Create 10–20 repeatable tasks covering:

1. Repository inspection
2. Small code change
3. Bug reproduction and fix
4. Test creation
5. Documentation update
6. Dependency/security review
7. Git branch + commit + PR preparation
8. Failure/retry handling
9. Approval-gated action simulation
10. Multi-agent handoff
11. Local-model routing
12. Remote-model fallback
13. Browser task later
14. SSH/infrastructure task later
15. Real HufManager task once the MVP is ready

## Acceptance thresholds for early MVP

The first MVP is acceptable when:

- the deterministic end-to-end golden task passes reliably,
- mission/task history survives restart,
- a reviewer can reject bad output and trigger correction,
- failed tools do not leave the mission permanently stuck,
- risk policy blocks simulated R3/R4 actions,
- no paid API is required to run CI/evaluation.

## Grok Bot comparison later

Use the same or equivalent real-world missions where possible and compare:

- completion quality,
- time,
- human intervention,
- recovery,
- cost,
- auditability,
- security controls.

Do not chase cosmetic 1:1 parity. Close the highest-value functional gaps first.
