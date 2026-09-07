from hufiagents.contracts import Risk
from hufiagents.tools.process import run_process

# Closed operations: no supplied executable, flags, command text or package scripts.
COMMANDS = {"pwd": ["/bin/pwd"], "git_version": ["/usr/bin/git", "--version"]}


class ShellTool:
    id = "shell"

    def __init__(self, workspace, timeout=30):
        self.workspace, self.timeout = workspace, timeout

    async def classify(self, action, params):
        if action == "run_command" and params.get("command") in COMMANDS:
            if set(params) - {"command", "target"}:
                raise PermissionError("extra shell parameters forbidden")
            return Risk.R0
        text = str(params).lower()
        return Risk.R4 if any(x in text for x in ["rm ", "dd ", "mkfs"]) else Risk.R3

    async def execute(self, call):
        if await self.classify(call.action, call.params) != Risk.R0:
            raise PermissionError("arbitrary shell disabled until an OS sandbox is provided")
        return await run_process(
            COMMANDS[call.params["command"]], self.workspace, call, self.timeout
        )
