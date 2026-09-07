# HufiAgents Target Architecture

## Goal

A self-hosted multi-agent runtime that can take an outcome, decompose it, delegate work, use tools, review results, recover from failures and request human approval only when risk warrants it.

## Core components

1. **Mission API** — receives user outcomes and constraints.
2. **Planner / Orchestrator** — converts missions into tasks and dependencies.
3. **Agent Registry** — capabilities, tools, model preferences, budgets and policies.
4. **Task Engine** — persistent state machine, retries, timeouts, cancellation and recovery.
5. **Model Router** — local and remote provider abstraction.
6. **Tool Gateway** — filesystem, shell, git, GitHub, SSH, browser, MCP and APIs.
7. **Risk / Approval Engine** — classifies planned actions before execution.
8. **Memory / Knowledge Layer** — separates task context, project knowledge and global knowledge.
9. **Audit / Observability** — immutable event trail plus runtime/cost metrics.
10. **Reviewer / Master Audit** — independent acceptance and rejection of work.
11. **Dashboard** — missions, agents, approvals, failures, costs and results.

## Logical flow

```text
Mission
  -> Planner
      -> Task graph
          -> Agent selection
              -> Model + tools
                  -> Tool execution
                      -> Result
                          -> Reviewer
                              -> complete | fix | retry | approval
```

## Agent hierarchy

```text
Hufi Chief
  -> Project Lead
      -> Specialist Agent(s)
          -> Reviewer / Master Audit
```

Hierarchy is a coordination mechanism, not a security boundary. Security comes from workspace/tool isolation and policy.

## Task contract

Each task should carry at least:

- id
- mission_id
- parent_task_id
- objective
- context references
- expected output
- acceptance criteria
- allowed tools
- risk ceiling
- preferred model/provider
- token/cost/time budget
- retry limit
- dependencies
- status
- assigned agent
- created/started/finished timestamps

## State machine

Minimum states:

`queued -> planning -> running -> review -> completed`

Additional states:

`waiting_approval`, `blocked`, `retrying`, `failed`, `cancelled`.

Transitions must be persisted before side effects where possible.

## Model layer

Provider-neutral interface. Initial providers:

- Dummy/fake provider for deterministic tests.
- Ollama/Qwen local.
- Remote provider adapters added without changing core orchestration.

Routing inputs may include:

- complexity,
- privacy,
- latency,
- current provider availability,
- cost budget,
- required context/tool capability.

## Tool layer

Every tool call is represented as a planned action and an audited result.

Initial:

- workspace filesystem,
- shell,
- git.

Next:

- GitHub,
- SSH,
- Playwright/browser,
- MCP,
- external APIs.

## Isolation

Each mission/project agent runs against an explicitly assigned workspace. Avoid mounting the whole host filesystem. Later strengthen isolation with containers/sandboxes as necessary.

## Persistence

Prefer PostgreSQL for durable mission/task/audit state once the resource audit confirms fit. A lightweight development profile may use SQLite initially if adapters keep the persistence boundary clean.

Redis is optional for queueing/coordination if justified by actual concurrency requirements.

## Memory boundaries

- Task context: short-lived and task-scoped.
- Project knowledge: project-specific source of truth.
- Agent memory: role-specific operational history.
- Global HufiBoss knowledge: curated, cross-project knowledge.
- Audit history: append-only operational evidence.

Vector search is optional support, not the source of truth.

## Deployment profiles

### Low resource

Single API process, SQLite or small Postgres, bounded agent concurrency, local model optional/offloaded.

### Medium resource

API + worker(s), Postgres, optional Redis, Ollama/Qwen, 2–4 concurrent workers.

### High resource

Multiple workers, stronger isolation, browser workers, multiple local models where resources allow.

The XXL audit determines the profile. Do not assume capacity.

## First end-to-end proof

A user submits a mission. The system creates at least one task, assigns an agent, calls a deterministic provider, executes a harmless workspace tool, records all state transitions, passes output to a reviewer and stores the final result. The same mission history is present after restart.
