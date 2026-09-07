# HufiAgents Roadmap

## Phase 0 — Inventory and bootstrap

- Read-only XXL audit.
- Identify existing Hermes/OpenClaw/Ollama/Qwen/HufiBoss components.
- Record running services, ports and resource use.
- Establish repo structure, CI, dev commands and safe secret handling.

**Exit:** `docs/XXL-AUDIT.md` exists and a reproducible development stack starts without disturbing existing services.

## Phase 1 — Autonomous core MVP

- Mission API.
- Task model and persistent state machine.
- Agent registry.
- Planner/orchestrator.
- Dummy provider + Ollama/Qwen adapter.
- Files/shell/git tools in isolated workspace.
- Risk/approval gate.
- Audit log.
- Reviewer agent.

**Exit:** green end-to-end test for Mission -> Task -> Agent -> Tool -> Review -> Persisted Result.

## Phase 2 — Coding workforce

- Git worktree/branch automation.
- Builder + reviewer agents.
- Test/CI integration.
- GitHub PR workflow.
- HufManager as first real project connector/use case.

**Exit:** HufiAgents can complete a bounded real repository task and prepare a verified PR.

## Phase 3 — Browser and infrastructure operations

- Playwright browser worker.
- SSH tool with least-privilege policy.
- Scheduled missions.
- Credential handling and redaction.
- Recoverable sessions.

**Exit:** safe browser and server tasks can be executed and audited with approval gates.

## Phase 4 — Agent teams

- Chief -> Project Lead -> Specialists.
- Agent-to-agent handoffs.
- Parallel execution with resource budgets.
- Shared project knowledge with isolation.
- Cost/model routing.

**Exit:** at least two specialist agents can collaborate on one mission with independent review.

## Phase 5 — Grok Bot benchmark

Run comparable missions through official Grok Bot and HufiAgents. Measure:

- success rate,
- elapsed time,
- human interventions,
- recovery,
- output quality,
- cost,
- security/policy violations.

Close the highest-value gaps rather than chasing cosmetic 1:1 similarity.

## Business guardrail

HufiAgents work must not become another endless meta-project. Once the coding workforce is capable enough, HufManager becomes the first production mission and remains a top priority.
