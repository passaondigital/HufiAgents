# HufiAgents — Org-Canvas Product Spec

**Status:** product/target specification (docs only)  
**Date:** 2026-09-08  
**Scope of this document:** conceptual product model, data-model idea, UX flows, wireframe description  
**Explicitly out of scope for this PR:** implementation, backend schema migration, production deploy, DnD engine, runtime UI changes

Related: [`docs/HUFIAGENTS-PRODUCT-VISION.md`](../HUFIAGENTS-PRODUCT-VISION.md) (digital company, agent UI target, dynamic agents, channels). Org-Canvas **extends** that vision; it does not replace the chat-first mandate or the V1 workforce engine.

---

## 1. Why Org-Canvas

HufiAgents already treats the product as a **digital company**, not a pile of chat windows. Today's agent list (and any plain bot sidebar) still under-delivers that mental model.

Org-Canvas is the spatial, relational surface where Pascal builds and runs that company:

- Agents appear as **tiles** (avatar / photo, name, role).
- Structure is shaped by **drag & drop** that creates or changes **relationships**.
- The same graph can be read as hierarchy, projects, teams, resources, or a flat list.
- Communication lives on the graph: agent chat, team chat, project chat, department chat, company chat.

Tone target: premium consumer product — "Movie Agents / Berlin" clarity — more intuitive and more alive than a technical admin list or a Grok-Bot-style sidebar. Grok Bot remains a **behavioral benchmark only** (clean-room); do not copy proprietary implementation.

### 10-year UX rule

Normal users see **people, teams, projects, and work**.

They do **not** see technical agent IDs, orchestrator jargon, provider names, risk class codes, or backend terms in the primary UI. Those stay under Details / expert mode.

---

## 2. Core principle: flexible company graph, not a rigid organigram

**Org-Canvas is a flexible Unternehmens-Graph (company graph), not a starres Organigramm.**

| Rigid org chart (not this) | Org-Canvas (this) |
| --- | --- |
| Each person has exactly one boss | Multiple relationship types; multi-membership |
| Tree only | Directed graph with typed edges |
| Structure equals reporting line | Reporting is one view of many |
| Move = reparent in a tree | Drag & drop creates / updates / removes edges |

Consequences that the product must support from day one of the design:

1. An **agent can belong to multiple teams and multiple projects at the same time**.
2. Drag & drop **does not "move a file"** — it **creates or changes relationships**.
3. Teams can have **Unterteams** (subteams).
4. Projects can have **their own teams**.
5. The same agent may appear under different parents in different views without duplicating identity.

---

## 3. Example structure (illustrative)

```text
Ebene 1 — Pascal (Owner / human)
Ebene 2 — HufiBoss  and/or  Mr. EquiBot
Ebene 3+ — deeper nesting, for example:

  Marketing (department / team)
    └── Marketing · HufManager
    └── Marketing · Hufi App

  Specialists (cross-cutting)
    └── Repo Expert
    └── XXL Server
    └── OHV Server
    └── OpenCloud Server

  Project-bound
    └── HufManager Lead + builders
    └── Hufi App Lead
    └── Hufi Cloud Lead
```

Nesting axes are **orthogonal**, not mutually exclusive:

- by **reporting / leadership**
- by **team / department**
- by **project**
- by **resource responsibility** (repo, server, tool)

---

## 4. Agent tile — what every digital employee carries

Each agent is a first-class person-like node with:

| Field | User-facing meaning |
| --- | --- |
| **Name** | Display name (e.g. "Mr. EquiBot") |
| **Bild / Avatar / Foto** | Portrait on the tile |
| **Rolle** | One-line job (e.g. "Coordinates your projects") |
| **Beschreibung** | Short persona / mandate |
| **Rechte** | What they may do (shown in plain language) |
| **Projekte** | Projects they work on (many) |
| **Aufgaben** | Current / open tasks |
| **Routinen** | Recurring work |
| **Dokumente** | Specs, reports, briefs they own or share |
| **Bilder / Dateien** | Media and attachments |
| **Ressourcen** | Repos, servers, tools they may use or own |

Creation UX stays minimal (aligned with product vision §20):

- Name  
- Avatar / photo / color  
- "Wofür ist dieser Hufi verantwortlich?"  

Advanced policy/capability derivation stays expert-only.

---

## 5. Relationship types (edges)

Drag & drop (and explicit "Link…" actions) create or edit typed edges between nodes.

