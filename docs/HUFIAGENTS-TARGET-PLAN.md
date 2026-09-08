# HufiAgents — Target Plan, 1:99 Operating Model and Roadmap

**Status:** binding target plan / living roadmap  
**Date:** 2026-09-08  
**Production today:** `v1.1.2` at `https://agents.heyhufi.com`  
**Current development:** V1.2 — Learning + Visible Work + Digital Company foundations  
**V1.1.x rule:** frozen except real bug/security fixes

---

## 1. North Star

HufiAgents exists so Pascal can state a goal once and receive finished, reviewed work instead of coordinating tools, terminals, models and agents manually.

The target is not “many AI tools”. The target is a **digital company**.

```text
Pascal
  -> HufiBoss
      -> HufiAgents
          -> Project Leads / Teams
              -> Specialists
              -> Reviewers
              -> Skills / Memory / Routines
              -> Resources / Repos / Servers
              -> Tools / Computer / Browser
```

**HufiBoss** is Pascal’s private master/co-CEO layer.  
**HufiAgents** is the reusable workforce engine underneath.  
Everything below HufiBoss can be treated as digital employees, teams, projects, resources, skills, tools and autonomous routines.

The central success question is:

> How much useful result comes from one instruction by Pascal?

That is the 1:99 principle in software form.

---

## 2. Product law: a 10-year-old must understand the normal UI

The normal interface must be understandable without technical knowledge.

### The 10-year-old test

A normal user must be able to answer within seconds:

1. Where do I type what I want?
2. What is Hufi doing right now?
3. Is it finished?
4. Did something fail?
5. Does Hufi need my permission?
6. What should I do next?

If any answer requires understanding terms such as provider, model router, task UUID, risk ceiling, worker, migration, token budget or audit JSON, the normal UI has failed.

### Binding UX rules

- Chat is a primary control surface.
- One clear primary action per screen/state.
- Normal language before system language.
- Technical details only behind **Details / System / Expert**.
- No raw UUIDs, internal agent IDs or R0–R4 codes in the normal flow.
- Approvals explain consequences, not internal policy codes.
- Errors always provide a next action.
- Repeating work is expressed conversationally (“every Monday at 8”).
- Agent creation asks human concepts first: name, picture/avatar, responsibility.
- Mobile, tablet and desktop are equal product surfaces.
- Accessibility is a product requirement, not a polish task.
- Defaults must be safe and useful; configuration is progressive disclosure.
- Visible activity must come from real state/evidence; never invent work to make the UI feel alive.

Design brief:

> HufiAgents should feel like a very simple messenger with a team of digital employees, while underneath it runs a secure, auditable, self-recovering multi-agent system.

---

## 3. Operating principles: 1:99, 20:80, Open Source -> Cash Machine

### 1:99

One instruction should trigger as many safe follow-up actions as useful without Pascal becoming the message bus.

Example:

> “Make HufManager more sellable this quarter.”

Possible automated chain:

- inspect current product,
- analyse blockers,
- form/select a team,
- split work,
- implement safe fixes,
- test,
- review,
- retry/recover,
- create reports/branches/PRs,
- prepare marketing/SEO follow-ups,
- schedule recurring checks,
- learn reusable patterns after reviewed success,
- ask Pascal only for genuinely important decisions.

### 20:80

Build the capabilities that remove the most human coordination first:

1. reliable autonomous execution,
2. simple UX,
3. visible/trustworthy work,
4. learning/skills/memory,
5. routines and deterministic automation,
6. computer/browser,
7. high-value connectors,
8. product integration.

Do not spend 80% of development time on low-value technical decoration.

### Open Source -> Cash Machine

Open-source infrastructure should reduce the cost of the technical foundation. Commercial value comes from:

- integration,
- automation,
- simplicity,
- domain knowledge,
- reliable workflows,
- data/context,
- product UX,
- outcomes.

HufiAgents is built internally first. Later the same capabilities can power Hufi Manager, HufiApp, AgentHufi and HufiCloud without rebuilding the engine four times.

---

