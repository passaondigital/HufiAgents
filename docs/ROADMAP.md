# HufiAgents Roadmap

## Phase 0 — Inventory and bootstrap

- Read-only XXL audit. **Done** — see `docs/XXL-AUDIT.md` (2026-09-07).
  Key findings that shape every later phase: host is memory-constrained (not
  CPU/disk-constrained); no Ollama installed — real local inference is
  llama.cpp + the existing `hufi-local-ai-router` at `127.0.0.1:8090`
  (ADR-003); Hermes/HufiLab/Supabase are live production dependencies and
  must not be touched; no native Postgres/Redis service exists.
- Identify existing Hermes/OpenClaw/Ollama/Qwen/HufiBoss components. **Done**
  — see `docs/XXL-AUDIT.md` "Existing AI/agent components".
- Record running services, ports and resource use. **Done.**
- Establish repo structure, CI, dev commands and safe secret handling.
  **Open — Codex, see `docs/HANDOFF-CODEX-V1.md`.**

**Exit:** `docs/XXL-AUDIT.md` exists (done) and a reproducible development
stack starts without disturbing existing services (open, Codex).

## Phase 1 — Autonomous core MVP

Architecture is now binding, not exploratory — see `docs/ARCHITECTURE.md`
§§1-13 and `docs/HANDOFF-CODEX-V1.md` for exact contracts, schemas and file
layout. Build order matters; follow it so every step stays testable without
a live model call:

1. Repo bootstrap (package layout, `pyproject.toml`, lint/test commands, CI
   using only the `fake` provider).
2. Persistence layer: SQLite + repository interface + `schema_migrations`
   (ADR-002).
3. Core contracts as Pydantic models + tables: Mission, Task, Agent, Handoff,
   ToolCall, ToolResult, ReviewResult, ApprovalRequest, AuditEvent
   (`docs/ARCHITECTURE.md` §3).
4. Task state machine + transition rules (`docs/ARCHITECTURE.md` §4),
   unit-tested independent of any real tool/model call.
5. Model Router: `fake` provider first (unblocks CI), then the
   `hufi-local-router` adapter against `127.0.0.1:8090` (ADR-003).
6. Files/shell/git tools in an isolated workspace directory (ADR-005),
   Risk/Approval Engine (`docs/ARCHITECTURE.md` §8) wired in before any tool
   can execute a side effect.
7. Audit log (append-only, §3.8) and reviewer agent (§10, ADR-006 — reviewer
   pass mandatory even on trivial tasks).
8. Recovery: heartbeat + reaper + idempotency (`docs/ARCHITECTURE.md` §7),
   proven by killing the process mid-task and restarting it.

**Exit:** green end-to-end test for Mission -> Task -> Agent -> Tool ->
Review -> Persisted Result, using the `fake` provider in CI, plus one manual
run against the live `hufi-local-router`. State survives a process restart
(§7 restart recovery proof).

## Phase 2 — Coding workforce

- Git worktree/branch automation.
- Builder + reviewer agents.
- Test/CI integration.
- GitHub PR workflow.
- HufManager as first real project connector/use case.

**Exit:** HufiAgents can complete a bounded real repository task and prepare a verified PR.

## Phase 3 — Browser and infrastructure operations

- Playwright browser worker. **Resource note:** a Chromium worker is
  memory-heavy; per `docs/XXL-AUDIT.md` this must not launch by default
  alongside the model workers without a fresh headroom check (`free -h`)
  and a bounded concurrency limit (1 browser context at a time for V1).
- SSH tool with least-privilege policy (`docs/ARCHITECTURE.md` §6.5) — hard
  R3/R4 for any host-level sshd/firewall/root action, never auto-allow
  regardless of config (ADR pattern from ADR-006: structural, not optional).
- Scheduled missions.
- Credential handling and redaction.
- Recoverable sessions.

**Exit:** safe browser and server tasks can be executed and audited with approval gates.

## Phase 4 — Agent teams

- Chief -> Project Lead -> Specialists.
- Agent-to-agent handoffs.
- Parallel execution with resource budgets.
- Shared project knowledge with isolation.
- Cost/model routing.

**Exit:** at least two specialist agents can collaborate on one mission with independent review.

## Phase 5 — Grok Bot benchmark

Run comparable missions through official Grok Bot and HufiAgents. Measure:

- success rate,
- elapsed time,
- human interventions,
- recovery,
- output quality,
- cost,
- security/policy violations.

Close the highest-value gaps rather than chasing cosmetic 1:1 similarity.

## Business guardrail

HufiAgents work must not become another endless meta-project. Once the coding workforce is capable enough, HufManager becomes the first production mission and remains a top priority.
