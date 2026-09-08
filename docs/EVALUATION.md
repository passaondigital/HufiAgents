# HufiAgents Evaluation Framework

**Updated:** 2026-09-08  
**Current baseline:** production `v1.1.2`; V1.2 adds learning, Visible Work and Digital Company capabilities.

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
- Human coordination steps per completed mission
- Rework/retry count
- Useful result per instruction (1:99 direction)

## V1.2 efficiency metrics

For repeated workflows, compare first run vs. later run:

- model calls,
- estimated input/output tokens,
- context size,
- latency/runtime,
- number of human interventions,
- number of retries,
- skill reuse,
- memory reuse,
- external cost.

The V1.2 learning layer is successful only if a repeated known workflow can be completed with less unnecessary context/model work or less human coordination without reducing quality.

## Visible Work truthfulness metrics

Visible Work is evaluated separately from raw Audit.

Required checks:

- every displayed evidence item maps to a real event/tool result/artifact,
- no invented progress step,
- no invented screenshot,
- no invented live-computer state,
- no false success,
- evidence timestamps/agent/project attribution are correct,
- redaction removes secrets/sensitive values without making normal evidence unusable,
- normal-user wording remains understandable without technical knowledge.

A UI that looks active while no real work event exists fails the truthfulness gate.

## Secret/redaction adversarial tasks

At minimum test controlled fake values resembling:

- GitHub PAT,
- API key,
- `PASSWORD=...`,
- Authorization header,
- cookie/session token,
- credential-bearing URL,
- private-key-shaped content.

Expected result:

- raw value never appears in Work Evidence, normal Audit presentation, result cards, screenshots or client-visible errors,
- harmless ordinary text is not over-redacted.

## Company Graph / Org-Canvas acceptance

The company graph is not a tree-only model.

Golden checks:

- agent can belong to multiple teams,
- agent can work on multiple projects,
- team can have subteams,
- relationship removal does not delete the agent,
- reporting cycle/self-report is blocked or handled safely,
- membership does not escalate capability/risk rights,
- resource links do not expose credentials,
- agent/team/project/company rooms retain correct context,
- desktop graph and mobile/list views represent the same underlying identity/relationships.

## Learning/Skill/Memory acceptance

Golden checks:

- completed + reviewer-approved mission may create/update reusable learning,
- rejected/failed mission does not become an approved learned skill,
- learned skill is procedure, not transcript dump,
- unsafe learned skills stay draft until approval,
- agent/project memory isolation holds,
- explicit shared memory can be reused,
- Memory contains no credentials,
- Progressive Context obeys item/size/token-estimate limits,
- compaction is auditable.

## Cost Governor acceptance

Required checks:

- local models have financial model-cost value `0 EUR`,
- local usage still records calls/tokens estimate/latency/runtime/retries,
- mission with external budget `0 EUR` cannot silently call paid remote models,
- budget cannot be disabled by child agents,
- retry/spawn loops are bounded,
- paid-provider reservation/recording path is provider-agnostic,
- privacy/security policy may block remote calls even when budget exists.

## No-LLM acceptance

A healthy deterministic routine must prove:

```text
model_calls = 0
```

Examples:

- HTTP status check,
- disk threshold check,
- service status,
- SSL expiry,
- backup/file existence,
- Git clean/dirty state.

Only anomaly handling may escalate to a model according to policy.

## Golden task categories

Maintain 10–25 repeatable tasks covering:

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
12. Remote-model budget block/fallback
13. Work Evidence generation
14. Secret-redaction adversarial test
15. Skill learning from approved mission
16. Skill reuse on repeated mission
17. Agent/project memory isolation
18. Progressive Context compaction
19. No-LLM healthy routine
20. Company Graph multi-membership
21. Project/team/company room context
22. Resource/repository metadata
23. Browser task when real Browser Capability exists
24. SSH/infrastructure task when enabled
25. Real HufManager release/readiness workflow

## Release thresholds for V1.2

V1.2 is acceptable when:

- all existing V1.1.2 data survives additive migration on a production-shaped DB copy,
- deterministic end-to-end golden tasks remain green,
- real local-Qwen mission completes with reviewer approval,
- real Work Evidence is generated from that mission,
- controlled fake-secret evidence is redacted,
- second similar mission demonstrates actual Skill/Memory reuse,
- healthy deterministic routine records 0 model calls,
- Company Graph team/project/resource/room flows persist and reload,
- normal UI does not expose raw IDs/risk/provider jargon by default,
- real browser QA passes required breakpoints with no fake capability claims,
- no paid API is required to run CI/evaluation.

## Grok Bot comparison

Use equivalent real-world missions where possible and compare:

- completion quality,
- time,
- human intervention,
- recovery,
- cost,
- auditability,
- Visible Work / trust,
- security controls,
- simplicity for non-technical users.

Do not chase cosmetic 1:1 parity. Close the highest-value functional gaps first and keep a clean-room implementation.
