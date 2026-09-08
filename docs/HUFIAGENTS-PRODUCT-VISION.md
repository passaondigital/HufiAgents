# HufiAgents — Product Vision, V1.0.1 State and Target Experience

**Status:** living product/architecture document  
**Date:** 2026-09-07  
**Current production release:** `v1.0.1`  
**Production URL:** https://agents.heyhufi.com

## 1. Why HufiAgents exists

HufiAgents exists to remove Pascal from the role of human message bus between AI tools, repositories, servers, terminals and project sessions.

The intended interaction is outcome-first:

> Bring HufManager to a production-ready and sellable state.

HufiAgents should turn that outcome into the complete work loop:

1. inspect the project,
2. plan the mission,
3. decompose it into tasks,
4. assign or create specialist agents,
5. route tasks to suitable models,
6. execute tools inside bounded workspaces,
7. test and review results,
8. retry or recover from failures,
9. stop only for genuinely risky approvals,
10. prepare code/PR/report artifacts,
11. preserve an audit trail,
12. report finished results and real blockers in plain language.

The product is not meant to expose orchestration complexity to the user. The user should give goals; HufiAgents should coordinate the workforce.

## 2. Product model

```text
Pascal / User
  -> HufiBoss / Hufi Chief
      -> Mission Planner / Orchestrator
          -> Project Lead
              -> Builder
              -> Researcher
              -> Infrastructure
              -> Browser / Computer
              -> Security
          -> Reviewer / Master Audit
      -> Model Router
      -> Tool Layer
      -> Memory / Knowledge
      -> Approval Engine
      -> Audit / Recovery
```

The mental model is a **digital company**, not a collection of chat windows.

- **Pascal** — owner, decision-maker, idea source.
- **HufiBoss** — Pascal's private master/co-CEO layer.
- **HufiAgents** — the workforce/orchestration engine.
- **Hufi Chief** — operational lead for missions.
- **Project Lead** — owns one project or mission.
- **Specialists** — builders, reviewers, security, infrastructure, browser agents, etc.
- **Master Audit** — independent quality gate.

## 3. Position inside the Hufi ecosystem

### HufiBoss

Private master instance for Pascal only. HufiBoss is the personal Jarvis/co-CEO/second-brain layer and is not the public product name.

### HufiAgents

The technical multi-agent workforce layer behind autonomous mission execution, model routing, tool use, review, recovery, approval and audit.

### HufiApp

Public end-user assistant. Target: **Jarvis level** — natural chat/voice, memory, files, calendar, communication, proactive assistance, routines and simple actions. Normal users should not need to know what an orchestrator, provider or risk ceiling is.

### HufiApp Pro / AgentHufi

Jarvis level plus autonomous agent capabilities: specialist creation, delegation, parallel work, browser/computer use, connectors, review and result aggregation.

### HufiCloud

Possible future composition layer where users build their own AI environment from agents, models, skills, connectors, data, memory, computers, routines and workflows.

## 4. Product principles

1. Results before tooling.
2. Outcome language before terminal language.
3. Local-first where sensible.
4. Model-agnostic by design.
5. External models are optional capabilities, never structural dependencies.
6. High autonomy with hard safety boundaries.
7. Approval only for actions that genuinely matter.
8. Every important action is auditable.
9. Failures should trigger recovery before human escalation.
10. Existing production systems must not be disrupted by experimentation.
11. Business projects such as HufManager remain higher priority than endless meta-development.
12. Backend complexity must not leak into the normal UI.
13. Self-hosted/open-source components are preferred where they make economic sense.

## 5. Current production state — V1.0.1

The V1 core is real and deployed.

### Production surface

- login-gated web service,
- Dashboard,
- Mission creation,
- Mission detail,
- Agents,
- Projects,
- Models,
- Approvals,
- Audit,
- System status,
- HTTPS at `agents.heyhufi.com`,
- dedicated systemd service/user,
- Nginx reverse proxy,
- SQLite persistence.