| Edge type (product language) | Meaning | Typical from → to |
| --- | --- | --- |
| **berichtet an** | Reporting / leadership line | Agent → Agent or Owner |
| **gehört zu Team** | Team membership (many-to-many) | Agent → Team |
| **arbeitet an Projekt** | Project membership (many-to-many) | Agent → Project |
| **besitzt Verantwortung für Ressource** | Ownership / stewardship | Agent or Team → Resource |
| **darf Tool/Server/Repo verwenden** | Allowed use (not ownership) | Agent or Team → Resource |

Notes:

- Edges may carry optional metadata later (e.g. primary vs secondary membership, time-bounded access). Spec only — no schema migration here.
- Removing a tile from a cluster removes the **edge**, not necessarily the agent.
- Conflicting edges (e.g. circular "reports to") should be blocked or warned in plain language.

---

## 6. Communication spaces

Chats are rooms attached to graph nodes (or to the company root), not orphan threads.

| Room | Attached to | Who participates (conceptually) |
| --- | --- | --- |
| **Agent-Chat** | one agent | User ↔ that agent (and optional invitees) |
| **Teamchat** | team | Team members + user |
| **Projektchat** | project | Project members + user |
| **Abteilungschat** | department-scale team | Department members + user |
| **Firmenchat** | company / owner root | Broad company surface |

Opening a room from a tile or cluster is a primary action. Chat remains the **work surface** when diving into a node (consistent with chat-first mandate); the canvas is the **map**.

---

## 7. Views (same graph, different lenses)

Switching views must **preserve node identity** — it re-layouts and filters edges, it does not fork data.

| View | Shows |
| --- | --- |
| **Organigramm** | Reporting / leadership emphasis ("berichtet an"), with teams as clusters |
| **Projekte** | Project nodes as hubs; agents/teams as members |
| **Teams** | Team tree (incl. Unterteams); agents as members |
| **Ressourcen** | Repos / servers / tools as hubs; owners and allowed users |
| **Liste** | Searchable flat list of people / teams / projects (power users, mobile, a11y) |

Filters (search, project, status) apply across views.

---

## 8. Motion / "alive" structure

Structure should feel **slightly animated**, never noisy:

- Subtle pulse / soft highlight on tiles that are **actively working**.
- Quiet motion along edges for **active delegation** (who asked whom) and **work flow** (task in progress).
- No gaming neon, no constant particle spam.
- Prefer status dots and soft edge emphasis over loud badges (align with V1.1.2 visual pass: quiet status, warm brand).

Motion is **informative**, not decorative: it answers "who is busy for me right now?" without opening Details.

---

## 9. Conceptual data model (idea only — no migration)

This is a **product/target model**. V1 agents today are primarily role/capability/policy entries in the orchestrator. Org-Canvas does **not** require rewriting SQLite in this PR or as a silent production change.

### Node kinds

| Kind | Examples |
| --- | --- |
| `Owner` | Pascal (human) |
| `Agent` | HufiBoss, Mr. EquiBot, specialists |
| `Team` | Marketing, Marketing·HufManager, Infra |
| `Project` | HufManager, Hufi App, Hufi Cloud |
| `Resource` | GitHub repo, XXL server, OHV server, OpenCloud, tool |
| `ChatRoom` | agent / team / project / department / company |
| `Artifact` | document, image, file |
| `Task` | mission task / assignment |
| `Routine` | recurring work |
| `Permission` | plain-language right bundle (presentation of policy) |

### Edge kinds

Mirror §5:

- `reports_to`
- `member_of_team`
- `works_on_project`
- `responsible_for_resource`
- `may_use_resource`

Membership edges are **many-to-many**. An agent may have many `member_of_team` and `works_on_project` edges simultaneously.

### Suggested invariants (design-time)

- Stable product identity per agent (internal IDs exist only in Details / API).
- Deleting a team removes team membership edges and the team chat room; agents remain.
- Granting `may_use_resource` never silently escalates to production write without the existing approval/risk model.
- Chat rooms are 1:1 with their host node (or company root for Firmenchat).

---

## 10. UX flows

### 10.1 Create agent tile

1. User taps **Neuer Hufi** (or equivalent).
2. Minimal sheet: Name, Avatar/Foto, short responsibility prompt.
3. System creates an `Agent` node + default Agent-Chat.
4. Tile appears on canvas (e.g. near Owner or in "Unassigned").
5. Optional: system suggests team/project links; user confirms via drag or chips.

### 10.2 Drag agent onto team / project / under another agent

