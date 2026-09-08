# HufiAgents

HufiAgents is Pascal's self-hosted, local-first, model-agnostic multi-agent system and the workforce engine below HufiBoss.

The goal is not to copy another product. The goal is to reach the useful product effect of systems such as Grok Bot — simple agent UX, real work, routines, tools, browser/computer later — while keeping a clean-room implementation, Hufi's own architecture and a local-first operating model.

## Current status

**Production baseline:** `v1.1.2`  
**Production URL:** `https://agents.heyhufi.com`  
**Current development phase:** V1.2 — learning, Visible Work and Digital Company foundations.

V1.1.x is frozen except for real bug/security fixes.

## Core mission

Pascal gives an outcome, not a terminal tutorial.

Example:

> Bring HufManager to a production-ready and sellable state.

HufiAgents should then be able to:

1. plan the mission,
2. form/select the right team,
3. split work into tasks,
4. use models and tools,
5. work in isolated project workspaces,
6. test and review results,
7. recover from failures,
8. request approval only for genuinely risky actions,
9. preserve audit and user-facing Work Evidence,
10. learn reusable Skills/Memory from successful reviewed work,
11. report finished results and next decisions in normal language.

## Product principles

- Results before tool experimentation.
- **1:99:** one instruction should trigger as much safe useful follow-up work as practical.
- **20:80:** build the few capabilities that remove the most human coordination first.
- Local-first and self-hosted where sensible.
- Model-agnostic provider layer.
- Use the existing HUFI Local AI Router and local model aliases; do **not** install a second Ollama stack for HufiAgents.
- Least privilege and isolated workspaces.
- Persistent state and auditable tool execution.
- **Visible Work / Arbeitsnachweis:** Hufi shows understandable evidence of real work; progress, snapshots and success are never faked.
- **Digital Company:** agents, teams, projects, resources and chats form a flexible company graph, not a pile of unrelated bot threads.
- **Secrets are not chat content:** credentials use a separate scoped capability/store path and are never persisted in Memory/Skills/Work Evidence.
- No secrets, passwords or customer data in Git.
- Existing production systems must not be disrupted by development.
- HufManager remains a business priority and must not be blocked by endless meta-development.

## Product hierarchy

```text
Pascal
  -> HufiBoss
      -> HufiAgents
          -> Project Leads / Teams
              -> Specialists / Reviewers
              -> Skills / Memory / Routines
              -> Resources / Repos / Servers
              -> Tools / Browser / Computer
```

- **HufiBoss** — Pascal's private master/co-CEO layer.
- **HufiAgents** — reusable workforce/capability engine.
- **Hufi Manager / HufiApp** — later consume selected capabilities without exposing internal complexity.
- **AgentHufi / HufiApp Pro** — later public workforce layer.
- **HufiCloud** — later composition/builder layer.

## Digital Company / Org-Canvas target

HufiAgents evolves toward a visual company map where Pascal can organize digital employees through agents, teams, projects and resources.

Important: this is a typed graph, not a rigid tree. One agent may belong to several teams/projects at once.

Canonical specs:

- `docs/product/ORG-CANVAS.md`
- `docs/product/ORG-CANVAS-WORK-EVIDENCE.md`

## Visible Work

Normal users need to understand:

- who is working,
- what is happening,
- what actually finished,
- what evidence exists,
- whether approval is needed,
- what happens next.

Three target transparency modes:

- **Einfach** — milestones + result,
- **Transparent** — milestones + sanitized evidence/artifacts,
- **Live** — real browser/computer view only when a real session exists.

Canonical spec:

- `docs/product/VISIBLE-WORK.md`

## V1.2 work split

### Codex — Engine / Backend / Integration

Owns:

- Work Evidence + redaction,
- Company Graph backend,
- teams/projects/resources/relationships/chat rooms,
- Skill Engine,
- scoped Memory,
- Progressive Context,
- Learning Loop,
- Cost Governor,
- No-LLM routines,
- Credential Foundation,
- persistence/migrations,
- tests and real XXL validation,
- `docs/implementation/V1_2_API_CONTRACT.md`.

### Claude Code — Product / Frontend / Browser-QA

Owns:

- Org-Canvas,
- agent/team/project/resource cards,
- repo/resource grid,
- drag & drop + accessible alternatives,
- team/project/company chat UX,
- Visible Work / evidence cards,
- transparency modes,
- secure credential/token UX,
- responsive/accessibility/browser QA.

Both work autonomously in separate branches/worktrees and coordinate through repository contracts, issues and PRs instead of using Pascal as a technical message bus.

See `docs/OPERATING_MODEL.md`.

## Production capabilities today (`v1.1.2`)

Real today:

- FastAPI + SQLite,
- auth/login + HTTPS deployment,
- local HUFI model router,
- real local Qwen execution,
- mission/task lifecycle,
- review + retry,
- crash/heartbeat recovery,
- approval/risk engine,
- audit,
- HufManager connector,
- Bubblewrap isolation,
- controlled Git/GitHub path,
- dynamic/persistent agents,
- messaging/delegation,
- fan-out/fan-in,
- routines API/UI,
- chat-first product experience,
- responsive V1.1.2 Hufi visual pass.

The persistent per-agent browser/computer is still a later capability; do not represent it as already finished.

## V1.2 release proof

Before V1.2 can ship, prove at minimum:

- V1.1.2 data survives additive migrations on a production-shaped DB copy,
- real local-Qwen mission produces real Work Evidence,
- controlled fake-secret evidence is redacted,
- second similar mission reuses real Skill/Memory context,
- healthy deterministic routine records `model_calls = 0`,
- Company Graph team/project/resource/room context persists,
- frontend consumes real APIs without fake product states,
- full tests/lint/compile + real browser QA pass.

## Read first

- `AGENTS.md` — global operating rules.
- `CLAUDE.md` — Claude Code role/workflow history and rules.
- `docs/HUFIAGENTS-TARGET-PLAN.md` — binding 1:99 roadmap and long-term target.
- `docs/HUFIAGENTS-CAPABILITY-MAP.md` — reusable capability ownership.
- `docs/HUFIAGENTS-PRODUCT-VISION.md` — product vision and UX target.
- `docs/product/VISIBLE-WORK.md` — binding Work Evidence / trust principle.
- `docs/product/ORG-CANVAS.md` — Digital Company / flexible graph target.
- `docs/product/ORG-CANVAS-WORK-EVIDENCE.md` — real activity/evidence in the canvas.
- `docs/ARCHITECTURE.md` — system design and historical core contracts.
- `docs/ROADMAP.md` — current delivery sequence.
- `docs/SECURITY.md` — autonomy, credential and evidence security boundaries.
- `docs/OPERATING_MODEL.md` — Codex/Claude collaboration protocol.
- `docs/EVALUATION.md` — measurable acceptance framework.

## Repository safety

This repository is currently public. **Never commit real secrets, server credentials, customer data, private SSH keys, API keys or production `.env` files.** Use placeholders and approved secret/credential stores only.

## Development commands

Python 3.12 and `uv` are used in an isolated environment.

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Start the local API/UI:

```sh
uv run hufiagents serve
```

Useful CLI examples:

```sh
uv run hufiagents submit 'Write a short software test checklist'
uv run hufiagents list
uv run hufiagents show MISSION_ID
uv run hufiagents audit MISSION_ID
```

The default provider path uses the existing HUFI router. Use the fake provider for deterministic/offline development where appropriate.

See `docs/CORE-V1.md` for the historical V1 core runbook and `docs/V1-OPERATIONS.md` for production operations.
