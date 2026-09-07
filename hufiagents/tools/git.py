import os
import re
import stat
from pathlib import Path

from hufiagents.contracts import Risk
from hufiagents.tools.git_security import validate_metadata, validate_remote
from hufiagents.tools.process import run_process

HUFI_BRANCH = re.compile(r"hufi/[a-zA-Z0-9_-]{1,80}")
ASKPASS_SCRIPT = Path(__file__).with_name("git-askpass.sh")


class GitTool:
    id = "git"

    def __init__(
        self,
        workspace,
        timeout=30,
        *,
        remote_url="",
        project=None,
        dry_run=False,
        clone_timeout=None,
        push_token="",
    ):
        self.workspace, self.timeout = workspace, timeout
        self.remote_url, self.project, self.dry_run = remote_url, project, dry_run
        self.clone_timeout = clone_timeout or timeout
        self.push_token = push_token

    async def classify(self, action, params):
        if action in {"force_push", "reset", "clean"} or params.get("branch") in {"main", "master"}:
            return Risk.R3
        if action == "push":
            return Risk.R2
        if action in {
            "init",
            "clone",
            "status",
            "diff",
            "log",
            "branch",
            "add",
            "commit",
            "remote_add",
        }:
            return Risk.R0 if action in {"status", "diff", "log"} else Risk.R1
        return Risk.R3

    async def execute(self, call):
        action, params = call.action, call.params
        extra_env = None
        if action not in {
            "init",
            "clone",
            "status",
            "diff",
            "log",
            "branch",
            "add",
            "commit",
            "remote_add",
            "push",
        }:
            raise PermissionError("external or destructive git operation disabled in V1")
        metadata = self.workspace.root / ".git"
        if metadata.exists() or metadata.is_symlink():
            validate_metadata(self.workspace.root)
        elif action not in {"init", "clone"}:
            raise PermissionError("Git operates only on its own workspace repository")
        argv = [
            "/usr/bin/git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "credential.helper=",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=HufiAgents",
            "-c",
            "user.email=hufiagents@localhost",
        ]
        if action == "init":
            argv += ["init", "--initial-branch=hufi/mission", "."]
        elif action == "clone":
            if not self.project:
                raise PermissionError("no project configured for clone")
            # Any caller-supplied params are ignored entirely: only the
            # registry's repo_url can ever be cloned, so a task can never
            # fetch from an attacker-chosen source (docs/DECISIONS.md ADR-010).
            validate_remote(self.project.repo_url)
            argv += ["clone", "--no-hardlinks", "--single-branch", "--", self.project.repo_url, "."]
            return await run_process(argv, self.workspace, call, self.clone_timeout)
        elif action == "status":
            argv += ["status", "--short"]
        elif action == "diff":
            argv += ["diff", "--no-ext-diff", "--no-textconv"]
        elif action == "log":
            # Bounded: at most 50 one-line entries, no pager/decoration noise.
            argv += ["log", "--oneline", "--no-decorate", "-n", "50"]
        elif action == "branch":
            branch = params.get("branch", "")
            if not HUFI_BRANCH.fullmatch(branch):
                raise PermissionError("branch must be a bounded hufi/ name")
            argv += ["switch", "-c", branch]
        elif action in {"add", "commit"}:
            await self._require_unprotected_branch(call)
            if action == "add":
                target = params["path"]
                self.workspace.path(target)
                argv += ["--literal-pathspecs", "add", "--", target]
            else:
                message = params.get("message", "HufiAgents workspace result")
                if len(message) > 200 or "\n" in message:
                    raise ValueError("commit message must be one bounded line")
                argv += ["commit", "-m", message]
        elif action == "remote_add":
            if self.project:
                raise PermissionError("origin is set automatically by clone for a project task")
            if not self.remote_url:
                raise PermissionError("no git remote configured; set HUFI_GIT_REMOTE_URL")
            # Any caller-supplied params are ignored entirely: only the
            # server-configured remote can ever be wired in, so a task can
            # never redirect a push destination.
            validate_remote(self.remote_url)
            argv += ["remote", "add", "origin", self.remote_url]
        else:
            target_remote = self.project.repo_url if self.project else self.remote_url
            if not target_remote:
                raise PermissionError("no git remote configured; set HUFI_GIT_REMOTE_URL")
            protocol = validate_remote(target_remote)
            origin = await self._origin_url(call)
            if origin != target_remote:
                raise PermissionError("origin does not match the configured/allowlisted remote")
            branch = await self._current_branch(call)
            if not HUFI_BRANCH.fullmatch(branch) or (
                self.project and branch == self.project.default_branch
            ):
                raise PermissionError("refusing to push a non-hufi/ or detached branch")
            if self.dry_run:
                return call.model_copy(
                    update={
                        "result_status": "ok",
                        "exit_code": 0,
                        "result_summary": f"dry-run: push of {branch} to {origin} skipped",
                    }
                )
            # Fail closed before spawning the push if no push credential is
            # configured (docs/DECISIONS.md ADR-011). The token never touches
            # argv/git config/the remote URL -- only this one subprocess's
            # env, via a static, secret-free GIT_ASKPASS helper.
            if not self.push_token:
                raise PermissionError("no push credential configured; set HUFI_GITHUB_TOKEN")
            if protocol != "file":
                info = ASKPASS_SCRIPT.lstat()
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_mode & 0o022
                    or not os.access(ASKPASS_SCRIPT, os.X_OK)
                    or info.st_nlink != 1
                ):
                    raise PermissionError("unsafe askpass installation")
                extra_env = {
                    "GIT_ASKPASS": str(ASKPASS_SCRIPT),
                    "HUFI_GIT_PUSH_TOKEN": self.push_token,
                }
            # An explicit destination and full refspec avoid remote pushurl,
            # configured refspecs and upstream inference. No force or tags.
            argv += [
                "-c",
                "http.followRedirects=false",
                "-c",
                "http.sslVerify=true",
                "-c",
                "protocol.allow=never",
                "-c",
                f"protocol.{protocol}.allow=always",
                "push",
                "--no-verify",
                "--recurse-submodules=no",
                "--",
                target_remote,
                f"refs/heads/{branch}:refs/heads/{branch}",
            ]
        return await run_process(argv, self.workspace, call, self.timeout, extra_env=extra_env)

    async def _require_unprotected_branch(self, call):
        branch = await self._current_branch(call)
        protected = {"main", "master"}
        if self.project:
            protected.add(self.project.default_branch)
        if branch in protected or not HUFI_BRANCH.fullmatch(branch):
            raise PermissionError("switch to a hufi/ branch before making changes")

    async def _current_branch(self, call):
        result = await run_process(
            # symbolic-ref (not rev-parse --abbrev-ref) so this resolves even
            # on a branch with zero commits yet (the normal init -> add ->
            # commit order); it also correctly fails closed on detached HEAD.
            ["/usr/bin/git", "symbolic-ref", "--short", "HEAD"],
            self.workspace,
            call,
            self.timeout,
        )
        if result.result_status != "ok":
            raise PermissionError("cannot determine current branch")
        return result.result_summary.strip()

    async def _origin_url(self, call):
        result = await run_process(
            ["/usr/bin/git", "remote", "get-url", "origin"], self.workspace, call, self.timeout
        )
        if result.result_status != "ok":
            raise PermissionError("no origin remote configured")
        return result.result_summary.strip()