## 4. Internal first, reusable everywhere

HufiAgents is **not primarily a SaaS today**. It is Pascal’s own operating system for digital work.

Every major function should be designed as reusable infrastructure rather than hard-coded into one screen.

Bad framing:

> “Build a browser into the HufiAgents page.”

Correct framing:

> “Build a Browser Capability that HufiAgents, HufiBoss, HufiApp and HufiCloud can use.”

### Capability-first architecture

```text
HUFI CORE CAPABILITIES

Agent Engine
Orchestrator
Model Router
Cost Governor
Skills
Memory
Progressive Context
Learning Loop
Routines
No-LLM Automation
Work Evidence / Visible Work
Company Graph
Teams / Projects / Relationships
Chat Rooms
Resources
Credential / Secret Capability
Workspace
Files
Shell
Git / GitHub
Browser
Computer
Connectors
MCP
Approvals
Audit
Recovery
Notifications
Gateway
```

Product surfaces consume subsets of the same capabilities.

---

## 5. Product hierarchy

### HufiBoss — Pascal only

Purpose: private master / co-CEO / second brain.

HufiBoss should:

- know all relevant projects,
- accept strategic goals,
- prioritise,
- form teams,
- delegate,
- monitor results,
- surface decisions and relevant blockers,
- learn what works,
- keep model/API spending under control.

Pascal should not have to manage every specialist agent directly.

### HufiAgents — workforce engine

Purpose: reusable execution layer.

Contains:

- dynamic agents,
- messaging/delegation,
- fan-out/fan-in,
- review,
- memory/skills,
- tools,
- routines,
- model routing,
- teams/projects/resources,
- Work Evidence,
- approvals,
- audit/recovery,
- later persistent computer/browser and gateway.

### Hufi Manager

Consumes only business-relevant capabilities, e.g.:

- Hufi chat,
- CRM/task agents,
- schedules/routines,
- communication,
- documents,
- project/business memory,
- selected connectors,
- simplified Work Evidence where useful.

Users should not see “HufiAgents architecture”. They see a simple assistant.

### HufiApp

Personal Jarvis-level layer:

- chat + voice,
- memory,
- files,
- calendar,
- communication,
- proactive hints,
- routines,
- simple actions,
- selected connector capabilities.

### AgentHufi / HufiApp Pro

Jarvis plus workforce:

- own specialists,
- teams,
- delegation,
- parallel work,
- browser/computer,
- projects,
- connectors,
- autonomous routines,
- approvals/review,
- visible work/evidence.

### HufiCloud

Later composition/builder platform:

- agents,
- teams,
- skills,
- models,
- memory,
- data,
- computers,
- browser,
- connectors,
- routines,
- workflows,
- projects,
- surfaces.

The user assembles outcomes such as “My Stable” or “My Company”, not infrastructure primitives.

---

## 6. Reconciliation: what is real today

### Production `v1.1.2` — real

The production baseline now includes the proven V1 core plus the integrated V1.1 workforce/product layer:

- login-gated web service,
- FastAPI + SQLite core,
- local HUFI AI Router,
- real local Qwen execution,
- mission/task lifecycle,
- review and retry,
- crash/stale-heartbeat recovery,
- approval/risk engine,
- persistent audit,
- HufManager connector,
- Bubblewrap isolation,
- controlled Git/GitHub path,
- dynamic/persistent agents,
- agent messaging,
- delegation,
- fan-out/fan-in,
- routines API/UI,
- workspace/session foundation,
- connector registry foundation,
- HufManager team mission,
- chat-first interface,
- human-language approval/result surfaces,
- safe DOM-based result rendering,
- responsive V1.1.2 warm Hufi visual pass.

The previous V1.1 release gates — conversational routines, false-success prevention and reachable approvals — were closed before release. V1.1.x is now frozen except bug/security work.

### Honest current gap

The computer/browser layer is still a **foundation**, not yet the persistent per-agent desktop/browser experience targeted for V1.3.

Do not represent a placeholder/empty computer as real execution.

---

## 7. What we take from Grok Bot, Hermes Agent and OpenClaw

