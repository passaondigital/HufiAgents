from hufiagents.contracts import Risk, ToolResult, now
from hufiagents.redaction import redact


class FilesTool:
    id = "files"

    def __init__(self, workspace):
        self.workspace = workspace

    async def classify(self, action, params):
        self.workspace.path(params.get("target", ""))
        if action not in {"read_file", "write_file"}:
            raise PermissionError("unsupported files action")
        return Risk.R0 if action == "read_file" else Risk.R1

    async def execute(self, call):
        await self.classify(call.action, {**call.params, "target": call.target})
        summary = (
            self.workspace.read(call.target)
            if call.action == "read_file"
            else self.workspace.create(call.target, call.params["content"])
        )
        return ToolResult(
            **{
                **call.model_dump(),
                "result_status": "ok",
                "result_summary": redact(summary),
                "executed_at": now(),
            }
        )
