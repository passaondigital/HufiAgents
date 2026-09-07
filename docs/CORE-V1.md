# Core V1 — runnable integration

## Start and verify

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
HUFI_DEFAULT_PROVIDER=fake uv run hufiagents serve
```

API/status: `http://127.0.0.1:8765/`. OpenAPI: `/docs`.
`uv run hufiagents serve` defaults to the existing HUFI Qwen router instead.
The CLI always binds loopback and uses one worker. A process lock on the database
prevents accidentally starting a second scheduler against the same SQLite file.
Dependencies are fully pinned in `uv.lock`; Python is pinned to 3.12.

```sh
curl -s http://127.0.0.1:8765/missions \
  -H 'Content-Type: application/json' \
  -d '{"outcome":"Write a local test checklist","risk_ceiling":"R1"}'
uv run hufiagents list
uv run hufiagents show MISSION_ID
uv run hufiagents audit MISSION_ID
```

Default planner: one task per outcome, or up to 20 explicitly supplied `steps`.
Steps form a sequential dependency chain. Each step may set its objective,
expected_output, acceptance_criteria, allowed_tools, provider preference and
bounded budgets. The builder calls the selected model, performs explicitly
requested supported operations, and writes a create-only artifact. The reviewer
checks every task. Mission results are available through the API and CLI.
The default criteria check nonempty content and a readable nonempty artifact;
they prove pipeline execution, not semantic correctness of arbitrary outcomes.
`contains` and `exit_code` criteria provide additional mechanical checks. Unknown
criterion types are rejected rather than silently approved.

## Layout and interfaces

- `contracts.py`: Pydantic representations of every architecture §3 contract.
- `persistence/`: SQLAlchemy Core tables, versioned migration and transaction-scoped
  repositories. ToolCall and ToolResult share one row per architecture §3.5.
  Memory tables have independent scope/owner/key/value records.
- `orchestrator/`: planner, DB-backed registry, bounded queue, runner, reviewer,
  dependency resolution, heartbeat/reaper and explicit state machine.
- `providers/`: protocol, deterministic fake, HUFI router, optional Ollama HTTP.
  HTTP requests use no inherited proxy credentials; no paid providers required.
- `tools/`: protocol, Files/Shell/Git, policy gateway, reserved later integrations.
- `risk/`, `memory/`: narrow policy and scope ownership boundaries.
- `api/`, `cli/`: local resource API, read-only status and thin HTTP client.

The persistence UnitOfWork owns SQL. Lifecycle changes and their audit events
commit together. Every task has mandatory ReviewResult evidence before completion.
The audit table rejects UPDATE and DELETE with SQLite triggers. Audit repositories
expose append and paginated reads. Routing decisions, assignments, model call/result
metadata, tool intent/results, approvals, reviews, retries and recovery are logged.
Model output, task input and workspace artifacts can contain user information:
keep `run/` and `workspaces/` local, access-controlled and out of Git. Regex
redaction handles common credentials; it is not a general DLP classifier.

## Execution boundaries

V1 performs no production deployment and runs no model-written shell command.
The model returns deliverable text, not executable policy or tool instructions.

Files use mission-owned directories, reject absolute/traversal/symlink/hardlink
paths and reserved credential/Git metadata paths, cap content size and create
exclusively. Existing differing artifacts are never overwritten. Revisions use
new artifact paths; retries with identical content can reconcile an existing file.
Directories are not an OS sandbox against other processes under the same Unix user.
A future worker handling hostile code needs kernel/container isolation first.

Shell currently exposes `run_command` with `command=pwd` or `git_version` only.
Arbitrary commands, interpreters, pytest/npm hooks and host administration are
classified R3/R4 and cannot execute, even following human approval.
Git supports own-workspace init/status/diff/branch/add/commit with sanitized
environment, disabled hooks/helpers/signing and bounded execution. Branch creation
requires `hufi/…`. Push, clone, force-push, arbitrary config and external repositories
are not enabled. GitHub/SSH/browser/MCP remain reserved capabilities through
`ReservedTool`; no existing authentication state is automatically exposed to agents.

