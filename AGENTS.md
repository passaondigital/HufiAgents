# HufiAgents — Global Agent Instructions

These rules apply to every coding or automation agent working in this repository.

## Mission

Build a self-hosted, local-first, model-agnostic multi-agent system for Pascal. Optimise for finished outcomes, reliability, safety and low human intervention.

## Autonomy default

Do not ask Pascal routine technical questions that can be resolved by inspection, tests, documentation, reasonable defaults or reversible implementation choices.

### You may proceed without approval for

- read-only audits,
- code reading and analysis,
- branches/worktrees,
- commits and draft PRs,
- local builds and tests,
- documentation,
- reversible refactors,
- development containers,
- test/mocked data,
- static/security analysis,
- non-destructive diagnostics,
- implementation choices that can be changed later.

### You must stop and request approval for

- deleting or irreversibly modifying production data,
- destructive database migrations,
- purchasing paid resources or starting new contracts,
- public posts, customer communication or external commitments,
- exposing/rotating secrets where service interruption may occur,
- root/firewall/SSH changes with realistic lockout risk,
- switching production DNS/domains,
- material downtime to an existing production service,
- any action whose blast radius is unclear and cannot be safely tested first.

## Existing systems

Assume the XXL host may already run important services. Before installation or infrastructure changes perform a read-only inventory and record it in `docs/XXL-AUDIT.md`. Never blindly reinstall, overwrite or remove Hermes, OpenClaw, Ollama/Qwen, HufiOS/HufiBoss components or unrelated services.

## Repository policy

- Repository is currently public.
- Never commit real credentials, tokens, SSH keys, customer information or production `.env` files.
- Maintain `.env.example` with placeholders only.
- Prefer small, reviewable commits.
- Keep docs synchronized with implementation.
- Record meaningful architecture decisions in `docs/DECISIONS.md`.
- Record cross-agent handoffs in `docs/HANDOFFS.md`.

## Engineering standard

Every material change should include the appropriate combination of:

- implementation,
- tests,
- failure handling,
- logging/audit events,
- documentation,
- migration/rollback notes when relevant.

A feature is not done merely because the happy path works.

## Multi-agent coordination

Codex and Claude work in separate branches/worktrees.

Preferred roots:

- `codex/*`
- `claude/*`

Do not overwrite another agent's unmerged work. Use PRs, reviews, issues, `docs/HANDOFFS.md` and `docs/DECISIONS.md` for coordination.

## Priority order

1. Do not damage existing systems or leak data/secrets.
2. Reach a runnable HufiAgents MVP.
3. Preserve the path to HufManager becoming production-ready and revenue-generating.
4. Add browser/server/team capabilities.
5. Improve polish, voice, animations and non-essential UX later.

## Definition of useful progress

Useful progress means one or more of:

- a working capability,
- a reproduced and fixed bug,
- a green automated test,
- a verified deployment step,
- a documented architecture decision,
- a measurable reduction in manual intervention,
- a closed security/reliability gap.

Activity without a verifiable result is not progress.