These are references for product principles and architecture ideas, not code-copy sources.

### Grok Bot -> product experience + computer

Use as benchmark for:

- extremely simple chat-first UX,
- agent/sidebar mental model,
- dynamic bot creation,
- own chat/persona,
- routines,
- visible computer slot,
- persistent workspace/computer feeling,
- permissions in human language,
- marketplace packaging.

Additional lesson from hands-on testing:

- users need to trust that work is really happening,
- visible computer/snapshot/evidence must reflect reality,
- token/credential collection should not happen as an ordinary chat message in Hufi.

### Hermes Agent -> learning + efficiency

High-value concepts to implement:

- reusable Skills,
- procedural memory,
- project/agent memory separation,
- learning loop from successful missions,
- progressive disclosure / load only relevant context,
- skills improved from repeated successful work,
- no-LLM routines for deterministic checks,
- model/provider fallback without wasting expensive context.

### OpenClaw -> gateway + channels + modular extensions

High-value concepts for later phases:

- always-on gateway,
- plugins/capabilities,
- MCP integration,
- device/node integration,
- browser/computer channels,
- messaging channels,
- event hooks,
- notifications.

Do not rebuild all of OpenClaw/Hermes/Grok Bot. Extract only capabilities that improve Hufi’s 1:99 outcome and implement them clean-room.

---

## 8. Model and cost strategy

### Local-first routing

Default escalation ladder:

```text
hufi-qwen9-fast
  -> hufi-qwen9
      -> hufi-gemma
          -> cheap remote API if justified
              -> premium remote model only when needed
```

HufiAgents uses the existing HUFI Local AI Router. Do not install a second Ollama stack for this project.

Local models have financial model-call cost `0 EUR`, but usage still needs measurement: calls, estimated tokens, latency/runtime and retries.

### Cost Governor — mandatory before broad API use

Required capabilities:

- per-mission external cost ceiling,
- per-agent budget,
- per-project budget,
- daily/weekly/monthly ceilings,
- token/context limits,
- maximum remote parallelism,
- no unbounded child-agent spawning with paid models,
- local-first fallback/quality escalation,
- cache repeated deterministic results,
- summarize locally before sending to expensive models,
- compact long context and load only relevant knowledge,
- retry policy that avoids repeatedly paying for the same failure,
- audit actual and estimated cost per mission,
- optional modes: **Sparsam / Ausgewogen / Maximale Qualität**.

V1.2 default mission external budget:

```text
0 EUR = LOCAL ONLY
```

Target principle:

> Use the cheapest capability that can reliably finish the job.

Privacy/security policy may still forbid remote use even when budget exists.

---

## 9. Learning architecture

HufiAgents becomes more valuable when successful work becomes reusable.

```text
Mission
  -> execution
      -> review
          -> approved success?
              -> memory/skill candidate
                  -> safe reuse next time
```

### Memory layers

1. **HufiBoss/user/global memory** — strategic/company context.
2. **Project memory** — repo/product-specific facts and decisions.
3. **Agent memory** — role-specific context.
4. **Mission memory** — bounded run context.
5. **Shared knowledge** — explicitly reusable cross-scope knowledge.
6. **Procedural skills** — how to perform recurring work.
7. **Run history/audit** — what actually happened.

Memory must stay scoped; agents should not receive the entire company history for every task.

### Skill rule

A skill contains reusable procedure, not a dump of chat history.

Examples:

- HufManager release check,
- safe dependency remediation,
- website visual QA,
- SEO article pipeline,
- VPS health check,
- product QA before release.

### Learning boundary

Learning occurs only after mission completion **and reviewer approval**.

Unsafe learned procedures involving production writes, protected branches, destructive actions, credentials or other high-risk work stay draft until appropriate approval.

A failed/rejected mission must not silently become an approved skill.

Hufi may say “gelernt” only when a real persistent Memory/Skill event exists.

---

## 10. No-LLM automation

Many routine checks should not call any model at all.

Examples:

- HTTP 200 check,
- disk usage,
- SSL expiry,
- backup existence,
- service status,
- Git state,
- file existence,
- scheduled structured health collection.

Pattern:

```text
deterministic check
  -> normal? persist result + evidence, model_calls = 0
  -> anomaly? local Qwen analyses
  -> still unclear/high impact? review/remote model if policy + budget allow
```

This is a key 20:80, security and cost-control mechanism.

---

## 11. Visible Work / Work Evidence — binding

Hufi must not be a black box for normal users.

Work Evidence is a separate user-facing trust layer derived from real mission/tool/review/artifact events.

Normal users may see:

- who is working,
- what is happening,
- real completed milestones,
- last safe evidence item/snapshot/file/test/diff/PR/report,
- next step,
- whether approval is required,
- final result.

### Transparency modes

- **Einfach** — milestones, approvals, result.
- **Transparent** — milestones plus sanitized evidence/artifacts.
- **Live** — real browser/computer/terminal view only when a real session exists.

Never fabricate:

- progress,
- snapshots,
- live computer state,
- success.

Work Evidence must be sanitized before display/storage. Secrets, tokens, passwords, `.env` contents, Authorization headers, cookies, private keys and credential-bearing URLs must not appear unmasked.

Canonical specs:

- `docs/product/VISIBLE-WORK.md`
- `docs/product/ORG-CANVAS-WORK-EVIDENCE.md`

---

## 12. Digital Company / Org-Canvas — binding target

HufiAgents should become a visual operating surface for a real digital company.

The structure is a **typed graph, not a rigid org-chart tree**.

### First-class nodes

- Owner/Human,
- Agent,
- Team,
- Project,
- Resource,
- ChatRoom.

### Core relationship types

- `reports_to`,
- `member_of_team`,
- `works_on_project`,
- `responsible_for_resource`,
- `may_use_resource`.

An agent may belong to multiple teams/projects at once.

Drag & drop changes relationships; it does not clone agent identity and it must never silently raise capability/risk/credential rights.

### Product surfaces

- Agent cards with picture/avatar, name, role, real status,
- Team cards,
- Project cards,
- Resource/repository cards,
- Organisation view,
- Teams view,
- Projects view,
- Resources view,
- List/mobile view,
- Agent chat,
- Team chat,
- Project chat,
- Company chat.

Canonical spec:

- `docs/product/ORG-CANVAS.md`

---

## 13. Credential / Secret capability — binding target

Hufi must never instruct a normal user to paste a password/token into ordinary chat.

Required product/security contract:

- dedicated masked secret field,
- optional temporary reveal,
- raw value not redisplayed after save,
- credential storage separate from chat/Memory/Skills/Audit/Work Evidence/results,
- normal GET APIs never return full raw values,
- connector/resource records reference credential handles/IDs,
- agents receive scoped connector capability rather than plaintext by default,
- replacement/revocation supported,
- likely token pasted into normal chat can be intercepted before send and offered for secure storage,
- if safe encryption-at-rest is unavailable, fail closed rather than invent weak crypto.

This is a prerequisite for broad safe connector usage (GitHub, Google, SMTP, Supabase, APIs, etc.).

---

## 14. Target roadmap

### V1.1.x — shipped and frozen

`v1.1.2` is the current production baseline.

Only real bug/security fixes belong on this line.

### V1.2 — Hufi learns, proves work and becomes a digital company

**Theme:** Learning / Efficiency / Visible Work / Company Graph / Credentials.

#### Codex track — engine/backend

Build:

- Work Evidence persistence + APIs,
- redaction/sanitation,
- Company Graph backend,
- teams/projects/resources/relationships,
- chat-room context,
- Skill Engine,
- procedural/project/agent/mission/shared memory boundaries,
- Progressive Context Loader,
- Learning Loop after successful reviewed missions,
- skill versioning/review,
- Cost Governor,
- local-first quality escalation,
- No-LLM routines,
- context compaction/caching,
- Credential Foundation,
- real work-summary service,
- additive migrations,
- API contract in `docs/implementation/V1_2_API_CONTRACT.md`.

