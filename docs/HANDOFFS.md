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

No earlier handoffs recorded.
