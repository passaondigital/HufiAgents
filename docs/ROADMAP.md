# HufiAgents Roadmap

**Updated:** 2026-09-08  
**Production baseline:** `v1.1.2` at `https://agents.heyhufi.com`  
**North Star:** one instruction from Pascal should produce as much finished, reviewed, economically useful work as possible with minimal human coordination.

This file is the concise delivery roadmap. The binding long-form target is `docs/HUFIAGENTS-TARGET-PLAN.md`.

## Completed foundation — V1.0.x

Real and production-proven:

- FastAPI + SQLite core,
- login/auth + HTTPS deployment,
- mission/task lifecycle,
- local HUFI AI Router integration,
- real local Qwen execution,
- review + retry,
- crash/heartbeat recovery,
- risk/approval engine,
- append-only audit,
- isolated workspaces / Bubblewrap,
- controlled Git/GitHub push/PR path,
- HufManager as first real project connector/use case.

Historical details remain in `docs/CORE-V1.md`, `docs/V1-RELEASE.md`, `docs/CONNECTOR-HUFMANAGER.md`, `docs/PHASE2-GIT-PR-WORKFLOW.md`, `docs/DECISIONS.md` and related review records.

## Shipped — V1.1.x

`v1.1.2` is the stable product baseline.

Shipped capabilities include:

- chat-first UI,
- dynamic/persistent agents,
- agent messaging and delegation,
- fan-out/fan-in team execution,
- real routines API/UI,
- workspace/session foundation,
- connector registry foundation,
- HufManager team mission,
- human-language approvals/results,
- safe DOM-based result rendering,
- 10-year-old UX rules,
- warm Hufi visual system,
- responsive/browser QA across desktop/tablet/mobile.

V1.1.x is now frozen except for real bug/security fixes.

## V1.2 — Hufi learns, proves work and becomes a digital company

**Status:** active parallel implementation.

V1.2 combines the learning/efficiency layer with the new Digital Company and Visible Work foundations.

### Backend / engine — Codex track

- Work Evidence persistence and APIs,
- evidence-source traceability,
- secret/sensitive-data redaction,
- Company Graph data model,
- teams,
- projects and memberships,
- resources,
- typed relationships,
- agent/team/project/company chat-room context,
- Skill Engine,
- scoped Memory,
- Progressive Context Loader,
- Learning Loop after successful reviewed missions,
- Cost Governor,
- local-first routing policy,
- No-LLM deterministic routines,
- Credential / Secret capability foundation,
- real work-summary service,
- additive SQLite migrations,
- API contract in `docs/implementation/V1_2_API_CONTRACT.md`.

### Product / frontend — Claude Code track

- Org-Canvas,
- agent/team/project/resource cards,
- repository grid/cards,
- drag & drop relationship management,
- keyboard/form alternatives to drag & drop,
- multi-membership visualization,
- organisation/teams/projects/resources/list views,
- agent chat,
- team chat,
- project chat,
- company chat,
- Visible Work / evidence cards,
- `Einfach / Transparent / Live` modes,
- truthful work summary,
- secure credential/token UX,
- desktop/tablet/mobile/accessibility QA.

### V1.2 product laws

1. No fake progress.
2. No fake snapshots.
3. No fake live computer.
4. No fake success.
5. Normal users see people, teams, projects and work — not provider/router/task-ID jargon.
6. Secrets are never ordinary chat content.
7. Team/project membership does not silently grant capability/risk rights.
8. One agent may belong to several teams/projects at the same time.

### V1.2 acceptance evidence

Before release, prove on a production-shaped DB copy and real XXL environment:

- existing V1.1.2 data survives migration,
- a real local-Qwen mission produces real Work Evidence,
- a second similar mission reuses approved Skill/Memory context,
- a healthy deterministic routine performs **0 model calls**,
- a controlled fake-secret case is safely redacted,
- a team/project/resource/room graph can be created and read back,
- UI consumes real APIs without shipping fake backend state,
- full tests/lint/compile and real browser QA are green.

## V1.3 — Hufi gets hands

Theme: persistent Computer / Browser / Workspace.

Build:

- persistent per-agent workspace,
- real browser automation,
- retained safe browser sessions,
- computer/session lifecycle,
- controlled file interaction,
- real screenshots and evidence artifacts,
- optional live preview,
- user handoff,
- reset/snapshot/recovery,
- MCP tool adapter,
- connector permission scopes.

Visible Work becomes richer here because screenshots/live views can be generated from real sessions rather than placeholders.

**Exit:** Pascal can ask a Hufi to inspect and interact with a real web app, receive sanitized evidence, and get a reviewed result without manually driving the browser.

## V1.4 — Hufi is always available

Theme: Gateway / Events / Devices / Channels.

Build selectively:

- Hufi Gateway,
- notifications,
- voice entry points,
- device/node concept,
- selected messaging channels,
- event triggers,
- channel-independent mission identity,
- always-on routines/watchers.

Only add channels when they remove real friction.

## V1.5 — Product Capability Layer

Expose stable internal capability interfaces so real Hufi products can reuse the engine without duplicating orchestration.

First reuse targets:

- Hufi Manager,
- HufiApp.

Reusable capabilities include:

- chat/mission,
- skills,
- memory,
- routines,
- Work Evidence,
- approvals,
- resources/connectors,
- credential handles,
- notifications,
- model/cost policy.

**Exit:** at least one meaningful Hufi capability is implemented once and consumed from at least two product surfaces.

## V2 — AgentHufi / HufiApp Pro

Only after the internal engine is stable and genuinely useful:

- public user-created agents,
- teams/projects,
- product-safe browser/computer,
- tenant-scoped memory,
- usage/cost budgets,
- onboarding,
- billing only when commercially required.

## Later — HufiCloud

Composable builder/platform for:

- agents,
- skills,
- models,
- memory,
- projects,
- teams,
- resources,
- browser/computer,
- connectors,
- routines,
- workflows,
- product surfaces.

Users assemble outcomes such as “My Company” rather than infrastructure primitives.

## Canonical product specs

- `docs/HUFIAGENTS-TARGET-PLAN.md`
- `docs/HUFIAGENTS-CAPABILITY-MAP.md`
- `docs/HUFIAGENTS-PRODUCT-VISION.md`
- `docs/product/VISIBLE-WORK.md`
- `docs/product/ORG-CANVAS.md`
- `docs/product/ORG-CANVAS-WORK-EVIDENCE.md`
- `docs/SECURITY.md`
- `docs/OPERATING_MODEL.md`
- `docs/EVALUATION.md`

## Business guardrail

HufiAgents must not become an endless meta-project. The engine exists to make real products and real operations easier, cheaper and more autonomous. HufManager remains the first business-priority proof case.
