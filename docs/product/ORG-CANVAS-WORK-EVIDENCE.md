# Org-Canvas — Visible Work / Work Evidence Addendum

**Status:** binding addendum to `ORG-CANVAS.md`  
**Date:** 2026-09-08  
**Scope:** product/UX/data-model target only; no implementation or deploy

Org-Canvas is not only a structure editor. It must make the real work of the digital company understandable without turning the UI into a technical dashboard.

## Binding rule

An agent or team tile may show activity only when that activity is backed by a real runtime event, task state, tool result or artifact.

**Never fake:**

- `arbeitet` states,
- progress steps,
- screenshots/snapshots,
- completed work,
- delegation motion,
- success.

If no real evidence exists, the UI says so instead of simulating work.

## Tile-level work state

A selected agent/team/project may expose, in normal language:

- `arbeitet / wartet / fertig`,
- current task,
- project,
- elapsed time,
- last real action,
- latest sanitized work-evidence item,
- next step,
- pending approval,
- primary action `Arbeit ansehen`.

Technical IDs, providers, raw tool calls and risk codes stay under `Details / System`.

## Evidence examples

Evidence may be derived from:

- safe screenshots or browser snapshots,
- created/changed files,
- before/after views,
- Git diff or commit summary,
- branch/PR preview,
- test/build result,
- service/application state,
- generated report, document, image or other artifact.

## Transparency modes

- **Einfach:** important milestones, approvals, result.
- **Transparent:** milestones plus sanitized evidence/artifacts.
- **Live:** optional real browser/computer/terminal session when the capability exists.

## Motion

Activity pulses and animated edges represent only real active work/delegation. Motion is a projection of runtime truth, never decorative fake activity.

## Conceptual data-model extension

Add a reusable `WorkEvidence` concept linked to one or more of:

- Agent,
- Team,
- Project,
- Task,
- Routine,
- Artifact.

Suggested fields (target idea only):

- `id`
- `evidence_type`
- `summary`
- `source_event_id` / source reference
- `agent_id`
- `team_id`
- `project_id`
- `task_id`
- `artifact_ref`
- `created_at`
- `redaction_status`
- `visibility_scope`

The technical audit remains authoritative; WorkEvidence is the sanitized user-facing projection.

## Security

Before a screenshot, terminal excerpt, diff or artifact becomes user-facing Work Evidence, redact or remove:

- passwords,
- API keys,
- Personal Access Tokens,
- private keys,
- `.env` contents,
- session secrets,
- unnecessary sensitive personal/customer data.

## Daily value view

Org-Canvas should later support a company-level answer to:

> Was hat mein digitales Team heute für mich erledigt?

using real task/evidence data, with time/ROI only measured or explicitly labeled as an estimate.

Canonical cross-product principle: `docs/product/VISIBLE-WORK.md` on main.
