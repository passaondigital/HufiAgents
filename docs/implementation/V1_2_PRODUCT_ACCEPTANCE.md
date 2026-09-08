# V1.2 Product Acceptance — Digital Company Integration

Independent product/frontend/UX/security review of the integrated V1.2 release candidate, performed by Claude (frontend owner of PR #24) against Codex's integration branch. This document is the review's record of what was checked, what was found, what was fixed, and the release recommendation. It does not speak for Codex or represent backend sign-off.

## Heads under review

| | Ref | Head |
|---|---|---|
| PR #22 (backend) | `codex/v1-2-core-capabilities` | `8298e8e` |
| PR #24 (frontend) | `claude/v1-2-digital-company-ui` | `f46dc9b` |
| PR #25 (integration) | `codex/v1-2-final-integration` | `ae3937e` |
| QA branch | `claude/v1-2-final-product-qa` | `150dcef` |
| QA PR | `fix(v1.2): final product acceptance fixes` | opened against `codex/v1-2-final-integration`, see below |

`claude/v1-2-final-product-qa` was branched from `origin/codex/v1-2-final-integration` at `ae3937e` (confirmed via `git ls-remote` and `gh pr view 25` before branching), then rebuilt with a real local server, seeded with two independent test datasets via the real API (a small named test company matching this review's specified scenario, and a 50-agent/10-team/20-project/30-resource scale dataset), and driven end-to-end with Playwright/Chromium — not evaluated by reading code alone.

## 1. API compatibility matrix

Built by reading the real `hufiagents/api/org.py`, `hufiagents/api/__init__.py`, `hufiagents/org_graph.py` and `hufiagents/contracts.py` on the integration branch, then cross-checking every frontend adapter call site.

| Surface | Frontend expects | Backend returns | Match | Notes |
|---|---|---|---|---|
| `GET/POST /agents` | `Agent{id,role,capabilities,default_risk_ceiling,status}` | same, plus `name,description,parent_agent_id,project_id,risk_ceiling,model_preference,memory_scope,workspace_id,created_by,archived_at` | ✅ | Frontend only reads the subset it needs; extra real fields (`name`, `parent_agent_id`) are currently unused by the UI — see finding F5 below. |
| `GET/POST /teams`, `/teams/{id}/archive`, `/teams/{id}/members` | `Team{id,name,description,status,created_at,archived_at}` | exact match | ✅ | |
| `GET/POST /graph-projects` | `GraphProject{id,name,description,repository_ref,status,created_at,archived_at}` | exact match | ✅ | Distinct from the unrelated real `/projects` git-repo registry — see finding F1. |
| `GET/POST /resources` | `Resource{id,name,resource_type,description,metadata,status,created_at,archived_at}` | exact match | ✅ | |
| `GET/POST /relationships`, `DELETE /relationships/{id}` | `GraphRelationship{id,relationship_type,source_type,source_id,target_type,target_id,primary,created_at,removed_at}`; `relationship_type ∈ {reports_to,member_of_team,works_on_project,responsible_for_resource,may_use_resource}` | exact match, same enum | ✅ | Verified 409 on cycle/self/archived-membership; see F2 (now fixed). |
| `GET/POST /rooms` | `ChatRoom{id,room_type,host_type,host_id,name,created_at,archived_at}` | exact match | ✅ | No message-storage endpoint exists on either branch — frontend is honest about this (local-only room messages), matches `V1_2_CLAUDE_HANDOFF.md`'s "Room-to-runtime messaging bridge is foundation-only". |
| `POST /credentials` | `CredentialRef{id,connector,label,scopes,status,created_at,rotated_at,revoked_at}` (no secret field) | exact match | ✅ | See F3 (now fixed) — frontend previously implied secure storage that doesn't exist. |
| `GET /work-evidence`, `POST /work-evidence` | `WorkEvidence{id,mission_id,task_id,source_type,evidence_type,summary,content,artifact_ref,metadata,created_at,redacted_at}` | exact match | ✅ | Frontend correctly gates raw `content`/`artifact_ref` behind non-null `redacted_at` (verified in code, PR #24 review). |
| `GET /work-summary` | *(not consumed)* | `{completed_tasks,active_or_blocking_tasks,generated_artifacts,work_evidence_count,reviews,affected_projects,team_filter,source}` | ⚠️ MISMATCH | Real, richer, persisted-only endpoint exists; `work.js` still computes its own client-side grouping from `/work-evidence` + org relationships (built before this endpoint existed). Current behavior is honest and functional, just not using the best available source — see F5. |
| `GET /org` | `{teams,graph_projects,resources,relationships,chat_rooms}` | exact match | ✅ | Confirmed live: 200 with real data once seeded, `Hufi.orgData.isMock()` correctly `false`. |
| `GET /projects` | `{id,repo_url,github_repo,default_branch,allowed,has_test,has_build,has_lint}` list | exact match | ✅ | This is the pre-existing runtime git-repo registry, unrelated to `GraphProject` — see F1. |
| `GET/POST /routines` + pause/resume/archive | matches `Routine` contract | exact match | ✅ | Verified real (not mocked), tested pause/resume/archive against the live seeded routine. |

No schema mismatches found. Every mismatch is a **frontend not yet using an available real endpoint**, not a broken contract.

## 2. Findings

### F1 — Project identity: two concepts, one name (P2, mitigated not eliminated)
`GraphProject` (org-canvas "Projekt") and the runtime `/projects` registry (connected git repos) are genuinely different backend concepts that can share a display name (e.g. "HufManager"). The frontend already separates them visually (a Project card under "Projekte" vs. a Resource tile under "Ressourcen", different headings, resource tiles labeled with the full `owner/repo` form) — this is **not** the literal "HufManager / HufManager / HufManager" failure mode the review was watching for. However, the two are not linked to each other, and a project's "related resources" (computed one-hop through agents who work on that project *and* have a resource relationship) can attribute a resource to a project it isn't really about, if an agent works on multiple projects. Confirmed live with seeded data: `repo_expert` working on both HufManager and HufiAgents caused the HufiAgents repo resource to appear as a "related resource" on both project cards. This is a graph-model limitation (no direct project↔resource edge type exists), not a frontend bug — **documented for Codex below**, not fixed here.

### F2 — Raw English backend errors shown in the German UI (P0, fixed)
`org_graph.py` raises technical English `ValueError`s ("reporting cycle", "archived nodes cannot gain memberships", "self relationships are not allowed", etc.) that FastAPI surfaces as the `detail` string on 409/4xx responses. Every place PR #24 rendered a rejection message (`org-canvas.js`, `cards.js`, and pre-existing `agents.js`/`chat.js`) rendered this raw string directly — e.g. dragging an agent into a reporting cycle would show the English word "reporting cycle" in an otherwise all-German product. This directly violates the product's German-only, no-raw-technical-text rule and was reproducible on the very first realistic multi-agent test.

**Fixed:** added `Hufi.errors.translate()` in `org-data.js` mapping every known backend `detail` string to a plain German sentence (with a safe generic fallback for anything unmapped), and routed it through every mutation (`createTeam`, `createGraphProject`, `createResource`, `createRoom`, `addRelationship`, `removeRelationship`) plus every pre-existing raw-message render site in `agents.js`/`chat.js`. Verified live: cycle rejection now shows "Diese Zuordnung würde einen Kreis in deiner Teamstruktur erzeugen.", self-relationship shows "Das geht nicht auf sich selbst."

### F3 — Credential UI implied secure storage that doesn't exist (P0, fixed)
Even on the real (non-mock) success path, `POST /credentials` only ever creates a `CredentialRef` metadata handle — there is no secret field on that model anywhere in the schema, so the actual secret is never stored and Hufi cannot use the connection for anything yet. The UI nonetheless showed "✓ GitHub verbunden" unconditionally on any success, which a reasonable user would read as "my token is now saved and usable." This is exactly the failure mode `docs/implementation/V1_2_CLAUDE_HANDOFF.md` and this review's own section 9 name explicitly.

**Fixed:** replaced with "`<Label>`: Verbindung vorbereitet" plus an explicit "Zugang wird in dieser Version noch nicht dauerhaft gespeichert. Hufi kann diese Verbindung noch nicht für Aufgaben nutzen." note on both the real and (now-retired) mock paths. Never says "sicher gespeichert" or "verbunden" as an unqualified claim.

### F4 — Two CSS specificity bugs made a `hidden` element always visible (P0, fixed)
`.org-canvas__banner{display:flex}` had equal CSS specificity to the native `[hidden]{display:none}` UA rule and loaded later in the cascade, so it always won — **the "Entwicklungsmodus — Beispieldaten" mock banner stayed visible even against a fully real, connected backend.** This is the most serious truthfulness bug found: it directly told the user the backend wasn't connected when it was. Confirmed via `element.hidden` reading `true` while `is_visible()` still reported `true`. The same bug class was already correctly guarded against elsewhere in this exact codebase (`app.css`'s `.row[hidden]`/`.stack[hidden]`, `chat.css`'s `.chat-empty[hidden]`/`.chat-msglist[hidden]`) — the newer org-canvas.css file just didn't follow the established pattern. Systematically swept every other `hidden`-toggled class across every CSS file in the app; this was the only real instance (a second suspect, `.hufi-card__detail`, already had the correct guard on inspection).

**Fixed:** added `.org-canvas__banner[hidden]{display:none}`. Also extended the banner to distinguish `unavailable` (real backend outage — Codex's `ae3937e` removed the mock-data fallback in favor of honest empty states, but nothing told the user *why* the graph was empty) from `mock` (now effectively dead in the RC path) from neither (hidden) — verified via route-interception forcing `/org` to fail: banner now correctly shows "Die Firmenstruktur kann gerade nicht geladen werden. Bitte versuche es in Kürze erneut." and stays hidden against the real, connected backend.

### F5 — `work.js` doesn't yet use the real `/work-summary` endpoint (P2, documented not fixed)
`GET /work-summary` (project/team/agent-filterable, backed entirely by persisted tasks/evidence/reviews, explicitly "no ROI estimates") was added on the integration branch after `work.js` was built against `/work-evidence` alone. Current behavior remains honest and functional (client-side grouping from real evidence + real org relationships), just not using the richer, more authoritative source now available. Recommended as a small V1.2 follow-up or V1.3 item, not a release blocker.

### F6 — `interceptChatInput()` missed two of the review's own required test patterns (P0, fixed)
The secret-detection heuristic (wired into `chat.js`'s real send path by Codex's `ae3937e`) covered GitHub/OpenAI/Slack/AWS token prefixes and a generic long-random-run heuristic, but **did not catch a PEM private-key marker (`-----BEGIN...PRIVATE KEY-----`) or a `PASSWORD=value`/`token: value` assignment pattern** — both explicitly named as required test cases in this review's brief. Reproduced live: both fake test values sent through to the normal chat flow uncaught before the fix.

**Fixed:** added both as `SECRET_PATTERNS` entries. Re-verified live: all 5 required fake test secrets (GitHub PAT, `sk-` key, Bearer token, PRIVATE KEY marker, `PASSWORD=`) now trigger the warning before send, with zero leakage into DOM, console, `localStorage`, or `sessionStorage` (confirmed by dumping both storages after each test and diffing against the raw secret text).

## 3. "Must prove" checklist (section 4 of the review brief)

All verified live against the real, seeded backend (not mocked), using a dedicated test company matching the requested scenario (`Hufi Boss`/`Mr. EquiBot` → `Entwicklung`/`Marketing`/`Server & Infrastruktur` teams → `HufManager`/`HufiApp`/`HufiAgents` projects → named agents → resources):

| Requirement | Result |
|---|---|
| Create team | ✅ real `POST /teams`, persisted |
| Create/use project | ✅ real `POST /graph-projects` |
| Create/use resource | ✅ real `POST /resources` |
| Assign agent to team | ✅ `member_of_team` relationship |
| Assign same agent to second team | ✅ `repo_experte_test` in both Entwicklung and Marketing simultaneously, single node, no duplication |
| Assign same agent to several projects | ✅ `repo_experte_test` on both HufiAgents and HufManager, both project cards correctly list it under "Verantwortlich" |
| Drag/drop relationship | ✅ (PR #24 review; Cytoscape native drag + bounding-box drop-target mapped to the correct relationship type) |
| Reload keeps relationship | ✅ confirmed identical Liste-view row for "Hufi Boss" before and after a full page reload |
| Reporting cycle rejected | ✅ 409, now shown as "Diese Zuordnung würde einen Kreis in deiner Teamstruktur erzeugen." (F2) |
| Self-edge rejected | ✅ 409, now shown as "Das geht nicht auf sich selbst." (F2) |
| Org move does not grant credentials/business-data access | ✅ structurally true — the `relationship_type` enum has exactly 5 members (`reports_to`, `member_of_team`, `works_on_project`, `responsible_for_resource`, `may_use_resource`); none of them touch `CredentialRef` at all, confirmed by reading `org_graph.py` and by enumerating every relationship type actually present in a live seeded graph |
| Work Evidence uses real API | ✅ `/work-evidence`, redaction-gated (F5 notes the *summary* endpoint isn't used yet, evidence itself is real) |
| Work Summary uses real persisted records | ⚠️ see F5 — current client-side computation IS from real persisted evidence/relationships, just not via the dedicated `/work-summary` endpoint |
| No fabricated working status | ✅ no pulsing/"arbeitet" state without a real backing signal anywhere found |
| No fake Live view | ✅ transparency mode "Live" renders "Live-Ansicht ist für diese Aufgabe nicht verfügbar." honestly |
| Routines still work | ✅ real `/routines` list/pause/resume/archive tested against a live seeded routine |
| V1.1.2 chat still works | ✅ regression-tested: sidebar agent click → chat opens → existing bubble/thread UI intact |

## 4. Secret protection (section 5)

Tested with 5 fake test secrets only (no real credentials used anywhere): a GitHub PAT shape, an `sk-` API key shape, a `Bearer` token, a PEM private-key marker, and a `PASSWORD=value` assignment.

- Warning occurs **before** send: ✅ (default send is intercepted, message never reaches `sendText()`)
- Secret not echoed: ✅ (checked full page HTML after the warning renders — the raw secret string never appears)
- No secret in console: ✅ (console capture across the whole run showed nothing but the two deliberately-triggered 409s from the cycle/self-relationship negative tests)
- No secret in localStorage/sessionStorage: ✅ (both dumped and diffed against every test secret — empty)
- No secret left in DOM after discard: ✅ (input cleared, warning removed)
- Credential UI does not claim secure persistent storage: ✅ after F3 fix

Two of five required patterns were initially missed (F6, now fixed) — this is the one place the initial state did not meet the bar, and it's exactly why this review step exists.

## 5. Product / UX walkthrough

**Horse-professional persona.** Walked the seeded test company as a non-technical, first-time, mildly-skeptical user would: the calm 5-item nav (Hufi/Team-Firma/Projekte/Routinen/Arbeit-Verlauf) reads clearly; agent cards lead with avatar/role/status, technical fields (capabilities, raw IDs, timestamps) are behind a collapsed "Details"; approval and error language use "Zulassen"/"Ablehnen" and full German sentences, never raw enums. The Org-Canvas graph, however, gets visually dense fast — see F7 below — which is the one place a first-time non-technical user could plausibly feel intimidated rather than in control.

**First-time / empty state.** A fresh install shows the existing v1.1.2 chat welcome screen ("Was soll ich für dich erledigen?") with starter chips — calm, not overwhelming, does not force org-structure setup before Hufi is usable. The Firma/Projekte/Routinen/Arbeit views each show honest, full-sentence empty states ("Noch keine Teams.", "Noch keine Routinen angelegt.") rather than a blank screen or a forced setup wizard.

**10-year-old test.** Primary-screen vocabulary stayed on-list (Mitarbeiter/Team/Projekt/Aufgabe/Routine/Arbeit ansehen/Freigabe/Verbindung) throughout every view exercised. No UUID, risk-ceiling code, `event_type`, or raw JSON was found outside a collapsed `<details>` in any normal-mode screen.

### F7 — Org-Canvas graph density at 50+ nodes (P2)
At the 50-agent/10-team/20-project/30-resource scale dataset, the "Teams" and "Organisation" graph lenses become visually cluttered — overlapping labels, hard to visually parse which node is which without zooming. The **Liste** lens (search + sortable table) remains fully functional and fast at this scale (render <2s, search works, no errors) and is the correct tool for "find one employee/project/resource quickly" at scale — so the underlying requirement (section 15) is met, just not through the graph view itself. Worth a small follow-up (e.g., default to Liste above some node-count threshold, or add basic label decluttering/clustering) but not a release blocker since the graph is a secondary lens, not the only way to find something.

## 6. Desktop / tablet / mobile / accessibility

Full Playwright sweep at 1920×1080, 1366×768, 1024×768, 768×1024, 430×932, 390×844, 360×800 across Hufi/Firma/Projekte/Routinen/Arbeit, plus the room panel and credential modal: **zero horizontal overflow at any width**. Keyboard-only pass (Tab/Shift+Tab/Enter/Escape): every modal traps focus and restores it to the trigger on close; the Liste view's per-row "Bearbeiten" button (21–22 present at test-company scale) is the required non-drag-and-drop path for every relationship type drag-and-drop can create, confirmed reachable and functional by keyboard alone.

## 7. Security

- XSS: live-injected a team name of `<img src=x onerror=window.__xss_fired=true>` through the real `POST /teams` → real `GET /org` → render path. `__xss_fired` never set; payload rendered as inert text. Systematic grep sweep of every `${...}` template interpolation across every app JS file for likely-user-controlled fields (`name`, `description`, `role`, `summary`, `label`, etc.) not wrapped in `esc()`/`Hufi.esc()` found 5 candidates, all confirmed false positives on inspection (either `.textContent` assignment, `.setAttribute()`, or hardcoded non-user-controlled literals inside the (now largely dead) mock-data builder).
- Secrets: see section 4 above.
- `localStorage`/`sessionStorage`: only non-secret usage found is `work.js`'s transparency-mode UI preference (`einfach`/`transparent`/`live`).

## 8. Truthfulness & branding

Truthfulness violations found and fixed: F3 (credential over-claim), F4 (mock banner shown against real data). No other fabricated state found — Live transparency mode, work evidence redaction gating, and room-chat "local only, not saved" labeling were all already honest in PR #24 and remain so post-integration. Branding: warm orange/red/neutral palette confirmed consistent across every screenshot taken this pass (Org-Canvas nodes, cards, modals, room panel, credential UI); no blue/green/cyan/turquoise found anywhere, including Cytoscape's own node/edge styling (explicitly themed, not left at library defaults).

## 9. Backend issues for Codex (not fixed here — frontend-only scope)

1. **No direct project↔resource relationship type.** "Related resources" on a `GraphProject` card can only be inferred one-hop through a shared agent, which misattributes a resource when that agent works on multiple projects (F1). A `responsible_for_resource`/`may_use_resource`-style edge with `source_type: "project"` (or a dedicated type) would let the frontend show this accurately instead of inferring it.
2. **`Agent.name` is populated but unused.** Every real agent currently has `name: ""` and is identified purely by `role` — worth confirming whether `name` is meant to become the primary display identity in a future pass (it exists in the contract but nothing sets it yet in this seeded environment).

## 10. Scale test

50 agents / 10 teams / 20 projects / 30 resources / 113 relationships seeded via the real API (dev/staging-only, not production). Initial page load 0.62s, Org-Canvas graph render 1.7–1.8s, Liste view 0.55s, live search filtering correctly (including a deliberately-verified true-negative: searching a raw internal agent id correctly returns "Keine Treffer für diese Suche." since IDs are intentionally not shown/indexed in normal UI). Zero console/network errors at scale. Graph density concern noted as F7.

## 11. Environment notes

The local model router (`hufi-local-router` → `hufi-qwen9-fast`) was reachable and healthy from this review's execution environment (`GET /models` returned `healthy: true`), unlike Codex's own sandboxed execution context (recorded as `ENVIRONMENT_BLOCKED` in `V1_2_FINAL_INTEGRATION.md`). Deep LLM-quality/mission-execution testing is out of scope for this frontend/UX/security product acceptance pass and was not pursued further, per this review's own instruction to focus on product acceptance rather than infrastructure repair.

## 12. Remaining V1.3-scope items (explicitly out of scope, not findings)

- Encrypted, durable credential value storage (currently metadata-handle-only by design).
- Room-to-runtime message persistence (chat rooms are honestly local-only today).
- Real live browser/computer session view (Live transparency mode has no backing capability yet).
- Direct project↔resource graph edges (see backend issue #1 above).

## Release recommendation

No P0/P1 finding remains open — F2, F3, F4, and F6 were all confirmed and fixed on this QA branch and re-verified live post-fix. F1, F5, and F7 are real but non-blocking (P2), each already mitigated by existing honest/functional behavior, and documented for follow-up rather than fixed in this pass per the "do not compete with Codex on backend architecture" boundary.

**FINAL VERDICT: ACCEPT WITH MINOR FIXES** (fixes already applied and verified on `claude/v1-2-final-product-qa`; P2 items F1/F5/F7 tracked for a later pass).
