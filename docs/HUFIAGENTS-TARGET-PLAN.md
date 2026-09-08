# HufiAgents — Target Plan, 1:99 Operating Model and Roadmap

**Status:** binding target plan / living roadmap  
**Date:** 2026-09-08  
**Production today:** `v1.0.1` at `https://agents.heyhufi.com`  
**Integrated V1.1 candidate:** PR #14 (`codex/v1x-final-integration`) — not yet production  
**Product QA:** PR #15 (`claude/product-qa-v1x`) plus follow-up release-product fixes

---

## 1. North Star

HufiAgents exists so Pascal can state a goal once and receive finished, reviewed work instead of coordinating tools, terminals, models and agents manually.

The target is not “many AI tools”. The target is a **digital company**.

```text
Pascal
  -> HufiBoss
      -> HufiAgents
          -> Project Leads
              -> Specialists
              -> Reviewers
              -> Tools / Computer / Browser
              -> Skills / Memory / Routines
```

**HufiBoss** is Pascal’s private master/co-CEO layer.  
**HufiAgents** is the reusable workforce engine underneath.  
Everything below HufiBoss can be treated as digital employees, teams, skills, tools and autonomous routines.

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

- Chat is the primary control surface.
- One clear primary action per screen/state.
- Normal language before system language.
- Technical details only behind **Details / System / Expert**.
- No raw UUIDs, internal agent IDs or R0–R4 codes in the normal flow.
- Approvals explain consequences, not internal policy codes.
- Errors always provide a next action.
- Repeating work is expressed conversationally (“every Monday at 8”).
- Agent creation asks only for human concepts: name + responsibility; advanced capabilities are optional.
- Mobile, tablet and desktop are equal product surfaces.
- Accessibility is a product requirement, not a polish task.
- Defaults must be safe and useful; configuration is progressive disclosure.

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
- form a team,
- split work,
- implement safe fixes,
- test,
- review,
- retry,
- create reports/branches/PRs,
- prepare marketing/SEO follow-ups,
- schedule recurring checks,
- ask Pascal only for genuinely important decisions.

### 20:80

Build the capabilities that remove the most human coordination first:

1. reliable autonomous execution,
2. simple UX,
3. learning/skills/memory,
4. routines,
5. computer/browser,
6. high-value connectors,
7. product integration.

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

HufiAgents is built internally first. Later the same capabilities can power Hufi Manager, HufiApp, AgentHufi and HufiCloud and therefore create revenue without rebuilding the engine four times.

---

## 4. Internal first, reusable everywhere

HufiAgents is **not primarily a SaaS today**. It is Pascal’s own operating system for digital work.

However, every major capability should be designed as reusable infrastructure rather than hard-coded into one screen.

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
Routines
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
- surface only decisions and relevant blockers,
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
- approvals,
- audit/recovery,
- later computer/browser and gateway.

### Hufi Manager

Consumes only the capabilities needed for a business-management product, e.g.:

- Hufi chat,
- CRM/task agents,
- schedules/routines,
- communication,
- documents,
- project/business memory,
- selected connectors.

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
- simple actions.

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
- approvals/review.

### HufiCloud

Later composition/builder platform:

- agents,
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

## 6. Reconciliation: what already exists vs. target

### Production V1.0.1 — real today

Already proven in production:

- login-gated web service,
- FastAPI + SQLite core,
- local HUFI AI Router,
- real Qwen execution,
- mission/task lifecycle,
- review and retry,
- crash/stale-heartbeat recovery,
- R3 approval fail-closed path,
- audit,
- HufManager connector,
- Bubblewrap isolation,
- systemd/Nginx/HTTPS deployment.

This foundation remains valid.

### V1.1 integrated candidate — PR #14

The integrated candidate adds/combines:

- chat-first UI,
- sidebar + contextual right pane,
- dynamic agent persistence,
- real `POST /agents`,
- agent messaging,
- delegation,
- fan-out/fan-in,
- routines API/UI,
- workspace/session foundations,
- connector registry,
- HufManager team mission,
- local-Qwen team execution,
- human-language approval/result surfaces.

XXL validation already recorded on the PR branch:

