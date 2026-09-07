from hufiagents.providers.base import CompletionRequest, CompletionResult, ProviderHealth


class FakeProvider:
    id = "fake"

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(text=f"# Mission result\n\n{request.objective}\n", model="fake-v1")

    async def health(self):
        return ProviderHealth(available=True, reason="deterministic offline provider")
