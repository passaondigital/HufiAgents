# V1.3 Workforce Builder

Stacked on PR #32 (Visible Execution / Automatic Work Evidence).

## Overview

The Workforce Builder provides a safe, audited mechanism to create and configure persistent digital employees ("agents") through a single structured provisioning request. It enforces hard privilege ceilings, rejects raw secrets, records full profile history, and uses the normal agent runtime without any special bypass paths.

## Provisioning

**Endpoint:** `POST /workforce/provision`

A single request creates an agent with:

- Profile (display name, role, description, mission)
- Risk ceiling (bounded by caller's ceiling)
- Capabilities whitelist (bounded by caller's capabilities)
- Model policy (preferred provider, external fallback flag)
- External budget (tokens/spend ceiling)
- Initial profile history snapshot (version 1)

### Atomicity

Provisioning uses the standard `store.transaction()` context manager. All validation happens **before** any persistence:

1. Secret boundary check (no raw secrets in any field)
2. Capability ceiling check (requested ⊆ caller capabilities)
3. Risk ceiling check (requested ≤ caller ceiling)
4. Idempotency resolution (return existing agent if key matches)
5. Agent creation + profile history + audit log (all in one transaction)

If any check fails, nothing is written. There is no partial-creation state.

## Profile History

Every profile change records a versioned history entry in `agent_profile_history`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | UUID |
| `agent_id` | str | FK → agents.id |
| `version` | int | Monotonically increasing (1, 2, 3…) |
| `changed_at` | datetime | UTC timestamp |
| `changed_by` | str | Actor identifier |
| `summary` | str | Human-readable description |
| `changes` | JSON | `{before: {...}, after: {...}}` |
| `snapshot` | JSON | Full agent state at this version |

The history is **append-only** and always returned sorted by version ascending. Raw secrets are rejected before any history entry is written.

### Version lifecycle

- **Version 1:** Created at initial provisioning
- **Version N:** Added on every `update_profile()` call
- **Archive version:** Added when `archive_agent()` is called

## Privilege Ceilings

### Capability Guard

```
caller capabilities:   {"providers": ["local"], "tools": ["files"]}
request capabilities:  {"providers": ["local", "openai"]}

→ REJECTED — openai not in caller whitelist
```

The `_subset(child, parent)` function checks recursively:
- Dict values: same recursive check
- List values: set subset check
- Scalar values: equality

### Risk Ceiling Guard

```
caller ceiling:  R1
request ceiling: R3

→ REJECTED (R3 > R1)
```

Risk order: R0 < R1 < R2 < R3 < R4

Equal ceiling is allowed. Only strict escalation is rejected.

## Organization ≠ Permission

Assigning an agent to a team or project **never** grants:

- Additional capabilities or tools
- Additional risk ceiling
- Additional memory scopes
- Credential access
- Connector scopes

Team/project assignment is recorded via audit log only. It has no effect on the agent's security properties.

## Secret Rejection

Provisioning rejects raw secrets at the boundary before any DB access:

**Rejected field names** (case-insensitive): `api_key`, `secret`, `password`, `token`, `bearer`, `private_key`, `authorization`

**Rejected value patterns:**
- JWT/Bearer tokens: `Bearer eyJ...`
- OpenAI-style keys: `sk-[20+ chars]`
- GitHub PATs: `ghp_[36 chars]`

**Allowed:** `credential_ref: "cred://vault/my-creds"` — opaque handles are fine.

Secrets are checked recursively in dicts, lists, and string values. The same check applies to `update_profile()` changes.

Raw secrets **never** appear in:
- agent profile / profile history
- audit log
- work evidence
- memory / skills

## Model Policy Precedence

Provider selection follows this strict precedence (highest → lowest):

1. **Task-level override** (`task.preferred_provider`) — explicit caller choice
2. **Agent model policy** (`agent.model_preference`) — per-agent default
3. **Global/default router** (`settings.default_provider`) — system fallback

All choices are bounded by:
- Agent capabilities `providers` whitelist (PermissionError if violated)
- Provider health check (ConnectionError if unavailable)
- No silent external fallback — local-first

### Budget = 0 enforcement

If `external_budget = 0` is set, the router's capability check prevents any external provider from being selected (the external provider must be absent from the agent's `capabilities.providers`). There is no paid call without capability whitelisting.

## Skills, Memory, Reviewer

### Skills

`assign_skill(agent_id, skill_id)` verifies both agent and skill exist before logging. An unknown skill raises `KeyError`.

### Memory

Memory scopes are referenced by scope type + scope id. Unauthorized scopes are rejected by the memory service — the builder does not grant memory access directly.

### Reviewer

`set_reviewer(agent_id, reviewer_agent_id)` verifies both agents exist and are active. **Reviewer assignment grants no additional execution rights or capabilities.** It is recorded as an audit log entry only.

## Participation

Participation state (`ACTIVE`, `LISTENING`, `SLEEPING`) is managed via `set_participation(agent_id, room_id, state)`. It records/updates a `RoomParticipant` row.

Archived agents cannot be reactivated. The archive state is permanent through this API.

## Idempotency

If `idempotency_key` is provided:
- The agent ID is derived deterministically: `"agent-" + sha256(key)[:16]`
- If an agent with that ID already exists and has the **same role**, it is returned unchanged (no mutation, no duplicate history)
- If an agent with that ID exists but has a **different role**, `ValueError` is raised

Same key + same role = exactly one agent, no duplicate team/project/skill memberships, no profile version explosion.

## Visible Evidence

Successful provisioning emits truthful work evidence events:

| Event | Trigger |
|-------|---------|
| `agent_created` | Successful provisioning |
| `provisioning_completed` | End of provisioning transaction |
| `agent_updated` | Successful `update_profile()` |
| `agent_archived` | Successful `archive_agent()` |

**Failed provisioning emits no evidence.** All evidence is emitted only after the transaction commits successfully.

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workforce/provision` | Create/configure a digital employee |
| `PATCH` | `/workforce/agents/{id}/profile` | Update mutable profile fields |
| `GET` | `/workforce/agents/{id}/profile-history` | Retrieve version history |

Caller identity is provided via `x-caller-agent-id` header. Unknown callers default to empty capabilities + R1 ceiling (cannot escalate).

## Known Limitations

1. **Team/project memberships are log-only.** V1 schema has no join table for agent↔team or agent↔project beyond the single `agent.project_id` field. Multiple project assignments are tracked in audit logs but not in a queryable FK table.

2. **`external_budget` is policy, not runtime enforcement.** Budget is recorded via audit log. The router enforces it indirectly through the capabilities whitelist. True token-level budget enforcement requires a separate billing/metering layer.

3. **`reviewer_agent_id` is advisory.** The reviewer is recorded in the audit log and future tooling can read it. The current runtime does not automatically route results through the reviewer agent.

4. **`memory_scopes` are advisory.** The builder records requested scopes but does not create or validate scope entries in the memory store.

5. **No HTTP archive endpoint yet.** `archive_agent()` is accessible through `update_profile(agent_id, {"status": "archived"})` as a workaround. A dedicated `POST /workforce/agents/{id}/archive` endpoint is a natural next step.

6. **Profile history ordering.** The `agent_profile_history` table has no `created_at` column, so the generic repository falls back to UUID ordering. `get_profile_history()` sorts by `version` in Python after the query to guarantee determinism.