### Real execution path

```text
Mission
 -> Planning
 -> Task
 -> Agent
 -> Local Model / Tool
 -> Review
 -> Retry / Recovery when needed
 -> Approval when risky
 -> Result
 -> Audit
```

### V1 acceptance evidence

The live V1 release proved:

- real local Qwen execution via the HUFI Local AI Router,
- real HufManager clone and read-only project analysis,
- real reviewer pass,
- retry after failed acceptance criteria,
- hard-crash recovery after `kill -9`,
- stale-heartbeat requeue and successful completion,
- R3 approval block with `execution_started: false`,
- browser-session Deny path,
- readable audit timeline,
- persistence across service restart.

The final handoff reported `261/261` tests green and CI green on `main`.

### V1.0.1 hotfix

`v1.0.0` exposed a real-browser login defect: the request boundary treated every request carrying an `Origin` header as cross-origin. Modern same-origin browser writes also carry `Origin`, so legitimate browser login requests were rejected although curl/TestClient checks passed.

The fix compares `Origin` host against the request `Host`, preserves blocking of genuinely cross-origin writes, adds regression coverage and ships as `v1.0.1`.

## 6. Current local model stack

HufiAgents must use the existing HUFI Local AI Router instead of installing a second inference stack.

```text
http://127.0.0.1:8090/v1
```

Current aliases:

- `hufi-qwen9`
- `hufi-qwen9-fast`
- `hufi-gemma`

The product UI currently reports `hufi-local-router` as the healthy real provider and correctly reports unavailable providers as unhealthy instead of hiding them.

Model strategy:

- **Qwen Fast** — low-latency routine work.
- **Qwen** — more demanding local reasoning.
- **Gemma** — secondary/failover or task-specific alternative.
- **Remote providers** — future optional adapters when quality/capability justifies them.

Routing decisions should eventually consider complexity, privacy, health, latency, cost and context requirements and persist the selection reason for auditability.

## 7. Runtime architecture

V1 deliberately stays compact:

```text
FastAPI / UI
  -> in-process Orchestrator
      -> Task Engine
      -> Agent Registry
      -> Model Router
      -> Tool Gateway
      -> Risk / Approval Engine
      -> Reviewer
      -> Memory Layer
      -> Audit
      -> Persistence
```

Key constraints:

- single bounded Python process,
- asyncio concurrency,
- SQLite behind a persistence interface,
- default max task concurrency: 2,
- no Redis requirement,
- no additional always-on database daemon,
- no duplicate local model stack.

This is an implementation choice for the current host, not a long-term limit. Interfaces must allow later worker/service separation without rewriting orchestration semantics.

## 8. Mission and task lifecycle

Mission input is natural-language outcome intent.

Tasks carry bounded execution context including:

- objective,
- expected output,
- acceptance criteria,
- allowed tools,
- risk ceiling,
- provider hint,
- token/time budget,
- dependencies,
- retries,
- assigned agent,
- heartbeat,
- idempotency key.

Typical lifecycle:

```text
queued
 -> planning
 -> running
 -> review
 -> completed
```

Alternative states:

```text
waiting_approval
blocked
retrying
failed
cancelled
```

A successful task should not bypass review.

## 9. Agent model

V1 agents are primarily role/capability/policy entries loaded by the orchestrator, not necessarily permanent independent OS processes.

### Hufi Chief

- mission intake,
- prioritisation,
- decomposition,
- coordination,
- final human-facing result synthesis.

### Project Lead

- owns project context,
- delegates project work,
- manages dependencies and specialist results.

### Builder

- implementation,
- workspace file/code operations,
- bounded local execution.

### Integrator

- privileged Git/GitHub path,
- prepared pushes and PR creation,
- cannot silently cross risk boundaries.

### Reviewer / Master Audit

- independent verification,
- `approve`, `reject` or `revise`,
- must be able to send weak work back for correction.

### Security

- permissions,
- secret boundaries,
- high-risk execution policy,
- security review.