1. User drags tile onto a **Team** cluster → create/update `member_of_team`.
2. User drags tile onto a **Project** hub → create/update `works_on_project`.
3. User drops tile **under** another agent in Organigramm view → create/update `reports_to`.
4. Toast in plain language: "Mr. EquiBot gehört jetzt zu Marketing" / "berichtet an HufiBoss".
5. Undo available for a short window.

### 10.3 Grant resource access

1. User opens a Resource node (e.g. XXL Server) or drags agent onto resource.
2. Chooses **Verantwortung** (`responsible_for_resource`) vs **Darf nutzen** (`may_use_resource`).
3. Rights summary updates on the agent tile's detail pane in human language.
4. Risky grants remain gated by the existing approval model when execution would leave the sandbox.

### 10.4 Open chat from a node

1. Select tile / cluster → primary action **Chat öffnen**.
2. Center surface switches to that room; canvas can collapse to a mini-map or stay in the right/left context.
3. Sending a goal here is the same outcome-first chat model as today.

### 10.5 Switch views

1. View switcher: Organigramm | Projekte | Teams | Ressourcen | Liste.
2. Selected node stays selected; layout reflows.
3. Edges not relevant to the view dim or hide; membership does not change.

### 10.6 Nested teams and project teams

1. Create Team "Marketing", then Unterteam "Marketing · HufManager".
2. On a Project, action **Team für Projekt** creates or links a project-local team.
3. Agents can be in both the department team and the project team.

---

## 11. Wireframe description (layout)

Not pixels — spatial contract for design/implement later.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Top bar: search · view switcher · Neuer Hufi / Neues Team · subtle status │
├────────────┬─────────────────────────────────────────────┬───────────────┤
│ Left rail  │                 CANVAS                       │ Right pane    │
│            │                                              │ (selection)   │
│ Views:     │   [Owner tile]                               │ Name, avatar  │
│ · Organig. │        │                                     │ Rolle, Beschr.│
│ · Projekte │   [HufiBoss]────[Mr EquiBot]                 │ Rechte (plain)│
│ · Teams    │        │              │                      │ Projekte      │
│ · Ressourc.│   [Marketing]    [Repo Expert]               │ Aufgaben      │
│ · Liste    │    ···· tiles ···· soft edge motion ····     │ Routinen      │
│            │                                              │ Docs / Dateien│
│ Filters    │                                              │ Ressourcen    │
│            │                                              │ [Chat öffnen] │
├────────────┴─────────────────────────────────────────────┴───────────────┤
│ Optional bottom / center takeover when chat is focused: messenger surface │
│ Canvas reduces to mini-map or stays as map beside chat                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### Tile anatomy

```text
┌─────────────────────┐
│  (avatar / photo)   │
│  Name               │
│  One-line role      │
│  · quiet status dot │
└─────────────────────┘
```

### Interaction notes

- Drag handle / whole-tile drag; drop targets highlight in warm brand accents.
- Multi-select (shift/lasso) later; not required for first interactive prototype.
- Empty canvas state: "Bau deine Firma" + one suggested starter (HufiBoss).

---

## 12. Relation to existing product vision

| Vision topic | Org-Canvas contribution |
| --- | --- |
| Digital company mental model | Spatial graph + tiles make it tangible |
| Agent UI target (avatar, name, role) | Tile is the default representation |
| Dynamic agents | New tiles appear on the canvas when created |
| Channels / team spaces | Team / project / department / company chats |
| Chat-first UX | Canvas is the map; chat is still how work happens |
| Hide backend complexity | 10-year UX rule; IDs only in Details |

---

## 13. Non-goals (this PR and first implementation pass)

- No production UI or backend code in this PR.
- No SQLite / schema migration.
- No deploy.
- No full drag-and-drop engine or graph persistence yet.
- No SaaS multi-tenancy / RBAC productization.
- No copying of proprietary third-party implementation.
- No requirement that every orchestrator "role entry" already is a canvas tile in V1.x — mapping is a later integration step.

---

## 14. Suggested later delivery slices (not started here)

1. **Read-only canvas mock** over existing agents (no DnD persistence).
2. **Tile + detail pane** wired to current agent registry fields.
3. **DnD → relationship API** (create/update edges) with undo.
4. **Multi-view layouts** on the same store.
5. **Chat rooms** bound to teams/projects/company.
6. **Subtle activity animation** from live mission/task state.
7. **Resource nodes** for repos/servers with may-use / responsible-for.

Each slice needs its own implementation PR and approval; this document only defines the target.

---

## 15. One-sentence brief

> Org-Canvas is HufiAgents' living company map: drag people into teams and projects, grant resources, open the right chat, and watch work move — without ever teaching the user what an agent ID is.