- migrations `[1,2] -> [1,2,3,4]`,
- existing mission/audit data preserved,
- **273 tests passed** on the actual XXL host,
- Bubblewrap passed,
- loopback passed,
- TestClient/lifespan passed,
- auth passed,
- same-origin write passed,
- foreign-origin write blocked,
- real local Qwen HufManager team mission completed,
- dynamic agent lifecycle and routine lifecycle exercised.

### Product QA — PR #15

Independent product QA added:

- design system,
- UX-language rules,
- user flows,
- 100+ acceptance checks,
- Grok-style behavior benchmark,
- multi-breakpoint browser testing,
- accessibility/focus/contrast fixes.

Three important product gates were identified and must be closed before declaring the integrated release finished:

1. conversational routine recognition,
2. refusal/failure must never be rendered as green success,
3. normal chat must be able to reach approval policy without a hard-coded R1 ceiling blocking it.

### Honest current gap

The computer/browser layer is still a **foundation**, not yet the persistent per-agent desktop experience seen in Grok Bot-style systems.

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

Do not rebuild all of OpenClaw/Hermes. Extract only capabilities that improve Hufi’s 1:99 outcome.

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

Local agents are constrained mostly by hardware/time, not per-call API cost. Remote models must therefore be governed economically.

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

Target principle:

> Use the cheapest capability that can reliably finish the job.

---

## 9. Learning architecture — the next leverage layer

HufiAgents becomes much more valuable when successful work becomes reusable.

```text
Mission
  -> execution
      -> review
          -> successful pattern?
              -> save/improve skill
                  -> reuse next time
```

### Memory layers

1. **HufiBoss memory** — strategic/company context.
2. **Project memory** — repo/product-specific facts and decisions.
3. **Agent memory** — role-specific context.
4. **Procedural skills** — how to perform recurring work.
5. **Run history/audit** — what actually happened.

Memory must stay scoped; agents should not receive the entire company history for every task.

### Skill rule

A skill should contain reusable procedure, not a dump of chat history.

Examples:

- HufManager release check,
- safe dependency remediation,
- website visual QA,
- SEO article pipeline,
- VPS health check,
- product QA before release.

### Self-improvement boundary

Hufi may propose and improve skills automatically within policy.

Core/security-sensitive code changes still require:

- branch,
- tests,
- review,
- appropriate approval before production.

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
- scheduled file/report collection.

Pattern:

```text
deterministic check
  -> normal? store quietly
  -> anomaly? local Qwen analyses
  -> still unclear/high impact? remote model if budget allows
```

This is a key 20:80 and cost-control mechanism.

---

## 11. Target roadmap

### Release Gate — V1.1.0

**Goal:** ship the integrated workforce + chat experience safely.

Must be true:

- PR #14 integrated and validated,
- three product-gate findings closed,
- real browser/responsive pass on integrated state,
- no false-success rendering,
- conversational routines work,
- approvals reachable from normal chat policy,
- CI/full suite green,
- production DB backed up before deploy,
- V1.0.1 -> V1.1 migration safe,
- production smoke test passes.

### V1.2 — Hufi learns and spends intelligently

**Theme:** Learning / Skills / Memory / Efficiency.

Build:

- Skill Engine,
- procedural memory,
- project memory,
- per-agent memory boundaries,
- progressive context loading,
- learning loop after successful reviewed missions,
- skill versioning/review,
- Cost Governor,
- local-first quality escalation,
- no-LLM routines,
- context compaction/caching,
- simple “why this model?” audit details.

Success test:

> Repeating a known HufManager workflow requires less context, fewer model calls and less human coordination than the first run.

### V1.3 — Hufi gets hands

**Theme:** Persistent Computer / Browser / Tools.

Build:

- persistent per-agent workspace,
- real browser automation,
- retained browser session where safe,
- controlled file interaction,
- computer/session lifecycle,
- optional live preview,
- screenshots/artifacts,
- user handoff,
- reset/snapshot/recovery,
- MCP tool adapter,
- connector permission scopes.

Success test:

> Pascal can ask a Hufi to inspect a real web app, interact with it, capture evidence and return a reviewed result without manually driving the browser.

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
- approvals,
- connectors,
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

