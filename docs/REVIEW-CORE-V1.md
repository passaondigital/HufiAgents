# Review — Codex Core V1 (`codex/core-v1` @ 894fd93)

Reviewer: Claude Code (Architect & Reliability Lead), branch
`claude/review-core-v1`, based on `origin/codex/core-v1` commit `894fd93`.

**Coordination note:** Pascal started two parallel Claude Code sessions on
this exact review task, both operating in the same worktree
(`/home/administrator/HufiAgents-review-core-v1`). The second session
(`administrator-8e`) found and fixed one real bug (see below) and added
CLI/reconciliation test coverage before handing ownership of the final
commit to this session. Its contributions are folded in here and credited
explicitly rather than re-derived or duplicated.

## Geprüft

Full read of the implementation against `docs/ARCHITECTURE.md`,
`docs/HANDOFF-CODEX-V1.md`, `docs/DECISIONS.md` (ADR-001..008),
`docs/SECURITY.md`, `docs/XXL-AUDIT.md`, and `docs/CORE-V1.md`:

- Mission -> Planner -> Tasks -> Agents (`contracts.py`, `orchestrator/planner.py`, `orchestrator/engine.py`)
- Agent Registry (`orchestrator/registry.py`) and risk-ceiling enforcement (`risk/__init__.py`)
- Model Router (`providers/router.py`, `providers/hufi_local_router.py`, `providers/ollama.py`, `providers/fake.py`)
- Real local Qwen / `hufi-local-ai-router` integration — live call executed, see below
- Tool Gateway (`tools/gateway.py`) incl. idempotency/reconciliation
- Shell/Git/File security boundaries (`tools/shell.py`, `tools/git.py`, `tools/files.py`, `tools/workspace.py`, `tools/process.py`)
- Reviewer (`orchestrator/reviewer.py`)
- Retry, recovery-after-crash, persistence (`orchestrator/engine.py::_fail/recover`, `persistence/`)
- Approvals, cancellation (`tools/gateway.py`, `orchestrator/engine.py::resolve/cancel`, `api/__init__.py`)
- Audit log immutability (`persistence/migrations/001_initial.py` triggers)
- API (`api/__init__.py`), CLI (`cli/__init__.py`), status page (`api/status.html`)
- Restart-ability: real child-process crash + restart test (`tests/e2e/`)
- Resource footprint vs. `docs/XXL-AUDIT.md` (Low-resource profile, `deploy/hufiagents.service.example`)
- Port usage (`:8765` dev API — free per audit; no clash with `:8080/8081/8082/8090/4100/22/80/443/543xx`)
- Secrets: `.env.example` placeholder-only, `redaction.py`, no committed credentials
- New/duplicate services: none installed; no host state changed
- Architecture deviations: ADR-007 (branch name, optional Ollama adapter, status page) and ADR-008 (explicit transition exceptions, fail-closed non-file reconciliation) — both reviewed and accepted, see "Architekturfehler" below for the one correction made to ADR-008's implementation.

## Bestanden

- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — clean.
- `uv run pytest -q` — **156 passed** (132 baseline + 24 added by this review, see below), 0 failures.
- `uv build` — `hufiagents-0.1.0.tar.gz` + `hufiagents-0.1.0-py3-none-any.whl` built successfully.
- Real child-process crash/restart recovery test (`tests/e2e/test_restart.py`, both `after_result` and `after_effect` stages): process is hard-killed via `os._exit(75)` at two real checkpoints, restarted, and the task reaches `completed` with no artifact rewrite (inode/mtime unchanged) and, for the `after_result` stage, an audit `tool_reused` event proving idempotent replay instead of re-execution.
- Live local-model E2E test (item 7), executed against the real, running production
  infrastructure, not a mock:
  - Pre-check: `GET http://127.0.0.1:8090/router/status` — healthy, primary up, 0 failovers.
  - `hufiagents serve` started with `HUFI_DEFAULT_PROVIDER=hufi-local-router` against a throwaway SQLite DB/workspace (gitignored `run/`/`workspaces/`, deleted afterward).
  - `POST /missions` with outcome "Write one short sentence confirming HufiAgents core-v1 review E2E test is alive."
  - Mission reached `completed` in ~3s (fast route, model `hufi-qwen9`) with a real, on-topic response: *"The HufiAgents core-v1 review E2E test is confirmed alive."*
  - Verified via `/audit`: full event chain `mission_created -> task_created -> ... -> model_call(hufi-local-router) -> model_result(hufi-qwen9) -> tool_call -> tool_started -> tool_result -> review -> state_transition(completed)`.
  - Verified via `/router/status`: `requests_total` incremented 29 -> 30, served by `primary`, no failover triggered.
  - No production risk taken: single small read/inference call through the existing router, no host service touched, no model installed/stopped, throwaway DB/workspace removed afterward.

