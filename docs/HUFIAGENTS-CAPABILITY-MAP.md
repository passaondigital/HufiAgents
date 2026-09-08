# HufiAgents — Reusable Capability Map

**Date:** 2026-09-08  
**Production baseline:** `v1.1.2`  
**Rule:** implement capabilities once; expose them through different Hufi products.

## Product surfaces

| Surface | Primary purpose | User sees |
|---|---|---|
| HufiBoss | Pascal’s private co-CEO/master | goals, priorities, decisions, results |
| HufiAgents | workforce engine + internal operator UI | digital company, teams, projects, work, approvals, results; technical details optional |
| Hufi Manager | business-management assistant | CRM/business workflows in simple Hufi UX |
| HufiApp | personal Jarvis-level assistant | chat, voice, memory, files, calendar, routines |
| AgentHufi / HufiApp Pro | autonomous workforce product | specialists, teams, projects, browser/computer |
| HufiCloud | later builder/composition platform | user-owned AI environment assembled from capabilities |
| Hufi Factory | internal software/product factory | projects, build/review pipelines, agents, evidence, releases |

## Core capability ownership

| Capability | HufiAgents owns core? | HufiBoss | Hufi Manager | HufiApp | AgentHufi | HufiCloud |
|---|---:|---:|---:|---:|---:|---:|
| Mission/orchestration | yes | full | selected | selected | full | configurable |
| Dynamic agents | yes | full | hidden/selected | hidden | full | configurable |
| Agent messaging/delegation | yes | full | hidden | hidden | full | configurable |
| Review/Master Audit | yes | full | automatic | automatic | full | configurable |
| Model Router | yes | policy | hidden | hidden | policy | configurable |
| Cost Governor | yes | full | tenant/product policy | user/product policy | full | configurable |
| Skills | yes | full | domain skills | personal skills | full | marketplace/builder |
| Memory | yes | company/project | business | personal | project/team | configurable |
| Progressive Context | yes | full | automatic | automatic | full | configurable |
| Learning Loop | yes | full | domain-safe | personal-safe | full | configurable |
| Routines | yes | full | business routines | personal routines | full | configurable |
| No-LLM routines | yes | full | hidden/automatic | hidden/automatic | full | configurable |
| Work Evidence / Visible Work | yes | full | simplified | simplified | full | configurable |
| Company Graph | yes | full | hidden/selected | hidden | full | builder surface |
| Teams / Projects / Relationships | yes | full | selected | selected | full | configurable |
| Chat Rooms | yes | full | business rooms | personal/project rooms | full | configurable |
| Resources (repos/servers/tools) | yes | full | selected | selected | full | configurable |
| Credential / Secret capability | yes | full | connector-scoped | connector-scoped | full | configurable |
| Files/workspaces | yes | full | selected | selected | full | configurable |
| Browser | yes | full | task-specific | selected | full | configurable |
| Computer | yes | full | rarely exposed | selected | full | configurable |
| Git/GitHub | yes | full | hidden | no/default | developer packs | connector |
| Gmail/Calendar/Drive | connector layer | full | selected | full | full | connector |
| MCP/plugins | connector layer | full | hidden | selected | full | marketplace/builder |
| Approvals | yes | full | human-language | human-language | full | policy |
| Audit | yes | full/detail | simplified | simplified | full | tenant-scoped |
| Recovery | yes | automatic | automatic | automatic | automatic | policy |
| Gateway/channels | yes later | full | app channel | voice/app | multi-channel | configurable |
| Notifications | yes later | full | business alerts | personal alerts | full | configurable |

## Reuse rule

A capability is considered architecturally complete only when:

1. the core logic is not tied to one UI screen,
2. permissions and policy are explicit,
3. the capability can be called through a stable internal interface,
4. normal UX can hide its technical configuration,
5. audit/recovery behavior is defined,
6. it can later be tenant-scoped without rewriting the core behavior,
7. secret handling is explicit where credentials are involved,
8. visible status is derived from real state/evidence rather than presentation-only fiction.

## Simplicity rule

Every product decides **how much capability to expose**, not whether to duplicate the capability.

Example:

```text
HufiAgents Routine Engine
        |
        +-- HufiBoss: full controls
        +-- Hufi Manager: “Remind/Check every Monday”
        +-- HufiApp: personal routines
        +-- AgentHufi: autonomous team routines
        +-- HufiCloud: configurable routine block
```

The end user should never need to know that all five surfaces share the same routine engine.

The same applies to Work Evidence, Memory, Skills, Teams, Credentials and Browser/Computer capabilities.

## Digital-company rule

HufiAgents is not modeled as a pile of chat threads. The target is a **digital company graph**:

```text
Owner / Pascal
   ↕
Agents ↔ Teams ↔ Projects ↔ Resources
   ↕       ↕         ↕
Chats   Routines   Work Evidence
```

An agent may belong to multiple teams/projects at once. Drag & drop changes relationships; it must never silently increase capability/risk rights.

Canonical product spec: `docs/product/ORG-CANVAS.md`.

## Visible Work rule

Normal users need understandable evidence that real work happened. Work Evidence is separate from raw technical audit and must be derived from real mission/tool/review/artifact events.

Never fabricate progress, snapshots, live-computer state or success.

Canonical spec: `docs/product/VISIBLE-WORK.md` and `docs/product/ORG-CANVAS-WORK-EVIDENCE.md`.

## Credential rule

Secrets are a reusable capability, not chat content.

- never ask users to paste tokens into ordinary chat,
- never put raw secrets in Memory, Skills, Audit, Work Evidence or results,
- normal GET APIs never return full secret values,
- agents receive scoped connector/credential handles rather than plaintext by default,
- credential replacement/revocation must be possible,
- if safe encryption-at-rest is not available, fail closed instead of inventing weak crypto.

## Current status

### Production `v1.1.2` — real

- orchestration,
- local HUFI model routing,
- review/retry,
- recovery,
- approvals,
- audit,
- isolation,
- HufManager project path,
- dynamic agents,
- messaging/delegation,
- fan-out/fan-in,
- routines,
- chat-first product UI,
- V1.1.2 warm Hufi visual pass.

### V1.2 — active implementation

Codex owns the engine/backend track:

- Work Evidence + redaction,
- Company Graph,
- teams/projects/resources/relationships/chat rooms,
- Skills,
- scoped Memory,
- Progressive Context,
- Learning Loop,
- Cost Governor,
- No-LLM routines,
- Credential Foundation,
- real work summary/audit additions.

Claude Code owns the product/frontend track:

- Org-Canvas,
- agent/team/project/resource cards,
- drag & drop + accessible alternatives,
- agent/team/project/company chat surfaces,
- Visible Work/evidence cards,
- Simple / Transparent / Live modes,
- secret/token UX,
- desktop/tablet/mobile/accessibility QA.

### V1.3

- persistent Browser,
- persistent Computer,
- real snapshots/live preview,
- MCP/tool adapters,
- session handoff/reset/recovery.

### V1.4

- Gateway,
- notifications,
- voice/devices/channels,
- event triggers/watchers.

### V1.5+

- stable product capability layer reused in Hufi Manager and HufiApp,
- later AgentHufi / HufiApp Pro,
- later HufiCloud composition/builder.

## Architecture guardrail

Before implementing a new feature, ask:

> Is this a Hufi capability, or only a screen-specific feature?

If it is a capability, build it below the product surface first and make the UI a client of it.

A screen may visualize a capability, but it must not become the only place where the capability exists.
