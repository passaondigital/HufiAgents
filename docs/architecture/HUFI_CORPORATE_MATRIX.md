# Hufi Corporate Matrix (V1.4A)

## Product law

Pascal runs the company through one permanent Owner interface: HufiBoss. HufiBoss accepts,
prioritizes, routes, observes, escalates genuine decisions and compresses results. Mr. Equi is the
internal portfolio coordinator. Business Units and Shared Services perform the work.

The normal chain is:

`Owner goal → HufiBoss → Mr. Equi → unit(s) → agents → reviewed evidence → HufiBoss summary`

HufiBoss has no implicit root, production-write, credential or all-capability authority. Mr. Equi
is likewise a coordinator, not an authorization shortcut.

## Responsibility hierarchy

The idempotent bootstrap creates a bounded useful skeleton:

- Hufi Group
  - Shared Services: HufiTrust, HufiSales, HufiSupport
  - Business Units: HufiAgents, HufManager, HufiApp, EquiMeteo
- HufiAgents
  - Product → Quality Assurance
  - Engineering → Runtime, Browser, Agent Intelligence
  - Operations

It seeds only the executive contacts and workers required for real current flows. Future Finance,
Legal, Research, Data and Infrastructure units are not decorative records; they can be added when
they have real responsibilities and workers.

## OrganizationUnit identity and traversal

`OrganizationUnit` is additive to the existing `Team` model. A unit has a language-neutral
`stable_key`, localized display `name`, type, optional recursive parent/project, status, metadata,
and timestamps. A stable key represents its path, so `HufiAgents / Engineering` and
`HufiApp / Engineering` are legal and distinct. Display names are never global identifiers.

Parent changes go through a cycle check. Traversal is breadth-first, bounded and tracks visited
IDs, so corrupted cyclic data cannot recurse forever. List/snapshot APIs are paginated or capped;
the mobile Owner view uses active-area lists and drill-down rather than rendering the whole graph.

## Six independent layers

The system keeps these concepts separate:

1. Organization: `reports_to`, `member_of_unit`, legacy `member_of_team`.
2. Work: Missions, Tasks, `works_on_project`, artifacts and evidence.
3. Capabilities: agent tool/provider/role declarations and skills.
4. Data permissions: explicit project/data scopes and scoped memory.
5. Credential rights: metadata-only CredentialRefs and connector access.
6. Risk/cost: task and agent ceilings, approvals and external budget.

Organization never grants authority. Router membership is only an eligibility input; capability,
project scope, status, workload, risk and budget remain separate filters. A Shared Service worker
can work on multiple projects without cloning its identity, while project memory remains separately
scoped.

## Data-driven routing and 20:80

The corporate router first maps natural-language hints to language-neutral capability/project keys.
Those hints do not select workers. Selection queries stored unit responsibilities, recursive unit
membership, agent role capabilities, `works_on_project`, participation/status and active task
counts. Routing evidence records the selected unit, workers and the data sources used.

Selection is deliberately minimum-sufficient. A status question creates one task for one eligible
worker. The controlled multi-role QA contract selects four bounded roles because its four outputs
and dependency graph require them. No model call is spent discovering organization membership.
Provider selection and budget enforcement remain in the existing provider/risk routers; budget zero
does not become advisory.

## Owner Outcome Contract

Every normal front-door mission receives a persisted `OwnerOutcomeContract` with required roles,
workstreams, deliverables, reviews, evidence and completion conditions. It is a small validation
contract over existing Mission/Task/Review/WorkEvidence structures, not a workflow engine.

Task completion is not Owner completion. The evaluator requires:

- all required task workstreams and assigned roles;
- every required deliverable from `AGENT_GENERATED` or `TOOL_GENERATED` provenance;
- approved independent reviews for all tasks;
- persisted task evidence for all tasks.

If tasks end without those conditions, the contract becomes `PARTIAL` and the Mission becomes
blocked rather than completed. Only a satisfied contract can create `OUTCOME_COMPLETED`, set the
Mission completed and produce the HufiBoss management summary.

## Artifact provenance and work graph

`WorkArtifact.origin` is one of `OWNER_INPUT`, `IMPORTED`, `AGENT_GENERATED`, `TOOL_GENERATED` or
`SYSTEM_GENERATED`. Owner/imported artifacts may supply context, but cannot satisfy output
deliverables. Each generated output links mission, task, agent, deliverable key and artifact ref.

Together the existing and additive records reconstruct:

`Goal → Mission → workstream → Task → tool action → Artifact → Evidence → Review → Outcome`

The management summary reports only persisted task, artifact, evidence and review counts. It does
not invent ROI, time saved or completion percentages.

## Security and temporary agents

All user-visible mission text, audit detail, WorkEvidence, room messages, agent messages, result
summaries and artifact metadata cross redaction boundaries. Passwords, tokens, authorization/cookie
headers, private keys, credentialized URLs and credential-like sentinels are removed. Existing
historical records are not rewritten by migration 012.

Temporary children remain mission-scoped through the existing Workforce Builder. Their risk cannot
exceed the parent, tool/provider capabilities must be subsets, external budget cannot increase, data
scope cannot broaden and credentials never auto-inherit. Consequential work requires an independent
reviewer; an agent cannot be its own sole final reviewer.

## 1:99, international design and scale

Internal enums, keys and relationships are language-neutral; German labels are presentation only.
APIs are bounded, trees are lazy/drill-down, traversal is cycle-safe, and company/workforce
summaries batch tasks/events/memberships rather than issuing per-agent database queries. The 1:99
metric surface reports persisted Owner instructions, interventions, tasks, artifacts, evidence,
completed outcomes and paid model calls. Routine low-risk execution does not interrupt Pascal.

## Known limitations

- Natural-language classification uses a small deterministic multilingual bootstrap vocabulary;
  stored corporate facts remain the routing source of truth.
- Polling (2.5 seconds in chat) is used instead of SSE/WebSockets.
- Company Pulse reports recorded provider cost. Providers that do not emit cost metadata contribute
  zero recorded cost; it does not estimate monetary savings.
- HufManager exists as organizational metadata only in this release. No HufManager service, database
  or production environment is accessed.