### Infrastructure / Browser / Computer

Future specialist surfaces for server, deployment, browser and GUI/computer workflows.

## 10. Dynamic agents are a target feature

The next product generation should allow agents to create bounded specialist agents on demand.

Desired flow:

```text
Hufi Chief
  -> creates Project Lead
      -> creates Builder
      -> creates Researcher
      -> creates Reviewer
      -> creates temporary specialist
```

Each dynamic agent should have:

- name,
- role/persona,
- capabilities,
- own chat/thread,
- scoped memory,
- bounded workspace/computer context,
- explicit risk ceiling,
- lifecycle/status,
- audit identity.

## 11. Security and sandboxing

Autonomy is only useful if the trust boundary remains structural.

Project-code execution is contained through Bubblewrap with the intended properties:

- isolated user/PID/network namespaces,
- no network by default for untrusted project scripts,
- private `/tmp` and `/proc`,
- only the mission workspace writable,
- no inherited HUFI secrets,
- no `.ssh` / `.config`,
- no `/srv`,
- no Docker socket,
- no systemd access,
- no foreign workspace access,
- fail closed when Bubblewrap is missing or fails.

Credential-bearing Git/GitHub execution is separated from project code and hardened for:

- parent SIGKILL,
- SIGTERM,
- cancellation,
- timeout,
- child/grandchild cleanup,
- no duplicate push after a success-then-crash ambiguity.

The askpass path uses a hash-verified secret-free source and a private runtime `0700` copy for the individual push so checkout umask behavior cannot silently expand executable authority.

## 12. Risk and approval model

Conceptual levels:

- **R0** — read-only / analysis.
- **R1** — local, reversible, bounded changes.
- **R2** — controlled shared effects.
- **R3** — important external/productive action.
- **R4** — destructive or highly sensitive action.

R3/R4 require approval.

The normal product UI should **not** force users to understand `R3` terminology. Approval cards should say in plain language:

- what Hufi wants to do,
- why it is needed,
- what changes,
- whether it can be reverted,
- which project/agent is involved.

Suggested user actions:

- Allow,
- Deny,
- optionally create a rule for similar safe actions.

## 13. Retry and recovery

HufiAgents should try to recover before asking the user to rescue it.

V1 already demonstrates:

- review-triggered revision/retry,
- process restart recovery,
- stale-heartbeat detection,
- safe task requeue,
- idempotency protection around side effects.

Future error classes should include:

- model error,
- tool error,
- dependency error,
- test/build failure,
- review failure,
- network failure,
- resource exhaustion,
- external service block.

The target policy is:

> try a safe correction, alternate path, retry or model/tool failover first; escalate only when human judgement is actually required.

## 14. Audit as user-readable history

The backend audit trail should capture:

- mission creation,
- task creation,
- state changes,
- agent assignment,
- model choice,
- tool calls,
- approvals,
- review,
- failures,
- retry,
- recovery,
- completion.

The default UI must translate this to a human timeline.

Example:

```text
22:44 Mission started
22:44 HufManager connected
22:45 Builder analysing repository
22:46 Qwen produced priorities
22:47 Reviewer requested revision
22:48 Builder corrected missing items
22:49 Reviewer approved
22:49 Mission completed
```

Raw event JSON and internal IDs belong under **Details**, not in the primary experience.

## 15. HufManager is the first real project benchmark

HufManager is intentionally the first real project connector and should remain the practical benchmark that keeps HufiAgents grounded in useful business outcomes.

Already validated:

- project registry,
- real clone,
- isolated branches,
- foreign-remote protections,
- local Qwen analysis,
- review,
- audit,
- secure push credential path,
- R3 push approval boundary.

The next value step is not more meta-documentation: it is safely completing real productive HufManager work through the agent workforce.

## 16. Grok Bot as product benchmark

Grok Bot is a reference for **observable behavior and product simplicity**, not a source to copy proprietary implementation from.

Observed/high-value product patterns:

