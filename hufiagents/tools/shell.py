from hufiagents.contracts import Risk
from hufiagents.tools.process import run_process

# Closed operations: no supplied executable, flags, command text or package scripts.
COMMANDS = {"pwd": ["/bin/pwd"], "git_version": ["/usr/bin/git", "--version"]}
# Project-scoped commands (docs/DECISIONS.md ADR-010): the argv always comes
# from the server-side project registry, never from call.params -- a task
# only ever selects *which* pre-registered command to run, never its content.
PROJECT_ACTIONS = {
    "run_tests": "test_command",
    "run_build": "build_command",
    "run_lint": "lint_command",
}


class ShellTool:
    id = "shell"

    def __init__(self, workspace, timeout=30, *, project=None, project_timeout=None):
        self.workspace, self.timeout = workspace, timeout
        self.project = project
        self.project_timeout = project_timeout or timeout

    async def classify(self, action, params):
        if action == "run_command" and params.get("command") in COMMANDS:
            if set(params) - {"command", "target"}:
                raise PermissionError("extra shell parameters forbidden")
            return Risk.R0
        if action in PROJECT_ACTIONS:
            return Risk.R1
        text = str(params).lower()
        return Risk.R4 if any(x in text for x in ["rm ", "dd ", "mkfs"]) else Risk.R3

    async def execute(self, call):
        risk = await self.classify(call.action, call.params)
        if call.action in PROJECT_ACTIONS:
            if risk != Risk.R1:
                raise PermissionError("project command disabled")
            if not self.project:
                raise PermissionError("no project configured")
            argv = getattr(self.project, PROJECT_ACTIONS[call.action])
            if not argv:
                raise PermissionError(f"{call.action} is not configured for this project")
            return await run_process(argv, self.workspace, call, self.project_timeout)
        if risk != Risk.R0:
            raise PermissionError("arbitrary shell disabled until an OS sandbox is provided")
        return await run_process(
            COMMANDS[call.params["command"]], self.workspace, call, self.timeout
        )
