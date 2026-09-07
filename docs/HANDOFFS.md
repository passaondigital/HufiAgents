# Cross-Agent Handoffs

Use this file for concise handoffs between Codex and Claude Code.

## Template

```text
Date:
From:
To:
Task/Issue:
Ready:
Files/interfaces changed:
Tests run:
Known risks:
Need from receiver:
Acceptance criteria:
```

## 2026-09-07 — Claude Code -> Codex — V1 architecture ready for build

```text
Date: 2026-09-07
From: Claude Code (Architect & Reliability Lead)
To: Codex (Builder & Integration Lead)
Task/Issue: Define V1 architecture + read-only XXL audit (Pascal direct task, branch claude/architecture-v1)
Ready: yes — architecture, contracts, decisions and a concrete build-order handoff are committed
Files/interfaces changed:
  - docs/XXL-AUDIT.md (filled in from template, real host data)
  - docs/ARCHITECTURE.md (rewritten as binding V1 spec: contracts, state machine,
    model router, tool layer, risk engine, recovery model, deployment)
  - docs/DECISIONS.md (ADR-001..ADR-006)
  - docs/ROADMAP.md (Phase 0 marked done where applicable, Phase 1 given a concrete build order)
  - docs/HANDOFF-CODEX-V1.md (new — step-by-step implementation spec)
Tests run: none (no code exists yet in this repo; this pass is architecture + audit only,
  as scoped by the current task). Read-only host commands only, see docs/XXL-AUDIT.md footer
  for the exact command list used.
Known risks:
  - Host is memory-constrained (~350MB free, 66% swap used at audit time). V1 must stay
    single-process/SQLite/bounded-concurrency (ADR-002) or it will compete with production
    Qwen/Gemma workers and Supabase for RAM.
  - README.md/AGENTS.md still say "Ollama/Qwen" in places — this is aspirational, not real.
    Real local provider is http://127.0.0.1:8090/v1 (ADR-003). Do not install Ollama.
  - A private repo passaondigital/hufi-factory exists and was not reviewed (out of scope for
    a read-only HufiAgents audit). Possible scope overlap — flagging for awareness, not blocking.
  - Two unidentified local listeners (127.0.0.1:9900, 127.0.0.1:37965) were left uninvestigated;
    do not assume adjacent ports are free without checking first.
Need from receiver: build Phase 1 per docs/HANDOFF-CODEX-V1.md build order; open a PR against
  main (or a shared integration branch) once the fake-provider E2E test is green so review can
  start incrementally rather than as one large diff.
Acceptance criteria: docs/ARCHITECTURE.md §13 (first end-to-end proof) and
  docs/HANDOFF-CODEX-V1.md "Definition of done for Phase 1".
```

## 2026-09-07 — Claude Code -> Codex/Pascal — Core V1 review complete

```text
Date: 2026-09-07
From: Claude Code (Review Lead), branch claude/review-core-v1 (based on origin/codex/core-v1 @ 894fd93)
To: Codex, Pascal
Task/Issue: Full review of Codex core-v1 against docs/ARCHITECTURE.md, docs/SECURITY.md,
  docs/HANDOFF-CODEX-V1.md; run ruff/pytest/build; add missing tests; fix low/medium findings;
  run a real local-Qwen E2E test; write docs/REVIEW-CORE-V1.md.
Ready: yes — see docs/REVIEW-CORE-V1.md for the full report. Verdict: merge-ready.
Files/interfaces changed:
  - hufiagents/persistence/repository.py: fixed Rows.list() order fallback
    (created_at -> requested_at -> ts -> id); ToolCall/ApprovalRequest were silently
    ordered by random UUID before this (found by a parallel review session, verified here).
  - hufiagents/config.py + orchestrator/engine.py + .env.example: added
    poll_interval_seconds (default unchanged, 0.1s) so the scheduler loop is tunable
    instead of hardcoded.
  - docs/REVIEW-CORE-V1.md: new, full review report.
  - 7 new/extended test files (24 new tests, 132 -> 156 total): test_redaction.py,
    test_reserved.py, test_memory.py, test_approvals_http.py (this session), plus
    test_cli.py, test_gateway_reconciliation.py, and an extension of
    test_persistence.py (parallel session, folded in and verified here).
Tests run: uv run ruff check . (clean), uv run ruff format --check . (clean),
  uv run pytest -q (156 passed), uv build (wheel + sdist built), a real local-model
  E2E mission against the live http://127.0.0.1:8090 router (completed in ~3s,
  verified via /audit and the router's /router/status request counter), and the
  existing real-process-crash restart test (tests/e2e/test_restart.py, both stages).
Known risks:
  - POST /tasks/{id}/cancel has no owner-token auth, unlike approve/deny. Accepted as
    documented V1 loopback-dev scope; recommend gating before any remote exposure.
  - hufiagents/memory/ (Memory.put, read_global) is implemented and now tested but not
    wired into the orchestrator yet — inert by design until Phase 2 decides to use it.
  - Two Claude Code sessions ran concurrently on this exact task in the same worktree
    (Pascal started both); no work was lost, one found a real bug, but it was
    accidental — see docs/REVIEW-CORE-V1.md "Coordination note".
Need from receiver: merge/integrate claude/review-core-v1; Codex to pick up Phase 2
  (git worktree/PR automation, HufManager as first real project) per
  docs/ROADMAP.md and docs/REVIEW-CORE-V1.md's "Empfehlung für nächsten Schritt".
Acceptance criteria: docs/REVIEW-CORE-V1.md "V1-Core-Status" and "Empfehlung für nächsten Schritt".
```
