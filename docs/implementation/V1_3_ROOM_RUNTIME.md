# V1.3 Room -> Runtime Bridge Architecture & Implementation

## Overview

The Room -> Runtime Bridge establishes a generic, persistent communication and execution layer between team/project chat rooms (`ChatRoom`) and the underlying HufiAgents Orchestrator/Workforce runtime.

When a user posts a message to a team or project room (e.g. `"Prüft bitte den aktuellen Release."`), the system persists the message, resolves @mentions and room membership against the real agent graph, dispatches real `Mission` and `Task` contracts to the existing `Orchestrator`, and asynchronously posts execution results back into the originating room upon completion.

---

## Key Design Principles

1. **No Second Orchestrator**: Mission submission goes directly through `Orchestrator.submit()`. No shadow scheduler or duplicate event loop is created.
2. **No Second Agent Framework**: Multi-agent fan-out reuses standard `MissionCreate` and `TaskSpec` primitives. Independent tasks run concurrently within the orchestrator's existing semaphore budget.
3. **No Fake States**: Room participation states (`active`, `listening`, `sleeping`, `left`) reflect execution availability hints only. No simulated typing indicators or fake activity loops.
4. **Strict Security Boundaries**: Room membership and @mentions NEVER raise risk ceilings, grant capabilities, expand connector scopes, or bypass approvals. Redaction is enforced prior to message persistence.

---

## Architecture & Flow

```
+-------------------------------------------------------------------------------+
|                                  ChatRoom                                     |
+-------------------------------------------------------------------------------+
       |                                                                ^
       | 1. POST /rooms/{id}/messages                                   | 6. Fan-In Result
       v                                                                |    (post_result)
+-------------------------------------------------------------------------------+
|                            RoomMessageService                                 |
| - Redacts raw content before persistence                                     |
| - Resolves @mentions against real Agent Registry                             |
| - Reports unknown mentions in response                                       |
+-------------------------------------------------------------------------------+
       |
       | 2. POST /rooms/{id}/messages/{msg_id}/dispatch
       v
+-------------------------------------------------------------------------------+
|                             Dispatch Bridge                                   |
| - Precedence: @mentions > ACTIVE room participants                            |
| - Filters out SLEEPING and LEFT participants                                  |
| - Creates independent Mission per target agent (Parallel Fan-Out)             |
+-------------------------------------------------------------------------------+
       |
       | 3. Orchestrator.submit(MissionCreate)
       v
+-------------------------------------------------------------------------------+
|                            HufiAgents Orchestrator                            |
| - Task planning & risk review (Reviewer)                                     |
| - Approval gating (if R3/R4 or policy required)                              |
| - Parallel execution within max_concurrent_tasks                              |
+-------------------------------------------------------------------------------+
       |
       | 4. Mission completes / fails
       v
+-------------------------------------------------------------------------------+
|                           Orchestrator Tick Scan                              |
| - Calls notify_mission_outcome() for room-linked missions                     |
| - Posts system result message back to originating ChatRoom                    |
+-------------------------------------------------------------------------------+
```

---

## 1. Message Persistence (`RoomMessage`)

Every room message is stored in SQLite table `room_messages`:

- `id`: Unique identifier (UUID).
- `room_id`: Foreign key referencing `chat_rooms.id`.
- `sender_type`: `"user"`, `"agent"`, or `"system"`.
- `sender_id`: ID of the sender.
- `content`: Message text, always redacted via `hufiagents.redaction.redact` before storage.
- `mention_agent_ids`: JSON array of resolved agent IDs found in @mentions.
- `mission_id`: Linkage to the dispatched `Mission` contract (nullable).
- `task_id`: Linkage to a specific `Task` contract (nullable).
- `parent_message_id`: Threading link to a parent message (nullable).
- `created_at`: UTC timestamp.
- `status`: `"visible"`, `"redacted"`, or `"deleted"`.

Messages survive API process restarts, store reconstructions, and client reloads.

---

## 2. Participant & Participation Management (`RoomParticipant`)

Tracks membership of agents within rooms (`room_participants` table):

- `participation_state`:
  - `active`: Eligible for auto-dispatch when no explicit @mentions are present.
  - `listening`: Observes the room; executed ONLY when explicitly @mentioned.
  - `sleeping`: Not auto-dispatched; requires explicit @mention.
  - `left`: Agent has left the room; never dispatched.

> [!IMPORTANT]
> Participation state is an **execution hint only**. It does NOT alter an agent's default risk ceiling, tool access, or authorization.

---

## 3. Mention Parsing & Dispatch Resolution

### Parsing
- Pattern: `@([\w-]{1,200})`
- Mentions are resolved against `Store.agents` before redaction.
- **Unknown Mentions**: If an @mention does not match a real agent in the database, it is recorded in `unknown_mentions` and returned in the HTTP response. It does NOT throw a generic 500 error or silently create a fake agent.

### Dispatch Precedence
1. **Explicit @mentions**: Dispatches tasks to resolved agents whose participation state is `active` or `listening`.
2. **Room Participants**: If no explicit @mentions exist, dispatches to all `active` participants in the room.
3. **Default / Generic**: If no targets are resolved, submits a single generic `Mission` without explicit agent assignment (falling back to default `builder`).

---

## 4. Message -> Mission & Parallel Fan-Out

When dispatching via `POST /rooms/{room_id}/messages/{message_id}/dispatch`:

1. The service creates an independent `MissionCreate` for each target agent.
2. Independent missions allow tasks to run concurrently within the orchestrator's `max_concurrent_tasks` semaphore budget (parallel fan-out), avoiding sequential dependency blocking.
3. `constraints` dictionary carries `room_id` and `source_message_id` for fan-in tracking.

---

## 5. Fan-In & Result Persistence (`Result -> Room`)

1. During each `Orchestrator.tick()`, the engine scans recently terminal missions (`completed`, `failed`, `cancelled`).
2. If a mission has a `room_id` constraint, `notify_mission_outcome()` posts a system result message back to the originating room.
3. Only user-readable summaries are posted to the room; detailed technical logs remain in `audit_log`.

---

## 6. Approvals & Risk Ceiling Policy

- High-risk operations (R3/R4 or policy-gated tools) remain strictly gated by the existing `ApprovalRequest` workflow and `Reviewer`.
- If an agent task enters `waiting_approval`, execution pauses until Pascal approves or denies via standard approval channels.
- Posting to a room or @mentioning an agent never bypasses approvals or inflates risk ceilings.

---

## 7. Security Boundaries

- **Unauthenticated Access**: Gated by global `auth_gate` middleware.
- **Cross-Room Isolation**: Messages are queried strictly by `room_id`.
- **Secret Redaction**: Raw credential patterns (tokens, keys, headers) are redacted via `redact()` before DB persistence.
- **No Privilege Escalation**: Room membership grants zero extra tool or provider rights.

---

## 8. Known Limitations

- **Browser/Computer Sessions**: Foundation only (PR #27 / PR #28). No active Playwright or Chromium processes are launched by room messages in v1.3.
- **Participation States**: Execution dispatch filter only; no active polling/heartbeat per participation state.