R0/R1 within task and agent capabilities are automatic. Agent risk ceiling is a
hard cap. R2 outside the explicit YAML allowlist gets an audited rejecting preflight
review. R3/R4 within an agent's configured ceiling create a pending approval before
any effect. The shipped builder has ceiling R1, so no dangerous operation can enter
its execution path. Tests use harmless simulated higher-risk tools to exercise
approval/resumption without changing that shipped ceiling.

## Approval and cancellation

Set `HUFI_APPROVAL_TOKEN` to a generated owner-only secret outside Git to enable
resolution. With no configured token, approval endpoints return 503. Invalid
credentials return 401. The token is never passed to a model or tool subprocess.

```sh
uv run hufiagents approve APPROVAL_ID --note 'Reviewed exact requested effect'
uv run hufiagents deny APPROVAL_ID --note 'Outside scope'
uv run hufiagents cancel TASK_ID
```

Approval is scoped to the precise persisted tool-call/idempotency key; it does not
relax an agent ceiling or enable an unsupported executor. Denial cancels the task;
expiry fails it. Cancellation commits before interrupting the runner and expires
pending approvals. Terminal tasks cannot be reopened. These are loopback dev APIs;
mutations from browser Origin headers and untrusted Host values are rejected.
Use a separately designed authenticated gateway before any remote/public exposure.

## Recovery and limits

Defaults: two concurrent tasks, 100 pending tasks, two retries, heartbeat every
30s, stale threshold 120s, model timeout 180s, total task-attempt budget 300s,
tool timeout 30s and approval expiry 24h. Retry count advances only on the
retrying→queued edge. Provider errors retry within the budget; policy/path errors
fail immediately. Reviewer revise findings are fed into the next model request.
Each attempt has a timeout and bounded token request, with retries independently bounded.

Startup and periodic reaper recover stale planning/running work. A clean shutdown
leaves interrupted work checkpointed; restart may wait for the stale threshold.
Review-state work resumes review. Already-ok tool results are reused by a key over
task/tool/action/target/parameter hash. A file written before a process crash can
be reconciled by exact content equality without rewriting. Unknown interrupted
non-file effects fail closed for reconciliation, because a SQLite key cannot
promise exactly-once execution across an external effect and a process crash.

Tests actually terminate a child process via `os._exit(75)` after a file effect
and after its committed result, then restart. They assert completion, audit/review
records and unchanged artifact inode/mtime. Tests also cover timeout, retries,
review correction/rejection, dependency failure, concurrency, cancellation,
approval approve/deny/expire, R2 preflight, path escape and audit immutability.
Tests make no model network calls; integration tests need ordinary local thread/
socket support for Starlette TestClient. No external network is needed at test time.

## Deployment and rollback

No Docker/Compose stack is needed under the audited Low profile. No existing
service, Linux account, proxy config or shared knowledge file is changed.
A non-installed systemd example is provided in `deploy/hufiagents.service.example`.
Provisioning it is separate from this local demo and requires a fresh resource check.

Stop only the HufiAgents process to roll back a dev run. Retain `run/` and
`workspaces/` for evidence. Earlier Git commits remain usable in separate worktrees;
never downgrade a database after a future incompatible migration without a copy.
The current migration is additive and idempotent. Schema migration 001 is the only
version shipped in this core.

## Handoff alignment

Claude handoff `5d853d9` is incorporated as the branch base and preserved unchanged.
Read `docs/DECISIONS.md` ADR-007/008 for explicit branch, status-page, optional
Ollama, transition and safety refinements. Read `docs/HANDOFFS.md` for the concrete
verification and remaining Phase 2 work. This is a Core V1 integration delivery;
it does not claim autonomous coding-workforce/PR publishing completion.
