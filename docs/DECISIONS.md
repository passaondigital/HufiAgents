# Architecture Decisions

Use this file for concise architecture decision records until/if individual ADR files are introduced.

## Template

### ADR-XXX — Title

**Status:** proposed | accepted | superseded

**Context**

What problem/constraint triggered the decision?

**Decision**

What are we doing?

**Why**

Why is this preferable to the realistic alternatives?

**Consequences**

What becomes easier/harder? What must follow from this decision?

---

### ADR-001 — Branch name deviates from `CLAUDE.md`/`prompts/CLAUDE_START.md`

**Status:** accepted

**Context**

`CLAUDE.md` and `prompts/CLAUDE_START.md` name `claude/architecture-reliability`
as the primary branch. Pascal's direct task instruction for this V1
architecture pass explicitly named `claude/architecture-v1`.

**Decision**

Use `claude/architecture-v1` for this body of work, per direct instruction. A
direct, explicit instruction from Pascal overrides a default named in
project docs.

**Why**

`AGENTS.md` priority order and the operating model both treat Pascal's
explicit direction as authoritative over routine documentation defaults;
this is not a technical disagreement worth escalating.

**Consequences**

Future Claude Code sessions following `prompts/CLAUDE_START.md` verbatim will
default back to `claude/architecture-reliability`. Either branch name is
acceptable going forward; do not treat this as a permanent rename. If the two
branches diverge, merge/reconcile through a PR rather than force-pushing one
over the other.

---

### ADR-002 — V1 stack: Python + FastAPI + SQLite, single bounded process

**Status:** accepted

**Context**

`docs/ARCHITECTURE.md` (pre-V1 draft) left the implementation stack open
("adapt to the audit"). The XXL audit (`docs/XXL-AUDIT.md`) found the host is
memory-constrained (≈350 MB free, 66% swap used) with a Python-heavy existing
ecosystem (Hermes agent, local-ai-router, hufi-stt server all Python), and no
Ollama/Redis/native Postgres installed. `README.md`/`AGENTS.md` require a
provider-neutral, model-agnostic, local-first design that must not add load
the host cannot absorb.

**Decision**

V1 backend is Python 3.11+/FastAPI/Uvicorn (single worker), SQLite via
SQLAlchemy Core behind a repository interface, in-process `asyncio` task
execution bounded by a semaphore (default concurrency 2), no Redis, no new
Postgres instance, CLI as a thin HTTP client over the same API.

**Why**

Matches the existing operational pattern on the host (Python services running
as dedicated systemd users), avoids adding a Node/JVM/Go runtime purely for
the backend, and keeps the resource footprint small and predictable, which
the audit shows is the actual constraint (not CPU, not disk). SQLAlchemy Core
(not full ORM) plus hand-written migrations avoids an early dependency
(Alembic) while still giving a clean seam to swap in Postgres later without
touching orchestration code.

**Consequences**

A future move to Postgres/Redis is a persistence-adapter swap, not a
rewrite, as long as the repository interface boundary in
`hufiagents/persistence/` is respected. A future Web UI can be any stack
(e.g. Next.js, matching HufiLab) since it only talks to the REST API — this
decision does not constrain the eventual dashboard's frontend stack.

---

### ADR-003 — Local model provider targets the existing HUFI Local AI Router, not Ollama

**Status:** accepted

**Context**

`README.md`/`AGENTS.md`/`docs/ARCHITECTURE.md` (pre-V1) repeatedly say
"Ollama/Qwen" for local inference. The XXL audit found **no Ollama
installation** on the host. What actually runs is two llama.cpp `llama-server`
Docker containers (Qwen3.5-9B primary, Gemma-2-9B secondary) fronted by a
hand-built, already-verified OpenAI-compatible router
(`hufi-local-ai-router`, systemd, `127.0.0.1:8090`) with PRIMARY/SECONDARY
failover, a `hufi-qwen9-fast` low-latency route, and tuned timeouts, built and
tested by a prior session (see `CHRONICLE.jsonl` entries 2026-09-05).

**Decision**

HufiAgents' local `ModelProvider` adapter targets
`http://127.0.0.1:8090/v1` (OpenAI-compatible) as the local provider. Do not
install Ollama. Do not stand up a third local model worker or a second
router without a fresh capacity/decision review.

**Why**

`AGENTS.md`: "Never blindly reinstall, overwrite or remove Hermes, OpenClaw,
Ollama/Qwen, HufiOS/HufiBoss components or unrelated services." The
functioning equivalent already exists, is production-verified (Hermes
already routes through it successfully), and duplicating it would both waste
the scarce RAM budget and create two competing sources of truth for local
inference routing.

