# 00A - HufiAgents CURRENT STATE - KI START HERE - Source of Truth

## Current Production State

Production release:
**v1.4.0**

Production SHA:
**8dca1f70fd4a840feae3e47d047d2db1eafc82e6**

Production URL:
https://agents.heyhufi.com

PRs Merged in V1.4.0:
- PR #39 (Hufi Corporate Matrix & Live Workforce)
- PR #40 (Hotfix: User bubble text redaction in chat.js)
- PR #41 (Release metadata: Bump package version to 1.4.0)

## Verified V1.4.0 Capabilities

- **Corporate Matrix**: REAL (`OrganizationUnit` hierarchy `GROUP` → `COMPANY` → `BUSINESS_UNIT` → `DEPARTMENT` → `TEAM`, `GraphRelationship` edge model, Migration 012)
- **Mr. Equi Routing**: REAL (`CorporateRouter` deterministic routing without LLM in routing path)
- **Owner Outcome Contracts**: REAL (gated completion requiring generated deliverables, independent reviewer approvals, and work evidence)
- **Live Workforce Telemetry**: REAL (`/company/live`, `/company/pulse`, `/company/workforce` derived strictly from persisted runtime state)
- **Agent Workspace**: REAL (current activity, tasks, timeline, artifacts, evidence, handoffs)
- **Unit Workspace**: REAL (workers, tasks, artifacts, events, blockers/reviews)
- **Secret Redaction**: REAL (structured redaction across UI, API, audit logs, and evidence)
- **Test Suite**: 508 / 508 tests PASS
- **Visual Acceptance**: PASS (desktop 1366x768 & mobile 390x844)
- **Production Smoke**: PASS

## Known Limitations / Deferred Items

- Multilingual intent matching → deferred to V1.4B.