#### Claude Code track — product/frontend

Build:

- Org-Canvas,
- agent/team/project/resource cards,
- repo/resource grid,
- drag & drop + accessible alternatives,
- organisation/teams/projects/resources/list views,
- agent/team/project/company chats,
- Visible Work/evidence cards,
- `Einfach / Transparent / Live`,
- credential/token UX,
- desktop/tablet/mobile/accessibility/browser QA.

#### V1.2 success proof

Before release:

- V1.1.2 data survives additive migration on a production-shaped DB copy,
- real local-Qwen mission generates real Work Evidence,
- controlled fake-secret evidence is redacted,
- second similar mission demonstrates actual Skill/Memory reuse,
- healthy deterministic routine proves `model_calls = 0`,
- team/project/resource/room relationships persist and reload,
- frontend consumes real APIs without fake product states,
- full tests/lint/compile + real browser QA pass.

### V1.3 — Hufi gets hands

**Theme:** Persistent Computer / Browser / Tools.

Build:

- persistent per-agent workspace,
- real browser automation,
- retained browser session where safe,
- controlled file interaction,
- computer/session lifecycle,
- real screenshots/artifacts,
- optional live preview,
- user handoff,
- reset/snapshot/recovery,
- MCP tool adapter,
- connector permission scopes.

Success test:

> Pascal can ask a Hufi to inspect a real web app, interact with it, capture sanitized evidence and return a reviewed result without manually driving the browser.

### V1.4 — Hufi is always available

**Theme:** Gateway / Events / Devices / Channels.

Build selectively:

- Hufi Gateway,
- notifications,
- voice entry points,
- device/node concept,
- selected messaging channels,
- event triggers,
- channel-independent mission identity,
- always-on routines/watchers.

Do not add channels just for feature count. Add them when they remove real friction.

### V1.5 — Product Capability Layer

**Theme:** reuse the engine in real Hufi products.

Build stable internal interfaces so Hufi Manager and HufiApp can consume:

- chat/mission API,
- selected skills,
- project/business memory,
- routines,
- Work Evidence,
- approvals,
- connectors/resources,
- credential handles,
- notifications,
- model/cost policy.

Success test:

> A Hufi capability is implemented once and used from at least two product surfaces without duplicating the orchestration core.

### V2 — AgentHufi / HufiApp Pro

Only after the internal engine is stable and useful:

- public agent teams,
- user-created agents,
- product-safe computer/browser,
- tenant-scoped memory,
- usage budgets,
- onboarding,
- billing when commercially required.

### Later — HufiCloud

Composable AI environment / builder.

Do not let HufiCloud design slow down the internal 1:99 engine today.

---

## 15. Capability status map

Legend:

- **LIVE** — proven/current production capability.
- **FOUNDATION** — real interfaces/abstractions exist, full user-ready capability is not complete.
- **ACTIVE** — V1.2 implementation is underway/planned in the current development track.
- **PLANNED** — later target, not current production.

| Capability | Status | Notes |
|---|---|---|
| Mission/Task engine | LIVE | production core |
| Local Qwen routing | LIVE | HUFI Local AI Router |
| Review/Retry | LIVE | real acceptance evidence |
| Crash recovery | LIVE | heartbeat/requeue proven |
| Approval engine | LIVE | human-language V1.1 flow + policy core |
| Audit | LIVE | persistent technical evidence |
| Bubblewrap isolation | LIVE | hardened execution boundary |
| Chat-first UI | LIVE | V1.1.2 |
| Dynamic agents | LIVE | persistent create/archive |
| Agent messaging | LIVE | durable/audited |
| Delegation | LIVE | bounded by privilege/policy |
| Fan-out/Fan-in | LIVE | team execution foundation |
| Routines | LIVE | API/UI + lifecycle |
| Workspace/session | FOUNDATION | controlled abstraction |
| Connector registry | FOUNDATION | descriptor/permissions foundation |
| Work Evidence | ACTIVE | V1.2 |
| Company Graph | ACTIVE | V1.2 |
| Teams/projects/relationships | ACTIVE | V1.2 |
| Chat Rooms | ACTIVE | V1.2 context layer |
| Resources/repo cards backend | ACTIVE | V1.2 |
| Skills Engine | ACTIVE | V1.2 |
| Scoped Memory | ACTIVE | V1.2 |
| Learning Loop | ACTIVE | V1.2 |
| Progressive Context | ACTIVE | V1.2 |
| Cost Governor | ACTIVE | V1.2 |
| No-LLM routines | ACTIVE | V1.2 |
| Credential Foundation | ACTIVE | V1.2 |
| Persistent browser | PLANNED | V1.3 |
| Persistent computer | PLANNED | V1.3 |
| MCP adapter | PLANNED | V1.3 |
| Gateway/channels | PLANNED | V1.4 |
| Product capability API | PLANNED | V1.5 |
| Multi-tenant SaaS | LATER | not an internal blocker |

