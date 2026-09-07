# HufiAgents V1 Architecture

This is the binding V1 specification. It supersedes prose-level ambiguity: every
component below has an owner, a storage location, and a contract Codex can
implement directly. Where a decision was made instead of left open, the
rationale is in `docs/DECISIONS.md`; do not re-litigate it here — extend it via
a new ADR if reality proves it wrong.

This document assumes the findings in `docs/XXL-AUDIT.md`: memory-constrained
host, existing local model stack at `127.0.0.1:8090`, existing Hermes/HufiLab/
Supabase production dependencies that must not be touched.

## 0. Non-negotiable constraints from the audit

1. Single bounded process for V1 (API + in-process orchestrator). No new
   always-on database daemon, no Redis, no second local-model stack.
2. Default local model provider = existing `http://127.0.0.1:8090/v1`
   (HUFI Local AI Router). Do not install/manage Ollama.
3. SQLite is the V1 persistence engine. The persistence layer must be an
   interface, not `sqlite3` calls scattered through the codebase, so Postgres
   can replace it later without touching orchestration code.
4. Default task concurrency: 2 concurrent running tasks. Configurable, but the
   shipped default must respect host memory headroom.
5. Own workspace root, own Linux service account pattern
   (`hufirouter`/`hufilab` style: dedicated user, no sudo, no docker group
   unless a specific tool proves it needs it), bind to `127.0.0.1` only.

## 1. Component map

```text
Mission API (FastAPI, single process)
  -> Orchestrator (in-process, asyncio)
      -> Task Engine (state machine + persistence)
      -> Agent Registry (static + DB-backed capability table)
      -> Model Router (provider-neutral, local default = :8090)
      -> Tool Gateway (files, shell, git, GitHub, SSH, browser, MCP)
      -> Risk / Approval Engine (classify before execute)
      -> Reviewer (accept/reject/revise)
      -> Memory Layer (task/project/agent/global, read-only bridge to
         /srv/hufi/shared/knowledge)
      -> Audit Log (append-only, SQLite table, source of truth)
  -> CLI (thin client over the same API; V1 UI surface)
  -> Web UI (deferred; Phase 1 roadmap milestone 7, not V1 blocking)
```

Everything is one Python process for V1. Internal module boundaries below are
still enforced as real interfaces (ABCs/Protocols) so a later split into
separate services (worker pool, dashboard backend, etc.) is a deployment
change, not a rewrite.

## 2. Stack decision (binding for V1, see ADR-002)

- Language/runtime: Python 3.11+ (matches Hermes' pinned venv; host system
  Python is 3.14.4 — use a venv pinned to 3.11 or 3.12 for library maturity,
  do not depend on the system interpreter version).
- API: FastAPI + Uvicorn (single worker for V1; concurrency is inside the
  process via asyncio, not via multiple Uvicorn workers, to keep task state
  in one place).
- Persistence: SQLite via SQLAlchemy 2.0 Core (not the full ORM) behind a
  repository interface (`hufiagents/persistence/`). Plain, ordered `.sql`
  migration files applied idempotently at startup, tracked in a
  `schema_migrations` table. No Alembic dependency for V1.
- Task execution: in-process `asyncio` tasks drawn from a bounded
  `asyncio.Semaphore(settings.max_concurrent_tasks)` (default 2).
- HTTP client to model providers: `httpx` (async).
- CLI: `typer` or plain `argparse`, thin wrapper over the FastAPI app's own
  HTTP API (dogfood the API from day one).
- Tests: `pytest` + `pytest-asyncio`, no paid API required (deterministic
  fake provider is mandatory, see §5).

## 3. Core contracts

All contracts are persisted as SQLite tables and exposed as Pydantic models at
the API boundary. Field lists below are the minimum required set; adding
fields is fine, removing or renaming requires an ADR.

### 3.1 Mission

| field | type | notes |
|---|---|---|
| id | uuid | primary key |
| outcome | text | Pascal's outcome statement, verbatim |
| constraints | json | optional structured constraints |
| status | enum | mirrors task lifecycle at mission granularity: `queued, planning, running, waiting_approval, blocked, review, retrying, failed, completed, cancelled` |
| risk_ceiling | enum(R0-R4) | max risk class this mission may reach without new approval |
| created_at / updated_at / completed_at | timestamp | |
| requested_by | text | `pascal` or agent id for sub-missions |

