# HufiAgents V1.0 — Release Record

**Tag:** `v1.0.0`
**Date:** 2026-09-07
**URL:** https://agents.heyhufi.com
**Main commit at release:** see `git log --oneline -1` on `main` at tag time.

## What V1.0 is

HufiAgents is now a real, running, login-gated service Pascal can open in a
browser and use: submit a mission in plain language, watch it get planned
into tasks, routed to an agent, executed by a local model (HUFI AI Router —
Qwen), reviewed mechanically, retried/recovered on failure, and gated on
approval for anything risky (R3/R4) — with every step visible in an
audit timeline instead of raw logs.

## What shipped in this phase (on top of Phase 3A)

- **Auth** (`hufiagents/auth.py`, ADR-015): stdlib-only PBKDF2 password hash +
  signed session cookie. Opt-in, closes the whole API/UI except `/health` and
  `/login` once configured.
- **Web UI** (`hufiagents/api/status.html`, `login.html`): Dashboard, Mission
  erstellen, Mission Detail, Agents, Projects, Models, Approvals, Audit
  (human-readable timeline, raw JSON behind "Details"), System.
- **`GET /projects`, `GET /models`**: project registry and live local-router
  health/failover status.
- **`Settings.public_hostname`**: lets the app validate the reverse proxy's
  real `Host` header.
- **Deployment**: dedicated `hufiagents` system user, self-contained venv
  under `/srv/hufi/lab/factory/projects/hufiagents`, hardened systemd unit,
  nginx vhost + Let's Encrypt certificate for `agents.heyhufi.com`.

## Real acceptance evidence (run against the live deployment, not a test suite)

1. **HufManager technical status mission** — real local Qwen call, real
   `git clone` via the HufManager connector, reviewer approval, completed
   mission with a P0/P1/P2-structured report grounded in real,
   freshly-gathered facts about the repository (open `SECURITY_TODO.md`
   items, duplicate lockfiles, etc.). Two runs; the second used a larger
   token budget for a fuller report. Mission IDs:
   `877fa0c0-443e-4244-a817-f5a72ede54ae`,
   `42b3e6ac-a31b-4c5f-beed-fc15c04f385a`.
2. **Retry**: a mission with an intentionally unsatisfiable acceptance
   criterion was reviewed, rejected (`revise`) twice, retried automatically
   each time, and settled once the criterion happened to be met — full
   `review`/`state_transition` audit trail. Mission `ee9a0a22-edeb-48b0-9c97-bc413a5f7d8d`.
3. **Crash recovery**: the running `hufiagents.service` process was
   `kill -9`'d mid model-call. systemd restarted it; the stale-heartbeat
   detector correctly re-queued the interrupted task
   (`recovery` / `reason: stale heartbeat`), which then re-ran and completed
   normally. Mission `aea732b3-7706-4925-bcd4-7d958d1f84b5`.
4. **R3 approval**: a `git.push` targeting `main` (R3) never executed
   (`execution_started: false`, `result_status: blocked`) — it appeared in
   `GET /approvals`, was denied through the browser session (no separate
   bearer token), and the task/mission correctly ended `cancelled`. Mission
   `ca710783-9b5f-4672-b868-6cf5d6aae3da`. (The `integrator` agent's risk
   ceiling was temporarily raised to R3 in the live database to reach this
   path for the test, then reverted to its shipped R2 immediately after —
   the same pattern the automated test suite uses.)

These missions and their full audit trails remain visible in the running
system (Dashboard / Audit) as evidence, not deleted after the test.

## Known risks / not done in V1

- **Local model conciseness**: the shipped local model can produce a shorter
  report than requested (seen in acceptance test 1's first run, truncated at
  the default 512-token budget). `budget_tokens` is per-task and can be
  raised; the system prompt is not further tuned for exhaustiveness in V1.
- **Heartbeat-detected recovery latency**: a hard crash is only detected
  after `HUFI_HEARTBEAT_TIMEOUT_SECONDS` (120s in production) — proven
  correct, but not instant.
- **HufiAgents project self-analysis has no test/build/lint command**
  registered (`config/projects.yaml`) because the sandbox requires a system
  `/usr/bin/pytest`, which this host doesn't have; HufManager's is
  configured and used.
- **No push/PR credential configured for V1** (`HUFI_GITHUB_TOKEN` empty) —
  the acceptance mission's `git.push` in the approval test never had a real
  destination even if approved. Intentional: V1 didn't need write access to
  ship.
- **`Ollama` provider unavailable** in this deployment (not installed) —
  `hufi-local-router` (Qwen) is the sole real provider; `Models` correctly
  reports it unhealthy rather than hiding it.
- Full list of Phase 3A-era risks: `docs/PHASE3A-FINAL-REVIEW.md`.

See `docs/V1-OPERATIONS.md` for running it and `docs/V1-USER-GUIDE.md` for
using it.
