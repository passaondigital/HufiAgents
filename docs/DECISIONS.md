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

### ADR-007 — Core integration branch and additive implementation

**Status:** accepted (2026-09-07)

Pascal explicitly requires `codex/core-v1`; it supersedes the handoff's
`codex/core-builder`. A separate worktree starts at Claude's architecture
commit `5d853d9`. Existing documents and systems are preserved. Python 3.12,
FastAPI, SQLAlchemy Core/SQLite and concurrency 2 follow the handoff.
An optional Ollama HTTP adapter satisfies the direct request without installing
or managing Ollama. The default remains the existing HUFI local router.
A minimal read-only HTML status page is included as explicitly requested.
No Docker/Compose or production service installation is needed for this core.

### ADR-008 — Explicit exceptional transitions and fail-closed execution

**Status:** accepted (2026-09-07)

Architecture §4 omits `planning -> retrying`, while §7 requires it for
recovery. §7 also permits cancellation from every nonterminal state, absent
from §4's normal table. Implement the exact normal table and explicit
`recovery=True` / `cancel=True` exceptions; both remain audited transactions.

A directory and `cwd` do not isolate arbitrary code. V1 shell execution uses
fixed argument-vector operations (no shell interpreter, no arbitrary scripts
or package hooks); broader untrusted test/build execution requires a future
OS sandbox. Dangerous classifications still require approval, but approval
never grants an unsupported executor capability. This tightens ADR-005.

A crash after an external effect but before its result commit cannot be
made exactly-once by a database key alone. Unknown effects fail closed for
manual reconciliation; create-only files may reconcile identical content.
Already successful tool results are reused. Audit detail is redacted, and
model payloads remain task context rather than raw audit text.

### ADR-009 — Git push / GitHub PR workflow: a new `integrator` agent, not a
### capability raise on `builder`

**Status:** accepted (2026-09-07)

**Context**

`docs/ROADMAP.md` Phase 2 requires git push and a GitHub PR workflow.
`tools/git.py` (V1) hard-disabled `push` and any GitHub tool did not exist;
`docs/CORE-V1.md` explicitly relied on this: "the shipped builder has ceiling
R1, so no dangerous operation can enter its execution path." `git.push` is
already classified R2 (`docs/ARCHITECTURE.md` Sec8), and PR creation is R1/R2
per Sec6.4/`docs/HANDOFF-CODEX-V1.md`. Both need a real executor now.

**Decision**

Implement `GitTool.push`/`GitTool.remote_add` and a new `GitHubTool.open_pr`
(`gh pr create --draft` only). Add both to `config/risk_policy.yaml`'s
`r2_auto_allow` (the architecture's documented mechanism for "R2, automatic
only when policy explicitly allows it" — no change to `ToolGateway`'s R2
logic itself). Add a new Agent Registry entry, `integrator`
(`default_risk_ceiling=R2`, `tools=[files,shell,git,github]`), instead of
raising `builder`'s ceiling. A task opts in via the new
`TaskSpec.agent_id`/`Task.assigned_agent_id` field (defaults to `None` ->
`"builder"`, unchanged from V1's hardcoded assignment, validated against the
registry at `submit()` time). The remote URL, GitHub repo, base branch and
token are `Settings` fields only (`HUFI_GIT_REMOTE_URL`, `HUFI_GITHUB_REPO`,
`HUFI_GITHUB_BASE_BRANCH`, `HUFI_GITHUB_TOKEN`), all empty/disabled by
default; `GitTool`/`GitHubTool` never read a caller-supplied remote/repo/token
from `call.params` — only the server config. `GH_TOKEN` is injected as
subprocess env only (never persisted, never the host's own logged-in `gh`
session — `run_process`'s isolated env, including its `HOME` override, is
unchanged, so `~/.config/gh/hosts.yml` is never read). Push/PR both hard
-require the current branch to match `hufi/[a-zA-Z0-9_-]{1,80}`; merge/close/
repo-settings stay unimplemented (R3, no executor, matching the shell/git R3
posture from ADR-008).

**Why**

`docs/CORE-V1.md`'s stated security property ("no dangerous operation can
enter `builder`'s execution path") is a specific, tested claim about one
named agent. Raising `builder`'s ceiling would silently invalidate that claim
for every existing/future task that doesn't ask for push/PR, since ceiling is
a hard cap independent of task risk_ceiling. A new, separately-scoped agent
is additive: `builder`'s behavior and tests are provably unchanged (verified:
`test_builder_agent_cannot_push_even_with_remote_configured`), and the new
capability is only reachable by a task that explicitly names `integrator`.
Keeping remote/repo/token server-side-only, never caller-supplied, closes the
obvious alternative attack: a task/mission body cannot redirect a push or PR
to an attacker-chosen destination even once `integrator` is used.

**Consequences**

