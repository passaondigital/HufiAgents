# HufiAgents V1.2.0 Production Release

- Release date: 2026-09-08 (Europe/Berlin)
- PR: #25 (merged)
- Main/deployed commit: `887ce6871da2f1fd420d1b0ecf4ae830941fab23`
- Tag: `v1.2.0`
- GitHub release: https://github.com/passaondigital/HufiAgents/releases/tag/v1.2.0
- Previous production: v1.1.2 (`05f7caf421588ac1dd03324416a9e9747ba53212`)
- Production URL: https://agents.heyhufi.com

Retry backup: `/srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.1.2-pre-v1.2.0-retry-20260908-172349.sqlite3`. It passed SQLite integrity (`ok`), additive migrations 1–7 were present, and legacy agents, missions, tasks, audit events, routines and approvals were preserved.

Authentication was verified without exposing credentials: unauthenticated `/agents` and deliberately invalid login returned 401, while an in-memory server-signed session accepted authenticated API requests. Smoke mission `cb35a4d2-fe07-4789-bb96-05f59f464ab0` completed through `hufi-local-router` using `hufi-qwen9`; paid remote calls were zero.

The lifecycle did not automatically emit Work Evidence for this mission; no synthetic evidence, learning, memory, skill reuse or no-LLM telemetry proof is claimed. Service remained active, HTTPS health returned 200, and no severe repeating logs were found.

Known follow-up: direct project↔resource attribution, richer Work Summary frontend consumption, graph density above 50 nodes, secure encrypted durable credential vault, and genuine live browser/computer sessions.