**Consequences**

Every future mention of "Ollama" in project docs describes an aspiration that
was never built and should be read as "the local OpenAI-compatible model
endpoint," currently served by `hufi-local-ai-router`. If Ollama is genuinely
wanted later (e.g. for its model-management UX), that is a separate,
deliberate decision — not a default. The Model Router's provider interface
must stay adapter-based specifically so this kind of substitution stays
cheap.

---

### ADR-004 — HufiAgents keeps its own audit log; does not write into the existing shared knowledge/chronicle

**Status:** accepted

**Context**

`/srv/hufi/shared/knowledge/` already implements canonical/historical/
systems/projects/quarantine separation plus an append-only
`CHRONICLE.jsonl` event log with its own established format and existing
consumers (other agents/sessions on this host already read and write it).
`docs/ARCHITECTURE.md`'s Memory/Audit requirements ask for an append-only
audit trail and clean memory-layer separation.

**Decision**

HufiAgents implements its own `audit_log` SQLite table as the source of
truth for everything it does. It treats `/srv/hufi/shared/knowledge/` as a
**read-only** input to the Global Knowledge memory layer in V1. It does not
write, mirror into, or otherwise mutate `CHRONICLE.jsonl` or the knowledge
tree without a dedicated future ADR and Pascal's explicit sign-off.

**Why**

`AGENTS.md`/`docs/SECURITY.md` require not disrupting existing systems and
treating irreversible/shared-state changes carefully. Writing into a shared
append-only log another live system already depends on, without agreeing the
schema/ownership with whatever currently writes it, is exactly the kind of
avoidable cross-system coupling the security policy warns about. Keeping
HufiAgents' own audit trail independent is strictly reversible and safe.

**Consequences**

There will be two audit trails on the host for a while (HufiAgents'
`audit_log`, and the existing `CHRONICLE.jsonl`). This is an accepted,
temporary duplication in exchange for not risking the existing system. A
later, explicit integration (e.g. HufiAgents exporting a filtered
CHRONICLE-formatted stream) can close this gap once the two systems'
relationship is deliberately decided, not accidentally merged now.

---

### ADR-005 — Workspace isolation via directories in V1; container sandboxing deferred

**Status:** accepted

**Context**

`docs/ARCHITECTURE.md` calls for isolated workspaces and notes containers can
strengthen isolation "later, as necessary." The host already runs 13+ Docker
containers for Supabase plus 2 for model workers under real memory pressure.

**Decision**

V1 isolation is filesystem-path-based: each mission gets a dedicated
workspace directory; the Files/Shell/Git tools hard-enforce that all
operations resolve inside that directory (reject `..`/symlink escapes).
Container-per-task sandboxing is deferred until either (a) a real security
finding demands it, or (b) host resources are re-profiled as Medium/High.

**Why**

Directory-based isolation is sufficient for R0/R1 development-shaped work
and costs no additional memory/CPU on an already memory-constrained host.
Spinning up a container per task now would directly work against the Low
resource profile the audit mandates.

**Consequences**

The Risk/Approval Engine (§8 of `docs/ARCHITECTURE.md`) is the actual
security boundary for anything beyond filesystem scope (shell command
allow/denylists, R3/R4 gating), not container isolation. This must be kept
strict and well-tested since it is carrying more weight than it would if
containers were already in place. Revisit this ADR before any task is
allowed to run untrusted/externally-sourced code.

---

### ADR-006 — Reviewer pass is mandatory on every task, including deterministic ones

**Status:** accepted

**Context**

`CLAUDE.md`/`docs/EVALUATION.md` require a reviewer catch rate metric and a
reviewer that can reject bad output. Early implementations are tempted to
skip review for "obviously fine" deterministic tasks (e.g. the fake-provider
E2E test) to simplify the happy path.

**Decision**

Every task passes through the `review` state before `completed`, even when
the reviewer's check is purely mechanical (acceptance-criteria matching, exit
code checks). There is no lifecycle shortcut that reaches `completed`
without a `ReviewResult` row.

**Why**

If the happy-path E2E test is allowed to bypass review, review becomes an
optional feature that is easy to silently regress out of the real pipeline
later. Keeping it structurally mandatory — even trivial in the deterministic
case — is what makes "reviewer catch rate" a meaningful, continuously
measured metric rather than something bolted on only for "real" tasks.

**Consequences**

The deterministic fake-provider E2E test must include and assert on a
`ReviewResult` row, not just a `completed` status. This is slightly more
setup for the simplest possible test, in exchange for the lifecycle
guarantee holding everywhere, always.
