# Codex + Claude Operating Model

**Updated:** 2026-09-08  
**Current baseline:** production `v1.1.2`; active work is V1.2.

## Principle

Codex and Claude Code should maximize useful parallel work without turning Pascal into a technical message bus.

They work on separate branches/worktrees, communicate through repository contracts and PRs, and only escalate genuine product/business/security decisions.

## Current V1.2 roles

### Codex — Engine / Backend / Integration Lead

Primary ownership:

- persistence and migrations,
- Work Evidence model/API,
- redaction/security helpers,
- Company Graph backend,
- teams/projects/resources/relationships/chat rooms,
- Skill Engine,
- scoped Memory,
- Progressive Context,
- Learning Loop,
- Cost Governor,
- No-LLM routines,
- Credential Foundation,
- API contract,
- tests and real XXL validation.

Current branch convention:

- `codex/v1-2-core-capabilities`
- or `codex/<module>` for truly isolated work.

### Claude Code — Product / Frontend / UX / Browser-QA Lead

Primary ownership:

- `hufiagents/api/static/**`,
- Org-Canvas,
- agent/team/project/resource cards,
- repository/resource grid,
- drag & drop and accessible alternatives,
- agent/team/project/company chat UX,
- Visible Work / evidence cards,
- `Einfach / Transparent / Live` modes,
- credential/token UX,
- responsive/mobile/tablet/desktop behavior,
- accessibility and browser QA,
- visual consistency with Hufi product laws.

Current branch convention:

- `claude/v1-2-digital-company-ui`
- or `claude/<module>` for truly isolated work.

## Shared API contract

Codex owns the authoritative implementation contract:

`docs/implementation/V1_2_API_CONTRACT.md`

It should be updated at useful checkpoints and contain:

- endpoints,
- request/response shapes,
- enums/states,
- error behavior,
- what is real now,
- what is only foundation/planned.

Claude should consume this contract rather than invent backend semantics.

Temporary frontend mocks are allowed only for development isolation and must not ship as fake product functionality.

## Branch discipline

- Use separate worktrees where practical.
- Never overwrite the other agent's unmerged changes.
- Keep shared-file edits deliberate.
- If a proposed subagent split causes heavy file conflicts, change the split.
- Rebase/merge from current `main` before final integration.
- No automatic production deploy from Codex/Claude development branches.

## Subagents

Subagents are encouraged when they genuinely reduce wall-clock time and file overlap.

Good split examples:

### Codex

- Work Evidence + redaction,
- Skills/Memory/Context/Learning,
- Company Graph + rooms/resources,
- Cost Governor + No-LLM + credentials.

### Claude

- Org-Canvas/graph interactions,
- cards/resources/repo grid,
- Visible Work/evidence surfaces,
- rooms/credential UX/mobile/accessibility.

The parent agent owns architecture consistency, integration and final QA.

## Coordination

Use repository artifacts instead of Pascal as a technical message bus:

- `docs/DECISIONS.md` for architecture decisions.
- `docs/HANDOFFS.md` for concrete handoffs.
- `docs/implementation/V1_2_API_CONTRACT.md` for backend/frontend contract.
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
API contract impact:
Tests run:
Real validation run:
Known risks:
Need from receiver:
Acceptance criteria:
```

## Product truthfulness

Both tracks must obey:

- no fake progress,
- no fake Work Evidence,
- no fake snapshots,
- no fake live computer,
- no fake success,
- no fake repo/resource metadata.

If a capability is unavailable, the UI says so plainly.

## Secret boundary

Neither track may place raw credentials in:

- chat,
- Memory,
- Skills,
- Audit,
- Work Evidence,
- screenshots,
- logs,
- URLs,
- normal API responses.

Frontend is not the authority for secret storage. Backend is not allowed to expose raw values merely because the frontend asks.

## Conflict resolution

1. Prefer tests and documented constraints over preference.
2. Prefer simpler and reversible designs when outcomes are equivalent.
3. Prefer stable capability contracts over screen-specific shortcuts.
4. Benchmark technical disagreements when practical.
5. Record architectural decisions in `docs/DECISIONS.md`.
6. Escalate only business, cost, security or genuinely high-impact decisions to Pascal.

## Integration discipline

Do targeted tests during development instead of burning time on the full suite after every small commit.

Before final integration/release:

1. current `main` integrated,
2. API contract reconciled,
3. additive migration tested on production-shaped DB copy,
4. real local-Qwen flow,
5. Work Evidence truthfulness/redaction proof,
6. Skill/Memory reuse proof,
7. No-LLM zero-call proof,
8. full test/lint/compile gate,
9. real browser QA,
10. security review,
11. production DB backup,
12. controlled deploy + smoke test.

Every meaningful PR states what changed, why, how it was tested, real-vs-mock status and known risks.
