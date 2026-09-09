from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderChoice:
    provider_id: str
    reason: str


def select_provider(task, agent, registry_health, default="hufi-local-router"):
    """Select the provider for a task according to the model precedence policy.

    Precedence (highest → lowest):
      1. Explicit task-level override  (task.preferred_provider)
      2. Agent model policy            (agent.model_preference)
      3. Global router default         (default)

    All choices are constrained by:
      - Agent capabilities["providers"] whitelist (PermissionError if violated).
      - Provider health (ConnectionError if unavailable).
      - No silent external fallback — local-first, no automatic data transfer.
    """
    permitted = agent.capabilities.get("providers", [])

    # --- Resolve candidate in precedence order ---
    if task.preferred_provider:
        candidate = task.preferred_provider
        reason = "explicit task preference"
    elif getattr(agent, "model_preference", None):
        candidate = agent.model_preference
        reason = "agent model policy"
    else:
        candidate = default
        reason = "configured local-first default; no external fallback"

    # --- Capability whitelist check ---
    if candidate not in permitted:
        raise PermissionError(f"provider '{candidate}' is outside agent capabilities whitelist")

    # --- Health check ---
    health = registry_health.get(candidate)
    if not health or not health.available:
        raise ConnectionError(f"provider unavailable: {candidate}")

    # No silent fake fallback and no automatic transfer of local data to remote models.
    return ProviderChoice(candidate, reason)
