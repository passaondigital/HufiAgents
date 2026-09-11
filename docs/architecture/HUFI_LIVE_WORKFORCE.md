# Hufi Live Workforce (V1.4A)

## Persisted truth

`WorkforceEvent` is a redacted projection of real append-only audit transitions. It does not create
work and has no heartbeat events. Canonical types include mission acceptance, planning, unit
selection, assignment, task/tool start and completion, artifact creation, messages, handoffs,
reviews, approvals, blockers, retries, errors and Owner outcome completion.

Events carry mission/task/agent/unit references, a safe summary, optional artifact/status/severity,
metadata and persisted `read_at`. Reload therefore reconstructs active work, timeline, artifacts and
unread badges from the database rather than browser cache.

## Derived agent state

Live state is derived from current persisted Tasks:

- queued/planning → `PLANNING`
- running/retrying → `WORKING`
- review → `REVIEWING`
- waiting approval → `WAITING`
- blocked → `BLOCKED`
- no active task → `AVAILABLE`
- disabled/archived profiles retain their lifecycle state

The API also returns current activity from the most recent event, last activity timestamp, unread
event count and active task count. Merely existing never produces `WORKING`.

## Owner experience

The default screen keeps HufiBoss central. The sidebar shows HufiBoss, real active/capable areas, a
persisted Owner-decision count and a collapsed worker directory. An area opens a unit workspace with
tasks, active workers, artifacts and events. A worker opens a digital work room with current state,
timeline, tasks, artifacts, evidence and structured messages/handoffs.

Chat starts with “Ich bereite den Auftrag vor.” Only after an `AGENT_ASSIGNED` event has been
persisted may it say the team is working. During execution, each real Task is shown with its actual
status and latest evidence. A gear rotates only for planning/running/retrying/review states; idle
workers show a static circle. New persisted unread events create badges. Reading a worker timeline
persists `read_at`.

The result card renders “Fertig” only when the Mission is completed, which for V1.4A front-door
missions requires a completed Owner Outcome Contract. Partial/blocked work remains nonterminal and
visible. HufiBoss returns the management result to the same chat turn/conversation.

## Accessibility and transport

Status is expressed with text and icon, never color alone. Buttons keep usable touch targets. Mobile
uses active-area lists and drill-down at 390×844 rather than a full company graph. Desktop retains
the contextual side panel at 1366×768. Continuous activity animation is tied to real active states,
and `prefers-reduced-motion` disables rotation/pulse. Bounded polling is sufficient for the current
single-owner architecture and avoids premature realtime infrastructure.

## Decisions and huddles

Pending R3/R4 approvals are the minimal Owner decision queue. Routine decisions stay inside policy.
Structured AgentMessage types (`REQUEST`, `RESULT`, `HANDOFF`, `BLOCKER`, `REVIEW`, `CHALLENGE`,
`APPROVAL`, `INFO`) and existing Rooms provide a bounded evidence-first huddle mechanism. Conflicts
are compared against evidence and reviews before an Owner escalation is created.