---

## 16. Current execution order

V1.1 is shipped. Work now proceeds in parallel.

### Codex

1. Work Evidence + redaction.
2. Company Graph + teams/projects/resources/relationships/rooms.
3. Skills + Memory + Progressive Context + Learning Loop.
4. Cost Governor + No-LLM routines.
5. Credential Foundation.
6. API contract + targeted tests.
7. Real XXL validation on a production-shaped DB copy.

### Claude Code

1. Org-Canvas and graph interaction.
2. Agent/team/project/resource/repo cards.
3. Chat-room UX.
4. Visible Work/evidence surfaces.
5. Secret/token UX.
6. Responsive/mobile/accessibility/browser QA.
7. Wire real Codex APIs as the contract stabilizes.

### Integration/release

1. Reconcile API contract.
2. Integrate backend + frontend branches.
3. Migration/data-preservation proof.
4. Real Qwen + reuse + zero-LLM + redaction proofs.
5. Full suite/lint/compile.
6. Real browser QA.
7. Security review.
8. Production DB backup.
9. Controlled deploy.
10. Production smoke test and release documentation.

---

## 17. Anti-goals

Do **not** optimise for:

- maximum agent count,
- maximum model calls,
- copying every feature from Grok Bot/Hermes/OpenClaw,
- dozens of messaging channels now,
- premature SaaS billing/admin work,
- microservice complexity without proven need,
- technical dashboards as the normal UX,
- autonomous core self-modification without review/approval,
- fake visual activity merely to make the product look busy.

Optimise for:

- completed work,
- minimal human coordination,
- reliability,
- understandable UX,
- visible proof/trust,
- reuse across products,
- local-first economics,
- measurable business value.

---

## 18. Success metrics for the 1:99 system

Track:

- % missions completed without Pascal intervention,
- number of manual coordination steps removed,
- useful output per instruction,
- time from instruction to reviewed result,
- retry/recovery success rate,
- repeat-work efficiency gain after a skill exists,
- context/model-call reduction on known workflows,
- local vs remote model share,
- external AI cost per useful result,
- number of deterministic/no-LLM routine executions,
- Work Evidence truthfulness/redaction failures,
- number of capabilities reused across products,
- product errors caused by agent actions,
- number of times Pascal had to open technical details.

Ultimate test:

> Pascal states a business goal; HufiBoss and HufiAgents organise the digital workforce, complete the safe work, show understandable evidence, learn from reviewed success, ask only for real decisions and report the result in language a 10-year-old can understand.

---

## 19. Canonical references

- `docs/HUFIAGENTS-PRODUCT-VISION.md`
- `docs/HUFIAGENTS-CAPABILITY-MAP.md`
- `docs/ROADMAP.md`
- `docs/OPERATING_MODEL.md`
- `docs/SECURITY.md`
- `docs/EVALUATION.md`
- `docs/product/VISIBLE-WORK.md`
- `docs/product/ORG-CANVAS.md`
- `docs/product/ORG-CANVAS-WORK-EVIDENCE.md`
- `docs/implementation/V1_2_API_CONTRACT.md` — current V1.2 implementation contract when created/updated by Codex.