- narrow left bot/chat sidebar,
- chat as the main surface,
- contextual right pane,
- simple new-bot flow,
- per-bot persona,
- per-bot chat,
- visible computer/desktop slot,
- persistent computer concept,
- routines per bot,
- plugin marketplace,
- bot/template marketplace,
- local computer integration,
- per-action local execution permission,
- natural-language Auto-Review rules,
- computer update/reset and snapshot/recovery concepts,
- usage/billing kept outside the main work surface.

A controlled test showed an existing bot creating a new `HufiLabTest` bot without Pascal manually clicking through creation. The new bot appeared with its own chat, persona and desktop slot. Dynamic agent creation is therefore a high-value target for HufiAgents/AgentHufi.

### Clean-room rule

HufiAgents should reproduce useful product capabilities using its own architecture and code. Benchmark behavior, UX and workflows; do not copy proprietary implementation.

## 17. Current V1 UI verdict

The V1 frontend proves functionality but is **not the target product experience**.

Current problems:

- too many primary navigation items,
- feels like an admin/developer dashboard,
- mission creation feels like a technical form,
- Models exposes provider internals too prominently,
- Projects behaves like configuration data instead of a user journey,
- Approvals are functionally correct but visually raw,
- Audit is valuable but too prominent for everyday use,
- system terminology competes with the actual result.

The backend can remain complex. The frontend must not be.

## 18. New UI mandate

The next frontend should feel:

> as simple as a good messenger, as polished as a premium consumer app, and as capable underneath as an autonomous agent platform.

### Left sidebar

- agents/bots,
- projects/teams when useful,
- search,
- new bot/team,
- optional Marketplace.

### Center

Chat is the primary control surface.

Core input:

> What should Hufi do?

The user should be able to type or speak normal goals.

Examples:

- “Check HufManager for everything blocking a sale.”
- “Fix the important items and ask before anything risky.”
- “Do this every Monday morning.”

### Right contextual pane

Only show what matters **now**:

- current bot,
- live computer,
- active mission,
- routine,
- approval,
- result,
- project context.

Do not permanently fill it with technical telemetry.

### Technical information

Keep available behind `Details`, `System` or an expert/admin mode:

- model provider,
- model health,
- failover counters,
- task IDs,
- tool calls,
- raw audit,
- token budgets,
- retry counters,
- logs,
- low-level system metrics.

## 19. Ideal user flow

User enters:

> Check HufManager for every problem preventing a clean sale.

Hufi responds:

> I’ll check HufManager with my team.

Compact progress:

```text
Repository checked
2 agents working
Review running
```

Optional: `Show details`.

Final result:

> Done. I found 3 critical, 5 important and 8 smaller items. I recommend fixing the 3 critical items first.

Primary actions:

- Fix them
- Open report
- Later

No mission UUID needs to be shown unless the user asks for details.

## 20. Agent UI target

Normal users should see an agent as:

- avatar/color,
- name,
- one-line role,
- current state,
- optional current project.

Example:

```text
Hufi Chief
Coordinates your projects
```

```text
HufManager Lead
Responsible for HufManager
```

```text
Reviewer
Independently checks results
```

Creation UX should be minimal:

- Name
- Avatar/color
- “What should this Hufi be responsible for?”

The system should derive policy/capability configuration unless an expert explicitly opens advanced settings.

## 21. Routines

Routines should be conversational.

User:

> Do this every Monday at 08:00.

Hufi:

> Routine created: HufManager weekly check — Monday 08:00.

The UI can expose:

- next run,
- active/paused,
- edit,
- delete,
- last result,
- failure state.

No cron syntax in normal product UX.

## 22. Connectors and marketplace

Potential connectors:

- GitHub,
- Gmail,
- Google Calendar,
- Google Drive,
- Slack,
- Notion,
- browser,
- CRM,
- accounting,
- maps/routes,
- weather,
- cameras/stall systems,
- custom MCP servers.

Potential marketplace categories:

