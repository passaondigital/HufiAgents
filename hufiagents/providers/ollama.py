"""Optional HTTP adapter; never installs, pulls or manages a model/server."""

import httpx

from hufiagents.providers.base import CompletionResult, ProviderHealth


class OllamaProvider:
    id = "ollama"

    def __init__(self, base_url, model="qwen3:8b", timeout=180, transport=None):
        self.base_url, self.model = base_url.rstrip("/"), model
        self.timeout, self.transport = timeout, transport

    async def health(self):
        try:
            async with httpx.AsyncClient(transport=self.transport, trust_env=False) as client:
                response = await client.get(self.base_url + "/api/tags", timeout=5)
                response.raise_for_status()
                found = any(m["name"] == self.model for m in response.json().get("models", []))
                return ProviderHealth(available=found, reason="configured model inventory")
        except (httpx.HTTPError, ValueError, KeyError):
            return ProviderHealth(available=False, reason="Ollama unavailable")

    async def complete(self, request):
        async with httpx.AsyncClient(transport=self.transport, trust_env=False) as client:
            response = await client.post(
                self.base_url + "/api/chat",
                timeout=self.timeout,
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "messages": [
                        {"role": "user", "content": request.objective + "\n" + request.context}
                    ],
                    "options": {"num_predict": request.max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            return CompletionResult(
                text=data["message"]["content"], model=self.model, tokens=data.get("eval_count", 0)
            )
