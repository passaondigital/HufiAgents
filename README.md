# HufiAgents

HufiAgents is Pascal's self-hosted, local-first, model-agnostic multi-agent system.

The goal is **functional parity with the useful parts of products such as Grok Bot**, without copying proprietary implementation details. HufiAgents should become the autonomous workforce layer behind HufiBoss and operate Pascal's real software and infrastructure projects with minimal human intervention.

## Core mission

Pascal gives an outcome, not a terminal tutorial.

Example:

> Bring HufManager to a production-ready and sellable state.

HufiAgents should then be able to:

1. plan the mission,
2. split it into tasks,
3. assign specialist agents,
4. use models and tools,
5. work in isolated project workspaces,
6. test and review results,
7. recover from failures,
8. request approval only for genuinely risky actions,
9. preserve an audit trail,
10. report decisions, risks and finished results.

## Principles

- Results before tool experimentation.
- Local-first and self-hosted where sensible.
- Model-agnostic provider layer.
- Qwen/Ollama for cheap/private routine work; stronger remote models when needed.
- Least privilege and isolated workspaces.
- Persistent state and auditable tool execution.
- No secrets, passwords or customer data in Git.
- Existing production systems must not be disrupted by the build.
- HufManager remains a business priority and must not be blocked by HufiAgents development.

## Initial agent roles

- **Hufi Chief** — mission intake, prioritisation, coordination.
- **Project Lead** — owns one product/project mission.
- **Builder Agent** — implementation.
- **Reviewer / Master Audit** — independent verification and rejection of weak output.
- **Infrastructure Agent** — server, deployment and runtime operations.
- **Browser Agent** — Playwright/computer workflows.
- **Security Agent** — permissions, secrets and risk policy.

## Target architecture

```text
Pascal
  -> HufiBoss / Chief Agent
      -> Mission Planner / Orchestrator
      -> Agent Registry
      -> Task Queue / Scheduler
      -> Memory & Knowledge
      -> Approval / Risk Engine
      -> Audit Log / Observability
      -> Model Router
      -> Tool Layer
          -> Files / Shell / Git / GitHub
          -> SSH
          -> Browser / Playwright
          -> MCP / APIs
      -> Project Leads
          -> Specialist Agents
```

## Work split

### Codex
Builder and integration lead. Owns the runnable core, repository bootstrap, containers, provider adapters, tool layer, tests, CI and XXL deployment.

### Claude Code
Architect and reliability lead. Owns agent contracts, state/failure recovery, security/approval model, evaluation, architecture review and selected reliability/security modules.

Both work autonomously in separate branches/worktrees and coordinate through repository files, issues and pull requests instead of using Pascal as a message bus.

## First milestones

1. Read-only XXL capacity/inventory audit.
2. Runnable local/dev stack.
3. Mission -> task -> agent -> tool -> review -> persisted result.
4. Local Ollama/Qwen provider.
5. Approval/risk gate.
6. Git workspace + PR workflow.
7. Minimal dashboard.
8. Browser/SSH tools.
9. Multi-agent teams.
10. Grok Bot benchmark and gap-closing.

## Definition of Done for MVP

- Mission can be created through API/UI.
- Orchestrator creates tasks.
- At least two agents can work sequentially or in parallel.
- One local model provider works.
- Provider architecture allows external models without core rewrites.
- Shell/files/git run in isolated workspaces.
- Risky actions are blocked by approval policy.
- State and audit history survive restart.
- A real repository task can be completed, tested and prepared as a PR.
- A reviewer agent can reject failed work and trigger correction.
- Deployment is reproducible and documented.

## Read first

- `AGENTS.md` — global operating rules.
- `CLAUDE.md` — Claude Code role and workflow.
- `docs/ARCHITECTURE.md` — target system design.
- `docs/ROADMAP.md` — phased delivery plan.
- `docs/SECURITY.md` — autonomy and approval boundaries.
- `docs/OPERATING_MODEL.md` — Codex/Claude collaboration protocol.
- `docs/EVALUATION.md` — how HufiAgents is measured against the target.
- `prompts/CODEX_START.md` and `prompts/CLAUDE_START.md` — first-run prompts.

## Repository safety

This repository is currently public. **Never commit real secrets, server credentials, customer data, private SSH keys, API keys or production `.env` files.** Use placeholders and secret stores only.

## Runnable Core V1 (Codex branch)

Python 3.12 and [uv](https://docs.astral.sh/uv/) are used in an isolated venv.
Existing host services are not installed or managed by this project.

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Dependencies, including development tools, are pinned in `uv.lock`.

Start the local API and status page (single worker, loopback only):

```sh
uv run hufiagents serve
# In another terminal:
uv run hufiagents submit 'Write a short software test checklist'
uv run hufiagents list
uv run hufiagents show MISSION_ID
uv run hufiagents audit MISSION_ID
```

Open `http://127.0.0.1:8765/` for status and `/docs` for the API. The default
provider calls the existing HUFI router; use `HUFI_DEFAULT_PROVIDER=fake uv run
hufiagents serve` for an entirely offline demo. No model is installed or pulled.
See [Core V1 runbook](docs/CORE-V1.md) for configuration, boundaries, recovery,
approval setup and verification. This core creates bounded text/file deliverables;
arbitrary repository code execution and external publishing remain deferred.
