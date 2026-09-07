from hufiagents.contracts import Risk


class ReservedTool:
    def __init__(self, identifier):
        self.id = identifier

    async def classify(self, action, params):
        return Risk.R3

    async def execute(self, call):
        raise NotImplementedError(f"{self.id} is reserved for a later sandboxed integration")
