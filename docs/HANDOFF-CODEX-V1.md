# Handoff to Codex — HufiAgents V1 Implementation Spec

Audience: Codex, Builder & Integration Lead. This is not background reading —
it is the build order. `docs/ARCHITECTURE.md` is the binding spec; this file
is how to turn it into a repository in the right sequence, on the resource
budget the audit actually found.

Read first, in this order: `docs/XXL-AUDIT.md`, `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md` (ADR-001 through ADR-006). Do not re-derive stack or
resource decisions already made there — extend via a new ADR if you find
evidence one is wrong, don't silently deviate.

Branch: `codex/core-builder` per `docs/OPERATING_MODEL.md`.

## 0. Ground rules specific to this handoff

- Single Python process for V1 (ADR-002). No Redis, no new Postgres, no
  Ollama (ADR-003). Default task concurrency = 2.
- Every table in `docs/ARCHITECTURE.md` §3 needs a migration and a
  repository method before the first feature that uses it — do not
  freehand SQL inline in orchestration code.
- The `fake` provider must exist before the `hufi-local-router` adapter.
  CI must pass without any network call and without the local model
  workers running.
- Do not touch, restart, or reconfigure anything listed in
  `docs/XXL-AUDIT.md` "Risks / do-not-touch list". If a dev-time port is
  needed, pick one outside the documented range and outside `9900`/`37965`.

## 1. Repository layout (proposed, adjust only with a `docs/DECISIONS.md` note)

```text
hufiagents/
  api/            FastAPI app, routers per resource (missions, tasks,
                  approvals, audit, agents)
  orchestrator/   task engine, state machine, reaper, scheduler loop
  providers/      ModelProvider implementations: fake.py, hufi_local_router.py
  tools/          Tool implementations: files.py, shell.py, git.py, github.py
                  (ssh.py, browser.py, mcp.py as reserved interfaces/stubs)
  risk/           classify() functions + config/risk_policy.yaml loader
  memory/         task_context, project_knowledge, agent_memory repositories
                  + read-only bridge into /srv/hufi/shared/knowledge
  persistence/    SQLAlchemy Core engine, repository interfaces, migrations/
  cli/            thin HTTP client over the API (typer or argparse)
  config.py       settings (pydantic-settings), including
                  max_concurrent_tasks, heartbeat_timeout_seconds,
                  local_router_base_url, workspace_root
tests/
  unit/           classify(), state machine transitions, idempotency logic
  integration/    full API + orchestrator + fake provider, in-memory/temp SQLite
  e2e/            docs/ARCHITECTURE.md §13 proof, including the restart test
workspaces/        gitignored — per-mission working directories (dev default;
                  production default is /srv/hufi/lab/factory/projects/hufiagents/,
                  see docs/XXL-AUDIT.md "Safe installation plan")
```

## 2. Build order (do not reorder without a reason you can defend in review)

### Step 1 — bootstrap
- `pyproject.toml`, dependency pins (FastAPI, uvicorn, sqlalchemy>=2,
  httpx, pydantic-settings, pytest, pytest-asyncio, ruff or equivalent).
- `.env.example` (no secrets — placeholders only, per `AGENTS.md`).
- Lint/format/test one-liners documented in `README.md`.
- CI workflow that runs lint + unit + integration tests with zero external
  network dependency (`fake` provider only).

### Step 2 — persistence
- SQLAlchemy Core table definitions for every contract in
  `docs/ARCHITECTURE.md` §3.
- Ordered `.sql` (or Python-defined) migrations + `schema_migrations`
  tracking table, applied idempotently on startup.
- Repository interfaces (`Protocol` classes) per table; `audit_log`
  repository exposes only an `append()` method — no update/delete path
  even at the Python level.

### Step 3 — contracts as code
- Pydantic models mirroring §3 exactly (field names must match — Claude's
  reliability/eval work will assume these names).
- API routers exposing at minimum:
  - `POST /missions`, `GET /missions/{id}`, `GET /missions`
  - `GET /tasks/{id}`, `GET /tasks?mission_id=`
  - `GET /approvals`, `POST /approvals/{id}/approve`,
    `POST /approvals/{id}/deny`
  - `GET /audit?mission_id=` (paginated)

### Step 4 — state machine
- Implement the transition table in `docs/ARCHITECTURE.md` §4 as an
  explicit allowed-transitions map, not scattered `if` statements — a
  disallowed transition must raise, not silently no-op.
- Unit tests: every listed edge is exercised; every non-listed edge is
  proven to raise.

### Step 5 — providers
- `fake` provider: deterministic given a task's objective/context (e.g.
  template substitution or a canned response keyed by a test fixture id).
  This is what CI and `docs/EVALUATION.md` golden tasks run against.
- `hufi_local_router` provider: `httpx.AsyncClient` against
  `settings.local_router_base_url` (default `http://127.0.0.1:8090/v1`),
  OpenAI-compatible request/response shape, 180s timeout default, surfaces
  the router's own model aliases (`hufi-qwen9`, `hufi-qwen9-fast`,
  `hufi-gemma`) as selectable choices. Do not hardcode a shorter timeout —
  real turns through this router legitimately take 60-180s+ (see
  `docs/XXL-AUDIT.md`).
- `select_provider()` routing function per `docs/ARCHITECTURE.md` §5,
  unit-tested with the `fake` provider and a mocked router health check.