### 3.2 Task

| field | type | notes |
|---|---|---|
| id | uuid | primary key |
| mission_id | uuid | FK |
| parent_task_id | uuid, nullable | for decomposed subtasks |
| objective | text | |
| context_refs | json | pointers into Memory Layer, not inlined blobs |
| expected_output | text | |
| acceptance_criteria | json | list of checkable statements |
| allowed_tools | json | explicit allowlist, never implicit "all tools" |
| risk_ceiling | enum(R0-R4) | must be <= mission.risk_ceiling |
| preferred_provider | text, nullable | provider id hint; router may override with reason |
| budget_tokens / budget_seconds | int, nullable | |
| retry_limit | int | default 2 |
| retry_count | int | |
| dependencies | json | list of task ids that must be `completed` first |
| status | enum | see §4 |
| assigned_agent_id | text, nullable | |
| idempotency_key | text | required before any side-effecting tool call, see §7 |
| heartbeat_at | timestamp, nullable | updated by the running executor |
| created_at / started_at / finished_at | timestamp | |

### 3.3 Agent (registry entry)

| field | type | notes |
|---|---|---|
| id | text | e.g. `builder`, `reviewer`, `infra`, `browser`, `security` |
| role | text | free-text role description |
| capabilities | json | tool ids + model preferences this agent may use |
| default_risk_ceiling | enum(R0-R4) | hard cap, independent of task risk_ceiling; effective ceiling = min(task, agent) |
| status | enum | `active`, `disabled` |

Agents are configuration + policy, not separate processes in V1. "Running an
agent" means: the orchestrator loads this row, builds a provider+tool context
scoped to `capabilities`, and executes one task.

### 3.4 Handoff

| field | type | notes |
|---|---|---|
| id | uuid | |
| from_agent_id / to_agent_id | text | |
| task_id | uuid | |
| summary | text | what was done, what remains |
| artifacts | json | file paths, PR URLs, branch names |
| created_at | timestamp | |

Cross-agent handoffs inside HufiAgents are DB rows, not files. The **human**
coordination protocol in `docs/HANDOFFS.md` (Codex <-> Claude Code) is a
separate, deliberately simple markdown log — do not conflate the two.

### 3.5 ToolCall / ToolResult

| field | type | notes |
|---|---|---|
| id | uuid | |
| task_id | uuid | |
| tool | text | `files`, `shell`, `git`, `github`, `ssh`, `browser`, `mcp:<server>` |
| action | text | e.g. `write_file`, `run_command`, `commit`, `open_pr` |
| target | text | path/host/repo — whatever "target" means for that tool |
| params | json | redact secrets before persisting, never store raw credentials |
| risk_class | enum(R0-R4) | computed by Risk Engine before execution |
| policy_decision | enum | `auto_allow`, `reviewer_gate`, `approval_required`, `denied` |
| idempotency_key | text | |
| requested_at / executed_at | timestamp | |
| result_status | enum | `ok`, `error`, `timeout`, `blocked` |
| result_summary | text | bounded length, redacted |
| exit_code | int, nullable | for shell/git |

### 3.6 ReviewResult

| field | type | notes |
|---|---|---|
| id | uuid | |
| task_id | uuid | |
| reviewer_agent_id | text | |
| verdict | enum | `approve`, `reject`, `revise` |
| findings | json | list of `{severity, summary, evidence}` |
| created_at | timestamp | |

### 3.7 ApprovalRequest

| field | type | notes |
|---|---|---|
| id | uuid | |
| task_id / tool_call_id | uuid, nullable | one of the two is set |
| risk_class | enum(R3, R4) | R0-R2 never create an ApprovalRequest |
| summary | text | human-readable, what will happen if approved |
| status | enum | `pending`, `approved`, `denied`, `expired` |
| requested_at | timestamp | |
| resolved_at | timestamp, nullable | |
| resolved_by | text, nullable | `pascal` |
| resolution_note | text, nullable | |

### 3.8 AuditEvent

| field | type | notes |
|---|---|---|
| id | uuid | |
| ts | timestamp | |
| actor | text | agent id or `system` |
| mission_id / task_id | uuid, nullable | |
| event_type | text | `state_transition`, `tool_call`, `approval_requested`, `approval_resolved`, `review`, `error`, `recovery` |
| detail | json | |
| append_only | — | enforced at the DB layer: no `UPDATE`/`DELETE` grants on this table from application code, insert-only repository method |

