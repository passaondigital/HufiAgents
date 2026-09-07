# Connector: HufManager

First real project connector (Phase 2B, `docs/ROADMAP.md`). Design rationale
in `docs/DECISIONS.md` ADR-010; git/PR mechanics in ADR-009 /
`docs/PHASE2-GIT-PR-WORKFLOW.md`. This document is the operator-facing
reference for the HufManager registration specifically.

## Repo

- `https://github.com/passaondigital/hufmanager.git`, public, default branch
  `main`, **not branch-protected on GitHub's side** (checked read-only via
  `gh api repos/passaondigital/hufmanager/branches/main/protection` -> 404
  "Branch not protected", 2026-09-07) — HufiAgents' own guardrails (below)
  are the only thing standing between a task and `main`.
- Registered in `config/projects.yaml` as project id `hufmanager`.

## Stack (read-only inspection, 2026-09-07, shallow clone + `gh api`)

- Vite + React 18 + TypeScript, `shadcn-ui` component library, Tailwind CSS.
- Backend: Supabase (auth, Postgres schema under `supabase/migrations/`,
  ~80 edge functions under `supabase/functions/`).
- Package manager: **npm** — `package-lock.json` is the canonical lockfile
  (README explicitly documents `npm i`/`npm run dev`). Stray `bun.lock` /
  `bun.lockb` files exist in the repo but are not referenced by README or CI;
  flagged as a known inconsistency, not acted on by this connector.
- No `.nvmrc`/`engines` field; CI pins Node 20 explicitly
  (`.github/workflows/hufmanager-canonical-verify.yml`). This host runs Node
  22.23.2/npm 10.9.8 (`docs/XXL-AUDIT.md`) — not identical, not yet verified
  to matter for lint/test/build; a real Node-20 mismatch would surface as a
  `run_lint`/`run_tests`/`run_build` failure, not silently.
- 15 `*.test.ts(x)` files under `src/` and `supabase/functions/` (Vitest).
- CI (`hufmanager-canonical-verify.yml`) runs typecheck+tests+build with
  **placeholder** `VITE_SUPABASE_URL`/`VITE_SUPABASE_PUBLISHABLE_KEY` env
  vars — no real Supabase credentials needed for CI's own build gate.
  `scripts/verify-hufmanager-release.sh` (the full canonical verify script)
  additionally requires real Supabase env vars and is **not** wired into
  this connector's `build_command` — only plain `vite build`
  (`npm run build`) is registered, which is real but not the full canonical
  release gate.
- Governance note: HufManager's own `AGENTS.md` requires any agent working
  *directly inside a checkout of this repo* to read a `CODEXTODO.md` task
  queue and forbids push/deploy without explicit Pascal approval. That file
  does not exist on this host (`/home/pascaladmin/CODEXTODO.md` — not
  present here) and this governance model is separate from HufiAgents' own
  risk/approval engine; see ADR-010 "Consequences". This connector's first
  mission stayed strictly read-only/dry-run so the two never needed
  reconciling.

## Erlaubte Aktionen (config/projects.yaml)

```yaml
hufmanager:
  repo_url: https://github.com/passaondigital/hufmanager.git
  github_repo: passaondigital/hufmanager
  default_branch: main
  allowed: true
  test_command: ["/usr/bin/npm", "test"]       # vitest run
  build_command: ["/usr/bin/npm", "run", "build"]  # vite build
  lint_command: ["/usr/bin/npm", "run", "lint"]     # eslint .
```

Reachable only via the `integrator` agent (ADR-009, R2 ceiling) with
`Task.project_id: "hufmanager"`. `git.clone`/`git.push` and
`shell.run_tests`/`run_build`/`run_lint` all resolve their real argv/URL from
this file only — never from a task's `params` (ADR-010).

`git.status`/`git.diff`/`git.log` (R0, read-only, bounded output — `log` is
capped at the last 50 one-line entries) are available for inspection at any
point without needing a `hufi/` branch or write access.

## Teststrategie