- Horse / Stable,
- Office,
- Development,
- Marketing,
- Sales,
- Communication,
- Data & Analysis,
- Automation,
- Agent Teams.

Connector installation should feel like app installation, not server administration.

## 23. HufiCloud direction

HufiCloud is not finalised, but the strategic concept is a composable personal/company AI environment.

Possible building blocks:

- agents,
- teams,
- skills,
- models,
- connectors,
- data sources,
- memory,
- computers,
- routines,
- workflows,
- projects,
- dashboards.

The user should be able to express a goal such as:

> I want a stable-management assistant.

HufiCloud could then propose/build:

- Stable Manager,
- Weather Agent,
- Feed Agent,
- Camera Agent,
- Scheduling Agent.

## 24. SaaS is a later layer

The current instance is Pascal’s productive internal HufiAgents, not a complete SaaS.

A public SaaS will additionally need:

- multi-tenancy,
- user/org accounts,
- RBAC,
- tenant isolation,
- billing,
- usage/cost budgets,
- onboarding,
- admin tooling,
- privacy/contracts,
- off-host backup,
- monitoring/scaling,
- support operations,
- per-user connector/model credentials.

Do not let SaaS concerns block internal product value prematurely.

## 25. Success metrics

Measure usefulness, not feature count.

Useful metrics:

- missions completed without human intervention,
- time from instruction to useful result,
- number of unnecessary clarifying questions,
- recovery success rate,
- review failure/revision rate,
- useful PRs/reports/deployments produced,
- cost per mission,
- local vs remote model share,
- average number of agents used per mission,
- number of manual coordination steps removed from Pascal.

The central question:

> Does Pascal still have to babysit the workflow?

If yes, the system is not finished.

## 26. Near-term roadmap after V1.0.1

### V1.1 — product experience

- replace dashboard-first UX with chat-first UX,
- compact bot/project sidebar,
- contextual right pane,
- simple approval cards,
- advanced details hidden by default,
- modern transitions/microinteractions,
- responsive mobile/tablet layout,
- clearer results and status language.

### Dynamic agents

- agent creates agent,
- persona + scoped memory,
- own chat,
- own workspace/computer slot,
- agent-to-agent messaging,
- delegation,
- fan-out/fan-in,
- channels/team spaces.

### Routines

- schedule creation from chat,
- recurring execution,
- pause/edit/delete,
- notification and failure behavior,
- retry/recovery.

### Browser/computer

- persistent agent computer,
- browser automation,
- optional live preview,
- user handoff,
- local computer execution behind approval.

### Plugins/connectors

- production GitHub write path,
- Drive/Gmail/Calendar and other connectors,
- marketplace/permission model.

### AgentHufi / HufiApp Pro

Public agent product layer on top of the same workforce engine.

### HufiCloud

Composable user-owned AI workspace/platform.

## 27. Next working-session priorities

1. Freeze the functional V1 core unless a blocker requires changes.
2. Redesign the frontend around `sidebar + chat + contextual pane`.
3. Map existing Dashboard/Projects/Models/Approvals/Audit/System capabilities behind the new UX instead of deleting backend capability.
4. Design simple conversational approval cards.
5. Specify dynamic agent creation and bot-to-bot messaging using Grok Bot benchmark findings.
6. Specify routines and persistent agent workspaces.
7. Return to real HufManager productive missions as soon as the write/test path is ready.

## 28. One-sentence design brief

> HufiAgents should feel like an extremely simple personal messenger with a team of digital employees, while underneath it runs a secure, auditable and self-recovering multi-agent system.

## 29. Long-term definition of success

The long-term goal is a morning instruction like:

> Check HufManager today, fix everything sensible, ask before critical changes, and tell me this evening what is finished.

HufiAgents should then autonomously:

- form the team,
- analyse,
- plan,
- work,
- test,
- review,
- correct,
- document,
- report.

Without Pascal manually coordinating multiple terminals, model providers, repositories, server logs and agent sessions.

That is the actual finish line.