## Fehler gefunden

1. **(P1, correctness) `Rows.list()` silently ordered `ToolCall`/`ApprovalRequest` by random UUID instead of time.**
   Found and fixed by the parallel session (`administrator-8e`), verified independently by this review. `Rows.list()`'s order-column fallback was `created_at -> ts -> id`, but the `ToolCall` and `ApprovalRequest` contracts use neither field — they have `requested_at`. Every `/tool-calls`, `/approvals`, and internal `tx.tool_calls.list(...)`/`tx.approvals.list(...)` call (including the ones the Risk/Approval Engine and reviewer rely on for "most recent") was silently falling back to id-order, which is random per `uuid4()`. This does not corrupt data, but it breaks any consumer (dashboard, CLI, a future reviewer heuristic) that assumes chronological order, and it is exactly the kind of silent-wrong-not-loud-wrong bug the architecture's recovery/idempotency model depends on not having.
2. **(P2, test coverage) Zero direct test coverage for `redaction.py`.** The only barrier between model/tool output and persisted audit/API data (`docs/SECURITY.md`: "never print secret values into logs") was exercised only incidentally through other tests, never asserted against directly (key-name redaction, bearer tokens, `ghp_`/`sk-` prefixes, private-key blocks, `key=value` patterns, length bounding).
3. **(P2, test coverage) Zero test coverage for the HTTP approval-auth path.** `hmac.compare_digest`-based owner-token check in `api/__init__.py::resolve()` was only reachable indirectly (`Orchestrator.resolve()` bypasses HTTP entirely in the reliability tests); the "no token configured -> 503" case was covered, but "wrong token -> 401" and "correct token -> 200 and task resumes" were not tested at the HTTP boundary at all.
4. **(P2, test coverage) `POST /tasks/{id}/cancel` had no test at all**, at any layer, beyond the direct `Orchestrator.cancel()` unit test.
5. **(P2, test coverage) `hufiagents/memory/__init__.py` (`Memory.put`, `read_global`) — architecture §9's memory-boundary permission logic and the read-only global-knowledge bridge (ADR-004) — had zero test coverage and is not called anywhere in the runtime.** The orchestrator writes `task_context` directly (as a trusted system actor), so `Memory.put()`'s owner/actor permission checks have never been exercised by anything, and `read_global()`'s symlink/missing-root guards were unverified.
6. **(P2, test coverage) `ReservedTool` (SSH/browser/MCP placeholder, §6.5-6.7) had no test locking its fail-closed behavior** (must classify R3, must raise `NotImplementedError`, never silently succeed once wired in later).
7. **(P2, test coverage) `hufiagents/cli/__init__.py` had zero coverage.** Found and fixed by the parallel session: argument→HTTP mapping for `submit/list/show/audit/cancel/approve/deny`, including `HUFI_APPROVAL_TOKEN` bearer-header wiring and `trust_env=False`, was untested.
8. **(P2, correctness/hardening) ADR-008's fail-closed reconciliation path for non-`files` tools (a crash after `execution_started=True` but before a result commits) was only exercised end-to-end for the `files` tool** (which is safe to reconcile by content equality) via the real crash test; the fail-closed `PermissionError("uncertain prior effect...")` branch for shell/git-type tools had no direct test. Found and fixed by the parallel session.
9. **(P3, efficiency, low severity) The scheduler loop polled the DB unconditionally every 100ms with no configuration knob**, even fully idle, forever. Not a correctness issue and CPU is not the constrained resource per `docs/XXL-AUDIT.md`, but on a memory/CPU-shared host it is free to make tunable rather than hardcoded.
10. **(P3, residual risk, accepted as documented) `POST /tasks/{id}/cancel` has no auth, unlike `/approvals/*/approve|deny`.** `docs/CORE-V1.md` explicitly scopes the whole API as a "loopback dev API" pending "a separately designed authenticated gateway before any remote/public exposure," and cancellation is a stop/reduce action rather than a capability grant, so this is accepted for V1 rather than changed — see "Verbleibende Risiken."