Push/PR remain fully inert (`PermissionError`) until Pascal explicitly
configures `HUFI_GIT_REMOTE_URL` and/or `HUFI_GITHUB_REPO`+`HUFI_GITHUB_TOKEN`
locally (never committed — `.env.example` keeps placeholders only, per
`docs/SECURITY.md`). Any future agent that should be allowed to push/open PRs
reuses the same `integrator` role or gets its own new registry entry with an
explicit ceiling — `builder`'s R1 boundary is not the place to special-case
this. See `docs/PHASE2-GIT-PR-WORKFLOW.md` for the operator-facing runbook.

### ADR-010 — Phase 2B project connector: a server-side project registry,
### not a caller-supplied repo

**Status:** accepted (2026-09-07)

**Context**

Phase 2B (`docs/ROADMAP.md`) requires HufiAgents to clone a real external
project (first: `passaondigital/hufmanager`), work on it in an isolated
branch, run its own test/build/lint, and push/open a PR via the `integrator`
agent from ADR-009. Until now, `GitTool` only ever operated on a fresh,
empty, `git init`'d workspace repo (ADR-005) — there was no way to bring an
existing external codebase into a mission workspace at all, and no per-
project test/build command existed (`ShellTool` only had a two-command
closed allowlist, `pwd`/`git_version`).

**Decision**

Add `hufiagents/projects/` — a `ProjectRegistry` reading `config/projects.yaml`
(mirrors `risk.Policy`'s own pattern): `id -> {repo_url, github_repo,
default_branch, allowed, test_command, build_command, lint_command}`. A task
selects a project by `Task.project_id` (new field, opt-in, defaults to
`None`, validated against the registry at `submit()` time like
`assigned_agent_id`). `GitTool` gains `clone` (R1) — clones only
`self.project.repo_url`, never a caller-supplied URL — and `add`/`commit` now
hard-require the current branch to not be `main`/`master`/the project's
`default_branch` before executing (checked via `git symbolic-ref --short
HEAD`, which resolves correctly even before the first commit — `rev-parse
--abbrev-ref HEAD` does not). `push`'s existing remote check (ADR-009) is
generalized to also verify the workspace's actual configured `origin` still
equals the target remote/project URL, not just that some `remote_url` setting
is non-empty — defense in depth against origin drift. `ShellTool` gains
`run_tests`/`run_build`/`run_lint`, each executing exactly the registry's own
pre-registered argv for the active project, never a caller-supplied command.
A new `Task.dry_run` field (opt-in, default `False`) makes `GitTool.push` and
`GitHubTool.open_pr` return a synthetic `ok` result describing what would
have happened, without ever invoking `git push`/`gh pr create` — for
rehearsing/demonstrating a full pipeline without live push/PR side effects or
even requiring `HUFI_GITHUB_TOKEN` to be configured.

**Why**

The same anti-exfiltration principle as ADR-009 applies one level up: a
project's clone source and its test/build/lint commands are exactly as
sensitive as a push destination (a task that could pick its own `repo_url`
could clone from — or a caller-controlled build/test command could execute
arbitrary code as — anywhere), so both stay server-config-only, resolved by
`project_id`, never accepted from `call.params`. Branch protection is
re-verified at the tool layer (not just relied upon from `branch`'s existing
`hufi/` pattern requirement) because `clone` is a new way to *arrive* on a
protected branch (the project's own default branch) without ever calling
`branch` — the existing push-time-only check was no longer sufficient once
`add`/`commit` could also happen while still sitting on that branch.

**Consequences**

`passaondigital/hufmanager` is the only registered project
(`config/projects.yaml`, `allowed: true`); any other `project_id` is rejected
identically to an unregistered one (`ProjectRegistry.get` never distinguishes
"unknown" from "disabled" to a caller). HufManager's own `AGENTS.md` requires
an agent working *directly inside a checkout of that repo* to follow a
`CODEXTODO.md` task queue and forbids push/deploy without explicit Pascal
approval — that governance model is separate from, and not superseded by,
HufiAgents' own risk/approval engine; this connector's first real mission
(docs/CONNECTOR-HUFMANAGER.md) stayed strictly read-only/dry-run specifically
so it never needed to reconcile the two. Cloning an existing repository was
previously impossible (ADR-005 only covered a fresh empty workspace repo) —
this ADR extends, not replaces, that isolation model: the clone still lands
only inside the mission's own workspace directory, hard-scoped exactly as
before.

### ADR-011 — Git push credential path: a static, secret-free GIT_ASKPASS
### helper, not a URL-embedded or config-persisted token

**Status:** accepted (2026-09-07)

**Context**

Phase 3A's live probe (`docs/CONNECTOR-HUFMANAGER.md`/`docs/HANDOFFS.md`)
found `GitTool.push` had no HTTPS credential path at all:
`run_process`'s fixed baseline env (`hufiagents/tools/process.py`) sets
`GIT_CONFIG_GLOBAL=/dev/null` and every git invocation passes
`-c credential.helper=` (ADR-009's deliberate isolation from the host's own
`gh auth` session), so `git push` had no way to authenticate — confirmed
live: `fatal: could not read Username for 'https://github.com': terminal
prompts disabled`. `GitHubTool` already has a working, safe pattern for its
own credential (`GH_TOKEN` as isolated subprocess env for the `gh` CLI,
ADR-009) — `git push` itself needs an equivalent, not a copy of that
mechanism (`gh`/`GH_TOKEN` has nothing to do with plain `git`'s own HTTPS
auth, which uses `GIT_ASKPASS`/`core.askPass`, not `gh`'s config).

**Decision**

A static, checked-in, **secret-free** shell script,
`hufiagents/tools/git-askpass.sh`, set as `GIT_ASKPASS` only for the single
`git push` subprocess invocation (`extra_env`, `run_process`). The script
answers git's two-step HTTPS prompt itself:

```sh
case "$1" in
    Username*) echo "x-access-token" ;;   # not a secret, GitHub's own convention
    *)         echo "$HUFI_GIT_PUSH_TOKEN" ;;  # the only place the real value ever appears
