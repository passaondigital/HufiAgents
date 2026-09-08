# V1.2 Claude Handoff

- Backend branch: `codex/v1-2-core-capabilities`
- PR: #22 (must be synchronized with current `main` before merge)
- Available surfaces: `/work-evidence`, `/org`, `/teams`, `/graph-projects`/project members, `/resources`, `/relationships`, `/rooms`, `/skills`, `/memories`, `/context/assemble`, `/work-summary`, and metadata-only `/credentials`.
- POST responses return persisted typed objects. Invalid references, reporting cycles, self-edges, archived memberships and budget violations are 4xx errors.
- Evidence cards must render only persisted evidence and its redacted content. Org canvas edges represent organization only; membership never grants credentials, business-data access, deploy rights or risk-ceiling increases.
- Resource tiles may use safe metadata (`name`, `description`, `visibility`, `primary_language`, `last_activity_at`, `repository_ref`) stored in `metadata`; never display secrets.
- Work summary is a bounded persisted-data view and must not invent time saved, ROI or snapshots.
- Credential UI is handle/status/rotation/revocation metadata only. Plaintext secret entry, browser/computer snapshots and live external snapshots remain foundation/V1.3 scope.
- No fake learned state: display learning only when `LearningRecord` and corresponding audit event exist.