## 12. Capability status map

Legend:

- **LIVE** — proven in production V1.0.1.
- **CANDIDATE** — integrated in PR #14 / validated on staging but not production yet.
- **QA** — product-level QA work exists but final integration may still be pending.
- **FOUNDATION** — interfaces/abstractions exist, user-ready capability does not.
- **PLANNED** — target, not implemented.

| Capability | Status | Notes |
|---|---|---|
| Mission/Task engine | LIVE | Core proven |
| Local Qwen routing | LIVE | HUFI Local AI Router |
| Review/Retry | LIVE | real acceptance evidence |
| Crash recovery | LIVE | heartbeat/requeue proven |
| Approval engine | LIVE | R3 fail-closed proven; V1.1 chat reachability gate remains |
| Audit | LIVE | persistent/user-readable foundation |
| Bubblewrap isolation | LIVE | host validation passed |
| Chat-first UI | CANDIDATE/QA | PR #14 + QA work |
| Dynamic agents | CANDIDATE | persistent create/archive |
| Agent messaging | CANDIDATE | durable/audited |
| Delegation | CANDIDATE | bounded by parent privileges |
| Fan-out/Fan-in | CANDIDATE | HufManager team benchmark |
| Routines | CANDIDATE | API/UI + lifecycle validated |
| Workspace/session | FOUNDATION | persistent controlled abstraction |
| Connector registry | FOUNDATION | GitHub descriptor/permissions foundation |
| Persistent browser | PLANNED | V1.3 |
| Persistent computer | PLANNED | V1.3 |
| Skills Engine | PLANNED | V1.2 |
| Procedural memory | PLANNED | V1.2 |
| Learning loop | PLANNED | V1.2 |
| Progressive context | PLANNED | V1.2 |
| Cost Governor | PLANNED | V1.2, before serious API scale |
| No-LLM routines | PLANNED | V1.2 |
| MCP adapter | PLANNED | V1.3 |
| Gateway/channels | PLANNED | V1.4 |
| Product capability API | PLANNED | V1.5 |
| Multi-tenant SaaS | LATER | not an internal blocker |

---

## 13. Immediate execution order

Do not start V1.2 before V1.1 is actually shipped.

### Now

1. Finish the Claude release-product fixes against PR #14.
2. Validate the integrated browser experience.
3. Run affected targeted tests and one final full suite.
4. Merge PR #14 only when all release gates are green.
5. Backup production DB.
6. Deploy V1.1.0.
7. Smoke-test `agents.heyhufi.com`.
8. Close superseded PRs cleanly.

### Immediately after V1.1

Freeze V1.1 except bug/security fixes and start V1.2 in this order:

1. Memory model and scope boundaries.
2. Skill format + Skill Registry.
3. Learning loop after reviewed success.
4. Progressive context loader.
5. Cost Governor.
6. No-LLM routines.
7. Measure one repeated HufManager workflow before/after.

### After V1.2 proves leverage

Start V1.3 persistent browser/computer work.

---

## 14. Anti-goals

Do **not** optimise for:

- maximum agent count,
- maximum model calls,
- copying every feature from Grok Bot/Hermes/OpenClaw,
- dozens of messaging channels now,
- premature SaaS billing/admin work,
- microservice complexity without proven need,
- technical dashboards as the normal UX,
- autonomous core self-modification without review/approval.

Optimise for:

- completed work,
- minimal human coordination,
- reliability,
- understandable UX,
- reuse across products,
- local-first economics,
- measurable business value.

---

## 15. Success metrics for the 1:99 system

Track:

- % missions completed without Pascal intervention,
- number of manual coordination steps removed,
- useful output per instruction,
- time from instruction to reviewed result,
- retry/recovery success rate,
- repeat-work efficiency gain after a skill exists,
- local vs remote model share,
- external AI cost per useful result,
- number of deterministic/no-LLM routine executions,
- number of capabilities reused across products,
- product errors caused by agent actions,
- number of times Pascal had to open technical details.

Ultimate test:

> Pascal states a business goal; HufiBoss and HufiAgents organise the digital workforce, complete the safe work, ask only for real decisions and report the result in language a 10-year-old can understand.

That is the target.