This table is HufiAgents' own append-only audit trail (see ADR-004 on why it
is not merged into `/srv/hufi/shared/knowledge/CHRONICLE.jsonl`).

## 4. Task lifecycle — states and transitions

States: `queued, planning, running, waiting_approval, blocked, review,
retrying, failed, completed, cancelled`.

```text
queued
  -> planning            (orchestrator picks it up)
planning
  -> running              (plan accepted, tools/model bound)
  -> blocked               (missing dependency / context)
  -> failed                 (cannot be planned, no retry warranted)
running
  -> waiting_approval    (Risk Engine returned approval_required)
  -> review                (tool execution finished, output produced)
  -> failed                 (unrecoverable tool/provider error, retries exhausted)
  -> retrying               (recoverable error, retry_count < retry_limit)
waiting_approval
  -> running               (ApprovalRequest.status = approved, resume from checkpoint)
  -> cancelled              (ApprovalRequest.status = denied)
  -> failed                 (ApprovalRequest.status = expired, no auto-retry)
blocked
  -> queued                 (dependency resolved)
  -> cancelled              (dependency permanently failed and no fallback path)
review
  -> completed              (ReviewResult.verdict = approve)
  -> retrying               (ReviewResult.verdict = revise, retry_count < retry_limit)
  -> failed                 (ReviewResult.verdict = reject, or revise with retries exhausted)
retrying
  -> queued                 (re-enter the front of the lifecycle with revision context attached)
failed / completed / cancelled
  -> (terminal, no further transitions)
```

Rules:

- Every transition is a single DB write (status + timestamp + AuditEvent row)
  inside one SQLite transaction, committed **before** the corresponding side
  effect starts (e.g., mark `running` before invoking the model/tool, not
  after). This is what makes restart recovery possible (§7).
- `retry_count` increments only on the `retrying -> queued` edge, never
  silently.
- A task cannot skip `review` on the happy path. Deterministic/no-op tasks
  still get an automatic reviewer pass (a trivial reviewer that checks
  acceptance_criteria mechanically) — "no reviewer configured" is not a valid
  reason to reach `completed`.
- Mission status is derived from its tasks (e.g., mission is `completed` only
  when all required tasks are `completed`; mission is `failed` if any
  non-optional task is `failed` and has no remaining fallback task).

## 5. Model Router

Provider interface (Python `Protocol`):

```text
class ModelProvider(Protocol):
    id: str
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...
    async def health(self) -> ProviderHealth: ...
```

Providers for V1:

1. **`fake`** — deterministic, in-repo, zero network calls. Required for CI
   and the evaluation harness (`docs/EVALUATION.md`). Returns canned or
   template-substituted output so tests are reproducible.
2. **`hufi-local-router`** — HTTP adapter to `http://127.0.0.1:8090/v1`
   (OpenAI-compatible). Exposes the router's own aliases as router-level
   model choices: `hufi-qwen9` (reasoning, caller controls
   `enable_thinking`), `hufi-qwen9-fast` (forced non-thinking, low latency),
   `hufi-gemma` (failover/secondary). Default timeout 180s to match the
   router's own tuned backend timeout; do not set a shorter client timeout
   that would abandon a request the backend is still legitimately serving.
3. **Remote adapters** (Anthropic/OpenAI/etc.) — added as additional classes
   implementing the same `ModelProvider` protocol. Not required for V1
   completion, but the interface must not need to change when they are
   added. No remote provider may become a hard dependency of core
   orchestration.

Routing policy (pure function, testable in isolation):

```text
select_provider(task, agent, registry_health) -> ProviderChoice
```

Inputs: task.preferred_provider hint, task risk_ceiling (privacy: R2+ tasks
touching real data should prefer local unless explicitly overridden),
estimated complexity (heuristic: prompt size / tool count), current
`hufi-local-router` health (from `/router/status`), configured cost budget.
Output includes the chosen provider id **and a reason string**, persisted on
the Task row for auditability — routing must never be a silent black box.

## 6. Tool Layer

Every tool implements:

```text
class Tool(Protocol):
    id: str
    async def classify(self, action: str, params: dict) -> RiskClass: ...
    async def execute(self, call: ToolCall) -> ToolResult: ...
```

`execute()` is only ever invoked after the Risk/Approval Engine has cleared
the call (§8). `classify()` is pure and side-effect-free so it can run ahead
of any execution and ahead of approval-request creation.

V1 required tools, in priority order:

1. **Files** — read/write inside the task's assigned workspace directory
   only (`workspaces/<mission_id>/`, resolved to an absolute path check that
   rejects any `..` escape or symlink leaving the workspace root). R0 for
   reads, R1 for writes inside the workspace.
2. **Shell** — subprocess execution, always `cwd=` the task workspace,
   allowlist of safe commands as R1-default (e.g. `pytest`, `npm test`,
   `ruff`, language toolchains), denylist of destructive patterns
   (`rm -rf`, `dd`, disk/mount operations, anything touching `/etc`, `/srv`,
   systemctl/docker on host-level units) hard-classified R3/R4 regardless of
   caller intent. Bounded output capture (truncate + note truncation),
   timeout enforced, exit code always recorded.
3. **Git** — wraps the `git` CLI inside the workspace clone. Branch/commit/
   diff are R1. Push to a shared remote is R2 (policy/reviewer-gated by
   default). Force-push, history rewrite, or pushing to `main` directly are
   R3.
4. **GitHub** — via the already-authenticated `gh` CLI or REST with a
   scoped token. Draft PR creation is R1/R2; merging, closing others' PRs,
   or repo settings changes are R3.
5. **SSH** (Phase 3, interface reserved now) — dedicated key, target
   allowlist, no host-level sshd/firewall/root actions ever auto-allowed
   (hard R3/R4 regardless of policy config).
6. **Browser/Playwright** (Phase 3, interface reserved now) — isolated
   browser context per task, external page content always treated as
   untrusted data (see `docs/SECURITY.md` threat model), never as
   instructions.
7. **MCP** — MCP tool calls are wrapped as regular `ToolCall`s with
   `tool = "mcp:<server-name>"`; they flow through the same
   classify/approve/audit pipeline as native tools. An MCP server is
   registered with an explicit capability/risk default, not trusted blindly
   because it exposes a schema.

## 7. Recovery, retries, idempotency

- **Write-before-effect:** state transitions commit before the side effect
  they describe starts, per §4. On process restart, any task left in
  `planning` or `running` with `heartbeat_at` older than
  `heartbeat_timeout_seconds` (default 120s) is swept back to `retrying` (if
  `retry_count < retry_limit`) or `failed` (otherwise) by a startup + periodic
  reaper.
- **Heartbeat:** the executor updates `heartbeat_at` on the task row at a
  fixed interval (default 30s) while a tool/model call is in flight, so the
  reaper can distinguish "slow but alive" (matches the router's known 60-180s
  latency) from "orphaned by a crash."
- **Idempotency:** every side-effecting ToolCall carries an
  `idempotency_key` derived from `(task_id, tool, action, target, params
  hash)`. Before executing, the tool checks for an existing `ToolResult` with
  that key; if found and `result_status = ok`, it is returned without
  re-executing. This makes retries after a crash mid-call safe by
  construction instead of by convention.
- **Timeouts:** per-task `budget_seconds` and a hard per-tool-call timeout
  (tool-specific default, e.g. shell 300s, model call 180s to match the
  router) both apply; whichever fires first transitions the task per §4.
- **Cancellation:** an explicit `cancelled` transition is available from any
  non-terminal state via the API; cancellation must interrupt in-flight tool
  calls (best-effort) and always records the AuditEvent even if the
  underlying process could not be killed cleanly.
- **Restart recovery proof:** the E2E test in `docs/EVALUATION.md` /
  Codex's Phase 1 exit criteria must include: kill the process mid-task,
  restart it, assert the task reaches a terminal state without manual
  intervention and without re-executing an already-`ok` ToolResult.

## 8. Risk / Approval Engine

Binding mapping from `docs/SECURITY.md` risk classes to enforcement:

