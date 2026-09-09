# HufiAgents Current State

Release baseline:
v1.2.0

Main release commit:
887ce6871da2f1fd420d1b0ecf4ae830941fab23

Production:
https://agents.heyhufi.com

Current development:
V1.3 — RELEASE CANDIDATE

## V1.3 Release Candidate Status

Integration branch: `integration/v1-3-full-system`

All V1.3 feature PRs proven and ancestry-verified:

- PR #29 — Room → Runtime bridge
- PR #30 — Autonomous Routine Runtime
- PR #31 — Engineering Repo Context
- PR #32 — Real Visible Execution / WorkEvidence
- PR #33 — Workforce Builder
- PR #34 — Real Chromium Browser (Playwright)
- PR #35 — Memory + Skills Runtime Reuse
- PR #27 — Persistent Workspace / Session / MCP (integrated into PR #34)

## Proven V1.3 Capabilities

- Room → Runtime: real agent dispatch from team rooms
- Autonomous Routine scheduler: ticks, claims, dispatches without manual trigger
- Engineering Repo Context: bounded, redacted, relevance-ranked source context
- Visible Execution: real WorkEvidence from real events (no fake indicators)
- Workforce Builder: provision/configure/archive digital employees
- Persistent Workspace / Session / MCP adapters
- Real Chromium browser via Playwright: navigation, click, type, screenshot (PNG)
- Memory + Skills Runtime Reuse: approved knowledge injected automatically,
  unapproved/wrong-scope/secret content excluded
- Multi-agent fan-out / fan-in / delegation / review
- Risk ceiling / capability / approval / budget guards
- Secret redaction across all persistence and evidence paths
- Local-first deterministic retrieval (retrieval_model_calls = 0)

## V1.3 Known Limitations / Gaps

- Learning promotion UI: draft skills from learn_from_mission() need manual
  approval; no dedicated promotion UI yet
- Word-overlap relevance only (no semantic/vector retrieval)
- Team scope wired but team assignment not yet surfaced in Workforce Builder UI
- Browser process and cookies do not survive application restart (metadata does)
- durable encrypted credential vault: not yet implemented

## Production Decision

V1.3 RELEASE CANDIDATE READY.
Production release requires a separate controlled deployment task.
Production remains v1.2.0 until that task is completed.
