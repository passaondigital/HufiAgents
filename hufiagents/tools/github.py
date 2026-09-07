import re
from tempfile import TemporaryDirectory

from hufiagents.contracts import Risk
from hufiagents.tools.git_security import validate_metadata
from hufiagents.tools.process import run_process

HUFI_BRANCH = re.compile(r"hufi/[a-zA-Z0-9_-]{1,80}")


class GitHubTool:
    """Draft-PR-only bridge to `gh` (docs/ARCHITECTURE.md Sec6.4). `repo`,
    `base_branch` and `token` are always server-configured (Settings), never
    taken from call.params, so a task can never redirect a PR to another
    repository or exfiltrate a token. `GH_TOKEN` is passed only as subprocess
    env, never persisted; it is layered onto run_process's isolated env, so
    the host's own logged-in `gh` session (a real, separate credential) is
    never read or exposed. Merge/close/repo-settings stay unimplemented -- R3,
    no executor exists for them in V1, matching the shell/git R3 posture."""

    id = "github"

    def __init__(
        self, workspace, timeout=30, *, repo="", base_branch="main", token="", dry_run=False
    ):
        self.workspace, self.timeout = workspace, timeout
        self.repo, self.base_branch, self.token, self.dry_run = repo, base_branch, token, dry_run

    async def classify(self, action, params):
        return Risk.R2 if action == "open_pr" else Risk.R3

    async def execute(self, call):
        if call.action != "open_pr":
            raise PermissionError("only draft PR creation is implemented in V1")
        if not self.repo:
            raise PermissionError("GitHub integration not configured")
        if not self.token and not self.dry_run:
            raise PermissionError("GitHub integration not configured")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+", self.repo):
            raise PermissionError("invalid configured GitHub repository")
        validate_metadata(self.workspace.root)
        branch = await self._current_branch(call)
        if not HUFI_BRANCH.fullmatch(branch) or branch == self.base_branch:
            raise PermissionError("refusing to open a PR from a non-hufi/ or detached branch")
        title = call.params.get("title") or f"HufiAgents: {branch}"
        body = call.params.get("body") or "Opened by HufiAgents (draft, review required)."
        if len(title) > 200 or "\n" in title:
            raise ValueError("PR title must be one bounded line")
        if len(body) > 4000:
            raise ValueError("PR body exceeds bounded size")
        if self.dry_run:
            target = f"{self.repo}@{self.base_branch}"
            return call.model_copy(
                update={
                    "result_status": "ok",
                    "exit_code": 0,
                    "result_summary": f"dry-run: PR {branch} -> {target} skipped",
                }
            )
        argv = [
            "/usr/bin/gh",
            "pr",
            "create",
            "--repo",
            self.repo,
            "--base",
            self.base_branch,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
            "--draft",
        ]
        with TemporaryDirectory(prefix="hufi-gh-") as config_dir:
            return await run_process(
                argv,
                self.workspace,
                call,
                self.timeout,
                extra_env={
                    "GH_TOKEN": self.token,
                    "GH_PROMPT_DISABLED": "1",
                    "NO_COLOR": "1",
                    "GH_CONFIG_DIR": config_dir,
                    "GH_HOST": "github.com",
                },
            )

    async def _current_branch(self, call):
        result = await run_process(
            ["/usr/bin/git", "symbolic-ref", "--short", "HEAD"],
            self.workspace,
            call,
            self.timeout,
        )
        if result.result_status != "ok":
            raise PermissionError("cannot determine current branch")
        return result.result_summary.strip()