### Step 6 — tools + risk engine, wired together
- Implement `classify()` for Files/Shell/Git before `execute()` for any of
  them — the Risk Engine must be able to block a call before it can run.
- `config/risk_policy.yaml`: explicit allowlist for R2 auto-allow cases;
  everything not listed defaults to reviewer-gated at R2 and
  Pascal-approval at R3/R4, per `docs/ARCHITECTURE.md` §8.
- Files/Shell/Git tools scoped to the mission workspace directory
  (ADR-005) — write a dedicated test that a `..`/symlink escape attempt is
  rejected, not just happy-path tests.
- GitHub tool via the already-authenticated `gh` CLI on this host (see
  `docs/XXL-AUDIT.md` — `gh` is installed and logged in as `passaondigital`)
  or REST with a scoped token from `.env`; draft PR creation only for V1,
  merge/close/settings changes are out of scope until R3 approval flow is
  proven.
- SSH/Browser/MCP: stub `Tool` implementations that raise
  `NotImplementedError` with a clear message — reserve the interface, do
  not build Phase 3 tools yet.

### Step 7 — audit log + reviewer
- Every state transition, tool call, approval request/resolution writes an
  `AuditEvent` in the same transaction as the state change (write-before-
  effect, `docs/ARCHITECTURE.md` §7).
- Reviewer agent: mechanical acceptance-criteria check first (exit codes,
  file existence, lint/test pass), model-based judgment only where
  criteria aren't mechanically checkable. Reviewer pass is mandatory on
  every task, including the deterministic E2E test (ADR-006) — assert a
  `ReviewResult` row exists, don't just assert `status = completed`.

### Step 8 — recovery
- Heartbeat column update while a tool/model call is in flight.
- Startup + periodic reaper sweeping stale `planning`/`running` tasks per
  `docs/ARCHITECTURE.md` §7.
- Idempotency key check before every side-effecting tool `execute()`.
- Test: start a task, kill the process mid-tool-call (e.g. `os.kill` the
  test process or simulate via a fault-injection hook), restart, assert
  the task reaches a terminal state without re-executing the already-`ok`
  ToolResult.

### Step 9 — E2E proof
- Implement `docs/ARCHITECTURE.md` §13 literally as a test: mission ->
  task -> fake provider -> files tool -> reviewer -> completed ->
  persisted -> (separately) restart-and-still-present.
- This test is the Phase 1 exit gate. Green here means "ready for Claude
  Code review," not "done" — expect review findings and address P0/P1s
  before merge, per `docs/OPERATING_MODEL.md`.

### Step 10 — deployment shape (only once Step 9 is green)
- systemd unit following the `hufirouter`/`hufilab` pattern: dedicated
  low-priv user, no sudo, no docker group unless a specific tool proves it
  needs one, `127.0.0.1`-bound, `MemoryMax=`/`CPUQuota=` set conservatively.
- Do not enable/start this unit against production without re-checking
  `free -h` headroom first, per `docs/XXL-AUDIT.md` "Safe installation
  plan" step 5. Getting the dev/test stack running does not require this
  step at all — keep it decoupled so Phase 1 isn't blocked on a host
  change.

## 3. Definition of done for Phase 1 (Codex's current run)

All of the following, matching `docs/ARCHITECTURE.md` §13 and
`prompts/CODEX_START.md`'s existing Phase 1 checklist:

- [ ] Repo bootstrapped, reproducible dev start command documented in
      `README.md`.
- [ ] All §3 contracts implemented as tables + Pydantic models + repository
      methods.
- [ ] State machine transition rules implemented and unit-tested (every
      listed edge allowed, every other edge rejected).
- [ ] `fake` provider implemented; CI green with zero network dependency.
- [ ] `hufi_local_router` provider implemented and manually verified
      against the live `127.0.0.1:8090` endpoint (not required for CI, but
      required for Phase 1 sign-off — paste the verification transcript
      into the PR description).
- [ ] Files/Shell/Git tools implemented, workspace-escape rejection tested.
- [ ] Risk/Approval Engine wired in before tool execution, R0-R4 policy
      table testable in isolation.
- [ ] Audit log append-only and populated by every transition/tool call.
- [ ] Reviewer agent implemented, mandatory on every task (ADR-006).
- [ ] Heartbeat + reaper + idempotency implemented; restart-recovery test
      green.
- [ ] `docs/ARCHITECTURE.md` §13 E2E test green, including the restart
      assertion.
- [ ] Docs updated where implementation details diverge from this handoff
      (update `docs/ARCHITECTURE.md` via a new ADR if you change a
      contract, don't let docs silently drift from code).
- [ ] Commits pushed to `codex/core-builder`; PR opened once the E2E test
      is green, referencing this handoff and `docs/ARCHITECTURE.md` §13 as
      acceptance criteria.

## 4. What Claude Code will check in review

Per `CLAUDE.md`/`prompts/CLAUDE_START.md`: correctness, failure modes,
security (especially the workspace-escape and risk-classification tests),
resource usage against the audit's Low-resource profile, test coverage,
maintainability, provider lock-in (is `fake` truly swappable for
`hufi_local_router` without orchestration changes?), uncontrolled agent
loops (does retry_limit actually stop retries?), and auditability (is every
side effect represented as an AuditEvent?). P0/P1 findings will come with
reproducible evidence and acceptance criteria, and will be fixed directly in
review where the fix is small and clearly scoped, per
`docs/OPERATING_MODEL.md`.
