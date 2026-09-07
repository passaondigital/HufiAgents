import re

from hufiagents.contracts import Risk
from hufiagents.tools.process import run_process


class GitTool:
    id = "git"

    def __init__(self, workspace, timeout=30):
        self.workspace, self.timeout = workspace, timeout

    async def classify(self, action, params):
        if action in {"force_push", "reset", "clean"} or params.get("branch") in {"main", "master"}:
            return Risk.R3
        if action == "push":
            return Risk.R2
        if action in {"init", "status", "diff", "branch", "add", "commit"}:
            return Risk.R0 if action in {"status", "diff"} else Risk.R1
        return Risk.R3

    async def execute(self, call):
        action, params = call.action, call.params
        if action not in {"init", "status", "diff", "branch", "add", "commit"}:
            raise PermissionError("external or destructive git operation disabled in V1")
        metadata = self.workspace.root / ".git"
        if metadata.exists():
            if metadata.is_symlink() or not metadata.is_dir():
                raise PermissionError("external Git directory forbidden")
            for entry in metadata.rglob("*"):
                if entry.is_symlink():
                    raise PermissionError("Git metadata symlinks forbidden")
            config = metadata / "config"
            if config.exists():
                text = config.read_text().lower()
                if any(
                    word in text
                    for word in ["include", "filter", "fsmonitor", "worktree", "sshcommand"]
                ):
                    raise PermissionError("unsafe Git configuration")
        elif action != "init":
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
        elif action == "status":
            argv += ["status", "--short"]
        elif action == "diff":
            argv += ["diff", "--no-ext-diff", "--no-textconv"]
        elif action == "branch":
            branch = params.get("branch", "")
            if not re.fullmatch(r"hufi/[a-zA-Z0-9_-]{1,80}", branch):
                raise PermissionError("branch must be a bounded hufi/ name")
            argv += ["switch", "-c", branch]
        elif action == "add":
            target = params["path"]
            self.workspace.path(target)
            argv += ["--literal-pathspecs", "add", "--", target]
        else:
            message = params.get("message", "HufiAgents workspace result")
            if len(message) > 200 or "\n" in message:
                raise ValueError("commit message must be one bounded line")
            argv += ["commit", "-m", message]
        return await run_process(argv, self.workspace, call, self.timeout)
