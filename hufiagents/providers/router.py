from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderChoice:
    provider_id: str
    reason: str


def select_provider(task, agent, registry_health, default="hufi-local-router"):
    candidate = task.preferred_provider or default
    permitted = agent.capabilities.get("providers", [])
    if candidate not in permitted:
        raise PermissionError("provider outside agent capabilities")
    health = registry_health.get(candidate)
    if not health or not health.available:
        raise ConnectionError(f"provider unavailable: {candidate}")
    # No silent fake fallback and no automatic transfer of local data to remote models.
    return ProviderChoice(
        candidate,
        "explicit task preference"
        if task.preferred_provider
        else "configured local-first default; no external fallback",
    )