## Fehler behoben

- **#1 (ordering bug):** fixed in `hufiagents/persistence/repository.py` — order fallback extended to `created_at -> requested_at -> ts -> id`. Regression test added:
  `tests/unit/test_persistence.py::test_tool_call_and_approval_lists_are_chronological_not_by_id`
  (ids deliberately chosen to sort opposite of insertion order, so a regression to id-ordering fails loudly instead of silently passing).
- **#2:** `tests/unit/test_redaction.py` added — 8 tests covering key-name redaction, nested structures, bearer tokens, `ghp_`/`github_pat_`/`sk-` prefixes, `key=value` free-text patterns, private-key PEM blocks, length bounding, and scalar passthrough.
- **#3:** `tests/integration/test_approvals_http.py::test_approval_http_requires_correct_owner_token` added — drives a real task into `waiting_approval` over HTTP, asserts no-token and wrong-token both return 401 and leave the approval `pending`/task `waiting_approval`, then asserts the correct token resolves it and the mission completes.
- **#4:** `tests/integration/test_approvals_http.py::test_cancel_via_http_interrupts_a_running_task` added — uses a deliberately slow provider to catch the task genuinely `running`, cancels it via HTTP, and asserts the mission reaches `cancelled`.
- **#5:** `tests/unit/test_memory.py` added — 5 tests covering `task_context`/`agent_memory`/`project_knowledge` owner/actor permission enforcement (including rejection of an unrelated actor and of an unknown layer), plus `read_global()`'s missing-root, symlinked-root, and path-escape rejection.
- **#6:** `tests/unit/test_reserved.py` added.
- **#7:** `tests/unit/test_cli.py` added (by the parallel session, verified here) — 6 tests, `httpx.Client` substituted with an in-memory recorder rather than a real socket.
- **#8:** `tests/unit/test_gateway_reconciliation.py` added (by the parallel session, verified here) — simulates a crash-recorded `ToolCall` row (`execution_started=True`, `result_status="blocked"`) for a non-`files` tool and asserts `ToolGateway.invoke` raises `PermissionError("uncertain prior effect...")` without ever calling `tool.execute`.
- **#9:** `hufiagents/config.py` gains `poll_interval_seconds` (default unchanged at `0.1`, bounded `0 < x <= 5`); `orchestrator/engine.py::_loop` now reads it from settings instead of a hardcoded literal. Documented in `.env.example` as `HUFI_POLL_INTERVAL_SECONDS`. Default behavior is unchanged (all existing tests still pass unmodified), so this is a pure hardening addition, not a behavior change requiring an ADR.

All fixes are covered by the full suite: **156 passed**, `ruff check`/`ruff format --check` clean, `uv build` clean, re-verified after every change in this review (not just once at the end).

## Architekturfehler