`test_command` runs `npm test` (Vitest, the repo's own 15 test files) inside
the cloned workspace. Not yet run for real by this connector pass (see
"bekannte Risiken" — `npm install` was deliberately not exercised against
the real dependency tree in this pass); the mechanism itself is proven
against a disposable local fake repo in
`tests/unit/test_shell_connector.py`/`tests/integration/test_connector_end_to_end.py`.

## Buildstrategie

`build_command` runs `npm run build` (plain `vite build`, not
`verify:hufmanager:canonical`). This is real and non-destructive (writes only
to the cloned workspace's own `dist/`), but per the CI workflow's env block,
a fully successful build likely needs `VITE_SUPABASE_URL`/
`VITE_SUPABASE_PUBLISHABLE_KEY` set (placeholder values are sufficient, per
CI) — not yet verified end-to-end by this connector pass; flagged as a
known gap, not silently assumed to work.

## Sicherheitsgrenzen

Everything from ADR-009/ADR-010, applied to this project specifically:

- Clone source is fixed to the `repo_url` above; a task cannot clone
  anywhere else through this connector.
- Any change requires first switching to a `hufi/…` branch — `add`/`commit`
  on `main` (or any branch named `main`/`master`) is refused, checked at the
  moment of the call, not just at push time.
- Push only ever goes to the exact registered `repo_url`, re-verified against
  the workspace's actual `git remote get-url origin` immediately before
  every push (not just trusted from config).
- `test_command`/`build_command`/`lint_command` are fixed argv from this
  file; a task can only pick *which* one to run (`run_tests`/`run_build`/
  `run_lint`), never influence the command itself.
- No merge, no repo-settings change, no force-push — unimplemented (R3, no
  executor exists), same posture as every other project.
- `Task.dry_run: true` makes push/open_pr a no-op (returns a synthetic `ok`
  describing what would have happened) — used for the live mission below.

## Mission-Beispiel

```json
POST /missions
{
  "outcome": "Analysiere das Repository und erstelle einen technischen Statusbericht als Artifact.",
  "risk_ceiling": "R2",
  "constraints": {"gathered_facts": "... real facts, see this doc's Stack section ..."},
  "steps": [{
    "objective": "Clone passaondigital/hufmanager read-only, write a status report.",
    "agent_id": "integrator",
    "project_id": "hufmanager",
    "dry_run": true,
    "allowed_tools": ["files", "git"],
    "budget_seconds": 200,
    "budget_tokens": 2200,
    "operations": [{"tool": "git", "action": "clone"}],
    "expected_output": "STATUS-REPORT.md"
  }]
}
```

A mission that should also run tests/lint/build and push a draft PR adds
`"git"`+`"shell"`+`"github"` to `allowed_tools` and appends operations
(`shell.run_tests`, `git.add`, `git.commit`, `git.push`,
`github.open_pr`) — see `docs/PHASE2-GIT-PR-WORKFLOW.md`'s mission example
for the exact shape; set `dry_run: false` once Pascal wants a real push/PR
against HufManager. `HUFI_GITHUB_TOKEN` now authenticates both `git.push`
(ADR-011) and `github.open_pr` (ADR-009) — it must be a real, live,
write-scoped credential for the target repo; see "Bekannte Risiken" below
for why this session still could not supply one for `passaondigital/hufmanager`.

## Verifiziert (this pass)

- `uv run pytest -q` — 197/197 green (169 -> 189 -> 197: the connector's 20
  tests, plus 8 more for the ADR-011 push-credential path -- real HTTP
  basic-auth pushes, token-leak checks, fail-closed-when-missing), `ruff
  check`/`format --check` clean, `uv build` clean.
- **Real, live read-only clone of `passaondigital/hufmanager`** through
  `GitTool.clone` (not just raw `git clone` — the actual connector code
  path), inside a throwaway workspace, deleted afterward.
- **Real mission end-to-end**: `POST /missions`-equivalent submission ->
  `integrator` agent -> `hufi-local-router` (real Qwen, not `fake`) ->
  `git.clone` (real, live) -> `files.write_file` -> reviewer `approve` ->
  `completed`. Ran twice (31.2s then 23.4s, `hufi-qwen9` via the primary
  backend, 0 failovers, router `requests_total` 30 -> 32, confirmed via
  `/router/status`); the second run's generated `STATUS-REPORT.md` correctly
  reflects the real gathered facts (stack, package manager, CI, test count)
  with no hallucinated content, mildly truncated at the very end by the
  token budget (cosmetic — the pipeline mechanics are what this run proves,
  not report polish). No push, no PR, no product change; throwaway
  DB/workspace deleted after the run.
- **Real WRITE E2E probe (Phase 3A, 2026-09-07, run 1 — found the push gap):**
  a two-task mission (task 2 depending on task 1, the existing
  sequential-dependency mechanism) drove `integrator`/`hufi-local-router`
  through a real, live `git.clone` -> `git.branch` (`hufi/first-run-e2e`) ->
  `files.write_file` (exactly one new file,
  `docs/HUFIAGENTS-FIRST-RUN.md`) -> `git.status` -> `git.add` ->
  `git.diff` -> `git.commit` -> reviewer `approve` -> `completed` for task 1
  (44.2s total). Verified locally: `git show --stat HEAD` reported exactly
  `1 file changed, 33 insertions(+)` at the correct path; `git remote
  get-url origin` matched the registered `repo_url` exactly. Task 2
  (`git.push`) failed with a raw git auth error — this run is what found
  the credential-path gap now fixed by ADR-011 (below). Confirmed via
  `gh api`/`gh pr list`: nothing reached the real repository.
- **Real WRITE E2E probe, run 2 (2026-09-07, after ADR-011's fix):** same
  mission, re-run unchanged. Task 1 identical, real, live result again
  (44.2s, new commit `bf08bdff`, again exactly 1 file / 33 insertions).
  Task 2 now fails **closed and clean**: `PermissionError: no push
  credential configured; set HUFI_GITHUB_TOKEN` — the credential mechanism
  itself is now real and tested (see ADR-011 and
  `tests/unit/test_git_push_credentials.py`/
  `tests/integration/test_git_push_credentials_e2e.py`, which push for
  real against a local basic-auth-enforcing git server), but no live,
  write-scoped `HUFI_GITHUB_TOKEN` for `passaondigital/hufmanager` was
  available to this session — obtaining one requires either Pascal
  generating a dedicated PAT or explicitly authorizing reuse of an
  existing credential; neither was done, and the host's own personal `gh
  auth` session was deliberately not substituted (see ADR-009/ADR-011).
  Confirmed via `gh api`/`gh pr list` again: still nothing reached the
  real repository. Throwaway DB/workspace deleted after both runs.

## Bekannte Risiken

- **`GitTool.push` had no HTTPS credential-injection mechanism at all —
  found by the Phase 3A run-1 push attempt above.** Fixed in this pass:
  see `docs/DECISIONS.md` ADR-011 (a static, secret-free `GIT_ASKPASS`
  helper, `HUFI_GITHUB_TOKEN` reused, scoped to the one push subprocess).
  Rigorously tested against a real local basic-auth git-HTTP server
  (correct token pushes for real; wrong/missing token fails closed without
  leaking the token in argv/config/remote URL/error text). **Still
  required to close the loop against the real HufManager repo: a real,
  live, write-scoped `HUFI_GITHUB_TOKEN`** — the mechanism is proven, the
  live credential value is not something this session can generate or
  substitute (see run 2 above).
- **`npm install`/`run_tests`/`run_build`/`run_lint` were not exercised
  against the real HufManager dependency tree in this pass** — deliberately,
  to avoid an unbounded-duration `npm install` (large dependency tree, ~80
  edge functions, XXL-AUDIT's memory-constrained host) inside an autonomous
  step without first seeing how long/heavy it actually is. The mechanism is
  proven against a disposable fake repo; running it for real against
  HufManager is a documented next step, not assumed to work.
- **Model output does not see cloned file contents.** The current V1
  architecture passes `task.objective` + `mission.constraints` to the model,
  not actual repository files (`orchestrator/engine.py::_execute`) — the
  live status-report mission worked because the real gathered facts were
  placed in `constraints` by hand. A future "have the model actually read
  the cloned code" capability needs a real context/RAG mechanism over the
  clone, not assumed to exist yet; flagged so nobody assumes today's
  `git.clone` op alone makes cloned content visible to the model.
- **Build likely needs `VITE_SUPABASE_URL`/`VITE_SUPABASE_PUBLISHABLE_KEY`**
  (placeholder values, matching CI) to fully succeed; not yet verified by
  this connector pass — see "Buildstrategie".
- **Stray `bun.lock`/`bun.lockb` in the repo** alongside the canonical
  `package-lock.json` — not acted on, flagged for HufManager's own
  maintainers, out of scope for a read-only connector pass.
- **Two Node major versions** (host 22 vs. CI-pinned 20) — not yet proven to
  matter, not yet tested against a real `npm test`/`build` run.
- **HufManager's own `AGENTS.md`/`CODEXTODO.md` governance model** is
  separate from HufiAgents' risk/approval engine (see "Stack" above) — any
  future non-read-only mission against this repo should account for both,
  not assume HufiAgents' approval alone is sufficient sign-off in the sense
  HufManager's own process means.

## Independent Codex review correction (2026-09-07)

The historical verification above is superseded by `CODEX-REVIEW-PHASE3A.md` and
ADR-012. Fetch-origin comparison alone did not constrain pushurl; fixed npm argv
was not a sandbox; generic regex redaction did not protect opaque echoed tokens.
ADR-013 now runs npm commands only in a verified Bubblewrap boundary and contains
credential process descendants on hard parent death. A fresh real clone/documentation
commit and two-stage reviewer/dry-run-push/PR mission succeeded independently. No real
HufManager push or PR was attempted. Actual test/build/lint status is recorded in the
Phase 3A review; dependency installation is not performed outside the netless sandbox.