esac
```

`HUFI_GIT_PUSH_TOKEN` is set, only for that one subprocess, from
`Settings.github_token` — the same, already-existing setting `GitHubTool`
uses (ADR-009); no new secret/setting was introduced.
`GitTool.__init__` gains `push_token`; `execute()`'s `push` branch fails
closed (`PermissionError`) before spawning any subprocess if
`push_token` is empty and the call is not `dry_run` — dry-run rehearses
without needing a live credential, exactly like `GitHubTool.open_pr`
already does. Empirically verified end-to-end (a local basic-auth-enforcing
git-smart-HTTP test server, `tests/support/`) before this was written:
`GIT_ASKPASS` is honored even with `GIT_TERMINAL_PROMPT=0` and
`credential.helper=` cleared; a wrong token fails cleanly (`fatal:
Authentication failed for '<url>'` — no credential in the message, because
none was ever embedded in a URL to echo back); a correct token pushes for
real.

**Why, against each explicit requirement**

- *Never in the remote URL / never in argv*: the script's own two literals
  (`x-access-token`, and reading `$HUFI_GIT_PUSH_TOKEN`) are the entire
  credential surface; `git push`'s argv stays exactly
  `["push", "--set-upstream", "origin", branch]`, unchanged from before —
  the URL used is whatever `clone` already configured (project registry
  only), never rewritten with a username or token.
- *Never logged/audited*: `extra_env` is a parameter to
  `asyncio.create_subprocess_exec`, never touching `ToolCall.params` or any
  Pydantic model that gets persisted — there is no code path by which it
  could reach the DB, unlike `call.params`, which `redact()` scrubs as a
  second line of defense that this design doesn't even need to rely on.
- *Never persisted in git config*: `GIT_ASKPASS` is an env-var mechanism,
  orthogonal to `git config`; nothing ever calls `git config` with the
  token, and `credential.helper=` stays cleared exactly as before.
- *No personal `gh` session*: unrelated code path entirely — plain `git`,
  not `gh`; `run_process`'s existing `HOME` override already prevents
  reading the real host's `~/.config/gh`.
- *Only `HUFI_GITHUB_TOKEN`, server-side*: `push_token` is wired in
  `engine.tools()` from `settings.github_token.get_secret_value()` only —
  never from `call.params`, matching every other server-config-only value
  in ADR-009/ADR-010 (remote URL, repo, commands).
- *Scoped to the one push subprocess*: `extra_env` is passed only to the
  specific `run_process(...)` call inside the `push` branch — `clone`,
  `status`, `diff`, `log`, `add`, `commit`, `branch`, `remote_add` never
  receive it.
- *No leftover credential file/helper config*: the askpass script is
  **static** (checked into the repo, contains no secret, nothing to
  generate or delete per push) and the token exists only as one
  subprocess's environment for its lifetime — there is structurally
  nothing ephemeral to clean up, which is stronger than "cleans up after
  itself."
- *Remote still validated against the registry*: unchanged from ADR-010 —
  `push` still re-verifies `git remote get-url origin` equals the target
  project's `repo_url` (or the legacy `remote_url`) before ever reaching
  the askpass-authenticated subprocess call.
- *Only `integrator` can push, `builder` cannot*: unchanged from ADR-009 —
  `push` is still R2, `builder`'s ceiling is still R1; this ADR changes
  *how* an authorized push authenticates, not *who* is authorized to
  request one.
- *Fail closed when the token is missing*: `execute()` raises
  `PermissionError` before any subprocess is spawned if `push_token` is
  empty (checked ahead of the existing remote/branch checks), unless
  `dry_run`.

**Consequences**

`hufiagents/tools/git-askpass.sh` must ship as package data (verified: it
follows exactly the same inclusion path `hufiagents/api/status.html` already
uses — hatchling bundles it into the wheel with its source file mode
preserved, confirmed by inspecting the built wheel; `GitTool` additionally
`chmod`s it defensively before use so a permission-stripping install/copy
step can't silently break push). The same reused `HUFI_GITHUB_TOKEN` now
gates two independent effects (`git push` and `gh pr create`) — both still
fail closed independently if unset, and neither can be satisfied by the
other (a token good enough for one is not implicitly trusted for the other
without also being present on `Settings`, which is the same single
server-side value by design, not two separately-obtained secrets).
