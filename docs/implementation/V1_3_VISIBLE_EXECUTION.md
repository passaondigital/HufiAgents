# V1.3 Visible Execution & Automatic Work Evidence

Truthful, user-visible work activity and automatic proof-of-work evidence for HufiAgents V1.3.

## Overview
`Visible Execution` transforms real persisted runtime audit events, state transitions, tool execution results, reviews, approvals, handoffs, and routine triggers into user-readable, structured `WorkEvidence` records and derived execution feeds. It ensures complete transparency into active Agent activities without relying on fake live status indicators, simulated thinking text, or arbitrary step percentage animations.

## Key Architecture & Features

### 1. Evidence Collector (`hufiagents/evidence.py`)
- Automatically hooked into `UnitOfWork.log()` in `repository.py`.
- Maps raw audit events into structured, typed `WorkEvidence` categories:
  - `MISSION`: Mission creation and completion events.
  - `TASK`: Task start and retry events.
  - `TOOL`: Tool execution events.
  - `ARTIFACT`: File/report write events (`files: write_file`).
  - `TEST`: Test tool execution (`pytest`, `unittest`, etc.) with exit code detection.
  - `GIT`: Git status checks and commit operations.
  - `REVIEW`: Automated reviewer verdicts (`approve`, `revise`, `reject`).
  - `APPROVAL`: Risk ceiling gate requests, approvals, and rejections.
  - `HANDOFF`: Inter-agent task handoffs (`from_agent` to `to_agent`).
  - `REPO_CONTEXT`: Objective-driven repository context preparation.
  - `ROUTINE`: Autonomous routine execution triggers.
  - `ERROR`: Task failure events with redacted error context.

### 2. Mandatory Secret Redaction Before Storage
- All WorkEvidence fields (`summary`, `content`, `artifact_ref`, `metadata`) are passed through `redact()` before insertion in `EvidenceRows.add()` and `EvidenceCollector`.
- Raw bearer tokens, PATs, passwords, private keys, and environment secrets are sanitized to `[REDACTED]` prior to persistence.

### 3. Deduplication & Order Stability
- Evidence creation verifies existing mission evidence before insertion to prevent duplicate records during repeated observations or polling loops.
- Timeline ordering is preserved strictly by database insertion order and persisted timestamps (`created_at`).

### 4. Room & Milestone Integration
- Major milestones (`mission_created`, `mission_completed`, `handoff`, `approval_requested`, `artifact_created`) automatically post concise milestone messages (`📌 ...`) to Room chat if the mission originated from a room message.
- Granular tool step logs remain in the execution feed view to keep room chat clean.

### 5. Derived Execution Feed API
- `GET /missions/{mission_id}/execution`: Returns mission status, active agents, derived `current_activity`, `last_activity_at`, `step_summary`, `recent_evidence`, `artifacts`, `blockers`, and `approvals`.
- `GET /agents/{agent_id}/activity`: Returns bounded recent activity for a specific agent.
- Modes: `simple` (last 5 evidence items), `transparent` (full timeline), `live` (active event feed).

### 6. Truthful Current Activity & Fallbacks
- If an agent is running with no recent granular tool event, current activity returns `"Aufgabe läuft"`.
- Fake indicators such as `"Agent denkt"`, simulated typing, or arbitrary `4/11` step counts are strictly forbidden.

## Verification & Golden Tests
- `test_golden_visible_work_flow`: Verified end-to-end mission execution produces automatic `WorkEvidence` records without manual `POST /work-evidence`.
- `test_secret_redaction_before_persistence`: Verified raw secrets in tool outputs are redacted prior to database storage.
- `test_no_fake_live_activity_when_idle`: Verified idle/running tasks return `"Aufgabe läuft"` and no fake thinking text.
- `test_evidence_deduplication`: Verified duplicate completion events generate a single evidence record.
