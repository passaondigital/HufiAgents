# Codex Workforce V1.x State

## Done

- WF-1--4 dynamic-agent persistence, lifecycle, messaging, delegation and fan-out/fan-in.
- WF-5--7 routines, controlled workspaces/sessions and connector registry.
- WF-8 read-only HufManager team benchmark: Chief -> Lead -> Security/Product,
  local-provider assessments, fan-in, independent reviewer and audit.

## Open

- WF-9 adversarial/security integration and WF-10 PR/integration verification.

## Branch / commit

- `codex/v1x-workforce`; base `64523da`; workforce commits `07bf1c4`, `542eaca`.

## Migrations / APIs

- Additive `003_dynamic_workforce`, `004_routines_connectors`; no destructive migration.
- `/agents`, `/agent-messages`, `/delegations`, `/missions/hufmanager/team`.

## Tests

- Workforce/HufManager targeted test set: 8 passed; ruff clean.
- Existing TestClient integration tests currently hang during lifespan entry in this
  environment (also pre-existing `test_web_auth`); direct async lifespan is healthy.

## Remaining / blocker / next exact step

- Add adversarial upgrade/permission tests, run non-TestClient suite and prepare PR.
- Blocker: TestClient/installed Starlette-httpx lifecycle incompatibility needs separate
  environment remediation before the full HTTP suite can be claimed green.
