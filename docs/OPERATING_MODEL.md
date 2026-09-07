# Codex + Claude Operating Model

## Roles

Codex is the Builder / Integration Lead. Claude Code is the Architect / Reliability Lead.

## Branches

- Codex: `codex/core-builder` or `codex/<module>`
- Claude: `claude/architecture-reliability` or `claude/<module>`
- Use separate worktrees where practical.
- Never overwrite the other agent's unmerged changes.

## Coordination

Use repository artifacts instead of Pascal as a technical message bus:

- `docs/DECISIONS.md` for architecture decisions.
- `docs/HANDOFFS.md` for concrete handoffs.
- GitHub issues for work items and acceptance criteria.
- Pull requests for integration and review.

## Handoff template

```text
Date:
From:
To:
Task/Issue:
Ready:
Files/interfaces changed:
Tests run:
Known risks:
Need from receiver:
Acceptance criteria:
```

## Conflict resolution

1. Prefer tests and documented constraints over preference.
2. Prefer simpler and reversible designs when outcomes are equivalent.
3. Benchmark technical disagreements when practical.
4. Record the decision in `docs/DECISIONS.md`.
5. Escalate only business, cost, security or genuinely high-impact decisions to Pascal.

## Integration discipline

Integrate in small increments. Keep architecture contracts stable and branches short-lived. Every meaningful PR should state what changed, why, how it was tested and known risks.
