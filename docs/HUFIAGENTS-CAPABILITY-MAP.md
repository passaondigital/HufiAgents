# HufiAgents — Reusable Capability Map

**Date:** 2026-09-08  
**Rule:** implement capabilities once; expose them through different Hufi products.

## Product surfaces

| Surface | Primary purpose | User sees |
|---|---|---|
| HufiBoss | Pascal’s private co-CEO/master | goals, priorities, decisions, results |
| HufiAgents | workforce engine + internal operator UI | teams, work, approvals, results; technical details optional |
| Hufi Manager | business-management assistant | CRM/business workflows in simple Hufi UX |
| HufiApp | personal Jarvis-level assistant | chat, voice, memory, files, calendar, routines |
| AgentHufi / HufiApp Pro | autonomous workforce product | specialists, teams, projects, browser/computer |
| HufiCloud | later builder/composition platform | user-owned AI environment assembled from capabilities |

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
| Routines | yes | full | business routines | personal routines | full | configurable |
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
6. it can later be tenant-scoped without rewriting the core behavior.

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

## Current status

### Real production V1.0.1

- orchestration,
- local model routing,
- review/retry,
- recovery,
- approvals,
- audit,
- isolation,
- HufManager project path.

### Integrated V1.1 candidate

- dynamic agents,
- messaging,
- delegation,
- fan-out/fan-in,
- real routines,
- chat-first UI,
- workspace/session foundation,
- connector registry.

### Next shared capabilities

V1.2:

- Skills,
- procedural/project/agent memory,
- learning loop,
- progressive context,
- Cost Governor,
- no-LLM routines.

V1.3:

- persistent Browser,
- persistent Computer,
- MCP/tool adapters,
- snapshots/handoff.

V1.4:

- Gateway,
- notifications,
- voice/devices/channels.

## Architecture guardrail

Before implementing a new feature, ask:

> Is this a Hufi capability, or only a screen-specific feature?

If it is a capability, build it below the product surface first and make the UI a client of it.
