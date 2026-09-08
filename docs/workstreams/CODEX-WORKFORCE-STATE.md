# Codex Workforce State

- done: WF-1 schema/persistence for dynamic agents, messages, delegations and channels
- done: WF-2 bounded spawn, update and archive lifecycle runtime/API
- done: WF-3 durable agent messaging and delegation/result return
- done: WF-4 fan-out/fan-in service support
- open: WF-5 through WF-10 are owned by the parent integration stream
- branch: `codex/v1x-workforce`
- migrations: `003_dynamic_workforce` (additive; existing V1 databases supported)
- APIs: `/agents`, `/agent-messages`, `/delegations`; lifecycle and receive endpoints
- security: child capabilities must be a subset of delegator capabilities; child risk ceiling cannot exceed parent; no hidden in-memory workforce state
- tests: `tests/unit/test_workforce.py`, `tests/integration/test_workforce_api.py`
- remaining: integrate HufManager team mission after routine/workspace/connector interfaces land
- blocker: none
- next exact step: parent merges WF-1–4 commits and resolves the next migration number with routines workstream
