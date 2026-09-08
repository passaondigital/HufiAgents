# Codex Workforce V1.x State

## Done

- Branch/worktree created from `origin/main` (production V1.0.1 plus product vision).
- Work is split without frontend ownership overlap: Dynamic Workforce and
  Routines/Computer/Connectors.

## Open

- WF-1 through WF-10 implementation and integration.

## Branch

- `codex/v1x-workforce`

## Commit

- Base: `64523da` (product vision merged after V1.0.1).

## Migrations

- Existing schema migrations: 001 initial, 002 project fields.
- New additive migrations will be recorded per phase; no destructive migration.

## APIs

- Planned: dynamic agents, agent messages/delegation/results, routines,
  sessions/workspaces, connector registry, team HufManager mission.

## Tests

- Existing targeted suite is green at base pending integration verification.
- New unit/integration/adversarial coverage will be listed with phase commits.

## Remaining

- Integrate dynamic workforce and routines packages.
- Build HufManager team mission against real project facts with a local-model
  path, independent review, aggregation and audit.
- Run security/adversarial and full integration suite; prepare PR.

## Blocker

- None.

## Next exact step

- Review the two phase implementations, reconcile shared persistence/runtime
  interfaces, then add the HufManager team-mission E2E and security tests.