None found that require a correction to `docs/ARCHITECTURE.md` itself. Codex's
two additions to `docs/DECISIONS.md` (ADR-007, ADR-008) are sound
clarifications of underspecified edges in the original architecture
(§4's normal-transition table omitted the `planning -> retrying` recovery
edge and the cancel-from-any-state edge that §7 already required in prose;
ADR-008 makes both explicit as flagged exceptions rather than silently
widening the normal table). No further ADR was needed from this review —
the one correction made (finding #1) was an implementation bug in
`repository.py`, not a gap in the binding architecture document, so it did
not warrant a new ADR; it is recorded here and in the commit instead.

## Verbleibende Risiken

- **Cancel endpoint has no owner-token auth** (finding #10). Accepted as
  documented V1 scope (loopback-only, no browser cross-origin path per the
  `request_boundary` middleware, and cancellation cannot escalate privilege
  or bypass approval — it can only stop work). Recommend gating it behind
  the same `HUFI_APPROVAL_TOKEN` once a genuinely multi-tenant or
  remote-exposed deployment is on the table; not worth the added friction
  for a single-owner loopback dev/ops tool today.
- **The Memory boundary (`hufiagents/memory/`) is implemented and now
  tested, but not yet wired into the orchestrator.** The orchestrator
  writes `task_context` directly as a trusted system actor, bypassing
  `Memory.put()`'s permission checks entirely. This is fine for V1 (only
  the trusted orchestrator writes memory today) but means the permission
  boundary is unverified under real multi-agent conditions. Flag for Phase 2
  when agents themselves start writing memory records.
  `read_global()` (the ADR-004 read-only bridge into
  `/srv/hufi/shared/knowledge/`) is implemented and tested but not called by
  anything yet — correctly conservative for V1 (no accidental writes/reads
  into shared state), but it means the described "Global HufiBoss knowledge"
  memory layer is not actually reachable by an agent today.
- **GitHub/SSH/Browser/MCP tools remain `ReservedTool` stubs** (§6.5-6.7),
  as planned by the roadmap (Phase 2/3) — not a V1 gap, flagged only so the
  next phase's implementer does not assume any wiring already exists beyond
  the R3-classify/`NotImplementedError` stub.
- **`hufi-qwen35-worker` and the two unidentified local listeners
  (`127.0.0.1:9900`, `127.0.0.1:37965`) from `docs/XXL-AUDIT.md` remain
  unexplained** — not touched or investigated further by this review; still
  worth a follow-up before anything else claims a port in that range.
- **Two Claude Code sessions were run concurrently on the same review task
  in the same worktree** (see "Coordination note" above). No data was lost
  and the outcome was net-positive (an independent second pass found a real
  bug), but it was accidental, not designed. Recommend Pascal avoid pointing
  two sessions at the same worktree/branch simultaneously going forward —
  `docs/OPERATING_MODEL.md`'s "separate worktrees" guidance is about
  Codex vs. Claude, not about two instances of the same agent.

## V1-Core-Status

**Merge-ready.** All Phase 1 exit criteria in
`docs/HANDOFF-CODEX-V1.md` §3 are met: contracts implemented, state machine
transition-tested exhaustively (all 100 `State`×`State` pairs), both
providers implemented and the local one verified live, workspace/shell/git
security boundaries tested including escape attempts, risk/approval engine
enforced and tested end-to-end (including the R2-preflight-reject and
R3/R4-approval-required paths), audit log append-only and populated,
reviewer mandatory on every task, heartbeat/reaper/idempotency implemented
and proven against a real process kill at two distinct crash points,
`docs/ARCHITECTURE.md` §13's E2E proof green including the restart
assertion, package builds cleanly, and the codebase matches its own
documentation (`docs/CORE-V1.md` accurately describes what is and is not
implemented, including honestly scoping V1 as not claiming autonomous
coding-workforce/PR-publishing completion).

## Empfehlung für nächsten Schritt

1. Merge `claude/review-core-v1` into the shared integration line (or
   fast-forward `codex/core-v1`/`main` — Pascal's call on the exact
   git mechanics) now that it is fixed, tested, and reviewed.
2. Phase 2 per `docs/ROADMAP.md`: wire git worktree/branch automation and a
   real GitHub PR workflow (currently `git`'s `push`/external-repo paths and
   `github` as a tool are intentionally disabled — see `tools/git.py`), and
   pick HufManager as the first real project connector once that lands.
3. Before Phase 3 (browser/SSH), revisit the resource profile: a Playwright
   worker is meaningfully heavier than anything running today, and
   `docs/XXL-AUDIT.md`'s memory headroom was already tight at audit time.
4. Decide deliberately (not by default) whether/how to wire `Memory.put()`
   into agent-initiated writes, and whether the global-knowledge bridge
   should become reachable by real tasks — both are implemented and tested
   but inert today, which is the safe place to leave them until that
   decision is made.
5. Optional, low-priority: gate `/tasks/{id}/cancel` behind the owner token
   once the API moves beyond pure loopback-dev scope (see "Verbleibende
   Risiken").
