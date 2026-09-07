# Phase 2 — Git push / GitHub PR workflow

See `docs/DECISIONS.md` ADR-009 for the design rationale. This is the
operator-facing setup and usage note.

## What this adds

- `GitTool.remote_add` / `GitTool.push` — configure and push to a single,
  server-configured `origin` remote.
- `GitHubTool.open_pr` — `gh pr create --draft` against a single,
  server-configured repository.
- A new Agent Registry entry, `integrator` (`default_risk_ceiling=R2`). The
  shipped `builder` agent (`R1`) is unchanged and cannot reach either action,
  even if a remote/repo is configured — see ADR-009.

Both tool actions are R2 and only auto-execute because
`config/risk_policy.yaml`'s `r2_auto_allow` explicitly lists `git.push` and
`github.open_pr` (`docs/ARCHITECTURE.md` Sec8's documented mechanism, not a
new gateway behavior).

## Turning it on

All disabled by default. Set in `.env` (never commit real values):

```sh
HUFI_GIT_REMOTE_URL=<a git remote this box may push to>
HUFI_GITHUB_REPO=<owner/repo>
HUFI_GITHUB_BASE_BRANCH=main
HUFI_GITHUB_TOKEN=<a scoped PAT for HufiAgents, not your personal `gh auth` session>
```

`HUFI_GITHUB_TOKEN` is intentionally separate from the host's own
`gh auth login` session (`passaondigital`, per `docs/XXL-AUDIT.md`) — the
tool subprocess never reads `~/.config/gh/hosts.yml`; it only receives
`GH_TOKEN` as an isolated subprocess env var. Scope the PAT to the one target
repo (`repo` scope, that repo only) rather than reusing a broad personal
token.

## Requesting it in a mission

Only a task that explicitly names `agent_id: "integrator"` can reach
`git.push`/`github.open_pr` — this is per-task opt-in, not a global switch:

```json
POST /missions
{
  "outcome": "ship a small fix",
  "risk_ceiling": "R2",
  "steps": [{
    "objective": "add a note and open a draft PR",
    "agent_id": "integrator",
    "allowed_tools": ["files", "git", "github"],
    "operations": [
      {"tool": "git", "action": "init"},
      {"tool": "files", "action": "write_file", "target": "note.md", "params": {"content": "..."}},
      {"tool": "git", "action": "add", "params": {"path": "note.md"}},
      {"tool": "git", "action": "commit", "params": {"message": "add note"}},
      {"tool": "git", "action": "remote_add"},
      {"tool": "git", "action": "push"},
      {"tool": "github", "action": "open_pr", "params": {"title": "...", "body": "..."}}
    ]
  }]
}
```

An unknown `agent_id` is rejected at submit time (409), before any task is
persisted or dispatched.

## Boundaries (unchanged from Core V1, still enforced)

- Branch must match `hufi/[a-zA-Z0-9_-]{1,80}`; push/PR from `main`/`master`
  or a detached HEAD is refused (`GitTool.classify` already hard-R3s
  `main`/`master` branches; push/open_pr additionally re-check the actual
  current branch at execute time).
- `remote_add`/`open_pr` always use the server-configured remote/repo/token —
  any `url`/`repo`/`token` in a task's `params` is ignored, never read.
- `git push` never carries `--force`; `merge`/`close`/repo-settings actions
  on GitHub remain unimplemented (R3, `PermissionError`, no executor exists).
- Cloning an arbitrary external repository into a mission workspace is **not**
  implemented by this change — `git init` still only creates a fresh, empty
  workspace-local repo (ADR-005 workspace isolation is unchanged). Wiring a
  real project's existing repository into a mission workspace (e.g. the
  HufManager connector) is separate, later work.

## Verification performed for this change

- `uv run pytest -q` — 169/169 green (was 156; 13 added:
  `tests/unit/test_git_pr_workflow.py`,
  `tests/integration/test_git_pr_workflow_e2e.py`), including a real push to
  a local bare repo and a real subprocess branch check, no network required.
- `ruff check` / `ruff format --check` — clean.
- `uv build` — clean.
- Non-mutating live check only (`gh api user`, `gh repo view
  passaondigital/HufiAgents`) confirms `gh` auth and repo reachability; no
  real draft PR was opened against a production repository by this change —
  that requires Pascal to set `HUFI_GITHUB_REPO`/`HUFI_GITHUB_TOKEN` and
  request it explicitly.
