# V1.4.0 Production Release Record

Date: 2026-09-11
Tag: v1.4.0
Commit SHA: 8dca1f70fd4a840feae3e47d047d2db1eafc82e6
Production URL: https://agents.heyhufi.com

## Release Summary

HufiAgents V1.4.0 introduces the **Hufi Corporate Matrix & Live Workforce Experience**.

### Key Features
1. **HufiBoss-first Operating Model**: HufiBoss acts as primary front-door entry point; worker agents and company graph are accessible as drill-downs.
2. **Corporate Matrix**: Full `OrganizationUnit` hierarchy (`GROUP` → `COMPANY` → `BUSINESS_UNIT` → `DEPARTMENT` → `TEAM`) with `GraphRelationship` edge model and `bootstrap_corporate_matrix()` idempotent seed.
3. **Mr. Equi Routing**: `CorporateRouter` deterministically routes owner instructions to units/agents based on persisted responsibilities, capabilities, and workload; zero LLM calls in the routing path.
4. **Owner Outcome Contracts**: Gated completion requiring generated deliverables, independent reviewer approvals, and per-task work evidence.
5. **Live Workforce Telemetry**: Real-time event streams (`/company/live`, `/company/pulse`, `/company/workforce`) derived strictly from persisted runtime state.
6. **Agent & Unit Workspaces**: Truthful visualization of active tasks, artifacts, handoffs, and evidence without fake activity or fabricated counters.
7. **Secret Redaction**: Structured secret redaction across all visible UI surfaces, audit logs, and API endpoints.
8. **Database Migration 012**: Additive schema upgrade (`012_v1_4a_corporate_matrix.py`) introducing `organization_units` and `relationships` tables; 100% backward compatible with V1.3.1 production data.

## Verification & Acceptance
- **Full Test Suite**: 508 / 508 tests PASS
- **Ruff Check / Format**: PASS
- **Secret Scan**: PASS
- **Real Browser Visual Acceptance**: PASS (Desktop 1366x768 & Mobile 390x844)
- **Production Backup**: `/srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.3.1-pre-v1.4.0-20260911-203400.sqlite3`
- **Production Service**: Restarted `hufiagents.service`, status active (running)
- **Production Smoke**: PASS (Health 200 OK, Pulse 200 OK, Org Units 200 OK, Simple Owner Mission 202, Secret Redaction PASS)

## PR Traceability
- Merged PR #39 (Hufi Corporate Matrix)
- Merged PR #40 (Hotfix: User bubble text redaction)
- Merged PR #41 (Release metadata: Bump version to 1.4.0)

## Deferred / Future Work
- Multilingual intent matching → deferred to V1.4B.
