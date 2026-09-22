# 00A - HufiAgents CURRENT STATE - KI START HERE - Source of Truth

**Stand:** 22.09.2026

## Current Production State

Last verified production release:

**v1.4.0**

Production release SHA:

**8dca1f70fd4a840feae3e47d047d2db1eafc82e6**

Production URL:

https://agents.heyhufi.com

Repository:

`passaondigital/HufiAgents`

GitHub documentation baseline before this docs-only update:

`44b801fbe69b810e55e08ff982232301778b22bf`

No newer repository commit than the 11.09.2026 v1.4.0 release-documentation commit was found during the 22.09.2026 status reconciliation.

> Important: this 22.09 update is a documentation reconciliation. No fresh production runtime probe was performed as part of this update. Runtime claims below therefore refer to the last verified v1.4.0 production acceptance on 11.09.2026 unless explicitly stated otherwise.

## Verified V1.4.0 Capabilities

- **Corporate Matrix**: REAL / last verified PRODUKTIV
- **Mr. Equi Routing / CorporateRouter**: REAL
- **Owner Outcome Contracts**: REAL
- **Live Workforce Telemetry**: REAL
- **Agent Workspace**: REAL
- **Unit Workspace**: REAL
- **Secret Redaction**: REAL
- **Database Migration 012**: verified during v1.4.0 release
- **Test Suite**: 508 / 508 PASS at release
- **Ruff / Format / Secret Scan**: PASS at release
- **Real Browser Visual Acceptance**: PASS at release on desktop 1366×768 and mobile 390×844
- **Production Smoke**: PASS at release

## V1.4.0 Traceability

Merged release PRs:

- PR #39 — Hufi Corporate Matrix & Live Workforce
- PR #40 — User-bubble text redaction hotfix
- PR #41 — v1.4.0 release metadata/version bump

Release record:

`docs/releases/V1_4_0_PRODUCTION_RELEASE.md`

## Known Limitations / Deferred Items

Unless a newer runtime/repo proof supersedes them:

- multilingual intent matching remains deferred to V1.4B,
- Learning/Skill promotion still requires manual approval,
- Memory relevance remains deterministic / word-overlap rather than semantic/vector retrieval,
- active Chromium browser tabs do not survive a full application restart,
- a durable fully encrypted credential vault remains open.

## Product Rule

HufiAgents is the workforce/capability engine below HufiBoss.

Owner intent should flow:

`Pascal → HufiBoss → HufiAgents → Units / Teams / Agents → Evidence / Review → Result`

The system must continue to prefer:

- real work over simulated activity,
- evidence over reassuring text,
- minimum necessary agent fan-out,
- local-first/model-agnostic execution,
- explicit approval only for genuinely risky actions.

## Next Focus

Do not restart broad architecture work without evidence of need.

Use v1.4.0 in real work, collect failures/latency/UX evidence, and derive V1.4B from actual operational gaps.

## Naming

“AgentHufi” may be used conversationally for the public/agent product direction, but the currently verified GitHub implementation and production system documented here is **HufiAgents**.

## Source-of-Truth Rule

Priority:

1. fresh runtime evidence,
2. current production release record,
3. `docs/CURRENT_STATE.md`,
4. current code/tests,
5. older Drive/README/roadmap documents.

Never put real credentials, customer data, private keys or production secrets into Git.