| class | default policy | enforcement point |
|---|---|---|
| R0 | auto-allow | `classify()` returns R0 -> `execute()` runs immediately |
| R1 | auto-allow | same, logged to AuditEvent |
| R2 | reviewer/policy-gated | orchestrator checks a policy table (`config/risk_policy.yaml`) keyed by tool+action; if not explicitly allowed, task moves to `review` for a reviewer decision before the call executes, not after |
| R3 | Pascal approval required | task moves to `waiting_approval`, ApprovalRequest row created, execution blocks until `approved` |
| R4 | Pascal approval required | same as R3, plus the tool's `classify()` must not be overridable by any per-project policy config — hard-coded in the tool implementation |

`classify()` implementations are pure functions unit-tested independently of
any live model/tool call — this is explicitly required by CLAUDE.md's "Done
means... risk/approval logic is testable." ApprovalRequest resolution for V1
is via CLI (`hufiagents approve <id> [--note ...]` /
`hufiagents deny <id> --note ...`) hitting the same API the future dashboard
will use — no bespoke approval channel to maintain later.

## 9. Memory boundaries

| layer | storage | scope | write access |
|---|---|---|---|
| Task context | SQLite `task_context` table | one task, garbage-collected on mission completion + retention window | orchestrator + assigned agent only |
| Project knowledge | workspace files + a `project_knowledge` table (pointers, not blobs) | one project/mission line | builder/reviewer agents for that project |
| Agent memory | SQLite `agent_memory` table | one agent id, operational history (what worked, what failed) | that agent only, via a narrow API, not free-text dumping |
| Global HufiBoss knowledge | **read-only bridge** to `/srv/hufi/shared/knowledge/` (existing canonical store) | cross-project | HufiAgents reads; it does not write here in V1 (see ADR-004) |
| Audit history | SQLite `audit_log` table | everything | append-only, insert-only repository method |

Vector search is explicitly out of scope for V1. If added later, it indexes
one of the sources above; it does not become a source of truth on its own.

## 10. Reviewer / Master Audit

The Reviewer is an Agent Registry entry (`reviewer`) with a narrow contract:
given a Task and its produced output/ToolResults, it must return a
`ReviewResult` with a verdict. Minimum reviewer behaviors required for V1:

- Mechanically check `acceptance_criteria` where they are checkable (test
  exit code, file exists, lint passes) before any model-based judgment.
- Reject work that violates `allowed_tools` or exceeds `risk_ceiling` even if
  the output looks fine — a scope violation is an automatic reject,
  independent of output quality.
- On `revise`, attach the findings to the task's context so the retried
  attempt sees what failed, instead of repeating the same mistake blind.

## 11. Web UI

Deferred past V1 core (matches `README.md` milestone ordering: dashboard is
milestone 7, after the mission->task->agent->tool->review->result loop, local
provider, approval gate, and git/PR workflow). V1 exposes everything the
future dashboard needs as a plain REST API (missions, tasks, approvals,
audit) so the UI is a thin client, not a redesign, when it is built.

## 12. Deployment

Matches the Low-resource profile from `docs/XXL-AUDIT.md`:

- One systemd unit, dedicated low-priv service user, `127.0.0.1`-bound,
  explicit `MemoryMax=`/`CPUQuota=` in the unit.
- SQLite file under the service's own writable path.
- No new Postgres/Redis instance for V1.
- Local model calls go to the existing `127.0.0.1:8090` router.
- Any future public/web-facing surface goes through nginx on a **new**
  vhost, following the existing `lab.huficloud.heyhufi.com` TLS pattern —
  never edited into the existing site configs.

## 13. First end-to-end proof (binding acceptance test)

Unchanged in spirit from the original architecture draft, now concrete:

1. `POST /missions` with an outcome and `risk_ceiling=R1`.
2. Orchestrator creates at least one Task, assigns the `builder` agent.
3. Model Router selects the `fake` provider (deterministic) in tests, or
   `hufi-local-router` in a live manual run.
4. Task executes one harmless workspace Files tool call.
5. Every state transition and the ToolCall/ToolResult are persisted as
   AuditEvents.
6. Reviewer agent evaluates output, returns `approve`.
7. Mission reaches `completed`; result is queryable via
   `GET /missions/{id}`.
8. Process restarts; the same mission/task/audit history is present and
   unchanged (`GET /missions/{id}` returns identical data pre/post restart).

This is Codex's Phase 1 exit criterion, expanded in
`docs/HANDOFF-CODEX-V1.md`.
