# V1.1 Product Experience — State

**Branch:** `claude/v1-1-product-experience` (worktree: `/home/administrator/HufiAgents-v1-1-product-experience`)
**Base:** `origin/main` @ `64523da` (product vision doc)
**Last commit:** `92f0669` — see `git log --oneline` for the full sequence
**Spec:** `docs/HUFIAGENTS-PRODUCT-VISION.md` §18–20 (new UI mandate, ideal flow, agent UI)

## Done

- **Phases UX-1 through UX-7 complete** (layout, chat flow, agent experience,
  approval/result cards, right pane/activity/routines-prep, responsive,
  integration test).
- New chat-first shell replaces the technical dashboard as the default UI:
  `hufiagents/api/static/{index.html,app.css,app.js}` (shell + `Hufi.*`
  contract — API helper, right-pane host, responsive shell at 700px/1100px)
  + `{chat.js,chat.css}` (mission-as-chat, progress lines, approval/result
  cards) + `{agents.js,agents.css}` (sidebar contact list, agent detail,
  Live-Aktivität, "+ Neuer Hufi", Details/System expert view).
- Backend: `/static` mount + `/` now serves the new shell; old dashboard
  kept reachable, unlinked, at `/legacy` (not deleted — expert fallback).
  No orchestration/auth/security code touched.
- **Verified in a real browser** (Playwright, ephemeral install, not a repo
  dependency) against the live local Qwen router at 1920×1080, 1366×768,
  768px, 390px: login → chat → real mission → real model reply → result
  card; agent sidebar → detail → Live-Aktivität; System/Details raw view;
  "+ Neuer Hufi" modal; `/legacy` still works. No console errors.
- Found and fixed 3 integration bugs only visible in-browser (see commit
  `92f0669`): `Hufi.el()` dropping a sibling element, `[hidden]` losing to
  class-level `display` on `.chat-empty`/`.chat-msglist`/`.row`/`.stack`,
  and an unbounded CSS Grid row inflating `#chat` to ~19000px whenever the
  System/Details JSON dump was open.
- `uv run pytest` — 262/262 passing throughout. `node --check` clean on all
  five JS files.

## Backend gaps (documented in-UI, not faked)

- **No `POST /agents`** — registry is seeded in code (`AgentRegistry.seed()`),
  read-only via `GET /agents`. "+ Neuer Hufi" builds the full flow but tells
  the user honestly that persistent creation isn't wired yet.
- **No routines API at all** — agent detail shows a visual "Bald verfügbar"
  panel, no endpoint called.
- **No per-agent "Computer"/workspace backend** — visual placeholder only.
- **`GET /audit` requires `mission_id`** (not optional as originally assumed
  when briefing the agent-experience subagent) — worked around client-side
  in `agents.js` (`fetchAggregatedAudit()`) by pulling recent missions and
  merging their audit trails; no backend change made.

## Relevant files

`hufiagents/api/static/*` (new), `hufiagents/api/__init__.py` (`/static`
mount + `/` + `/legacy` routes only — no other backend changes).

## Tests

`uv run pytest` (262 passed). No JS test framework in this repo (no build
step); frontend verification is `node --check` + the real-browser pass
above (not automated/repeatable yet — see Next step).

## Next step

1. Open PR `claude/v1-1-product-experience` → `main`.
2. Optional follow-up (not blocking): capture the Playwright browser check
   as a repeatable script/project skill (`/run-skill-generator`) instead of
   an ad-hoc `uvx --with playwright` run, so future sessions don't
   re-derive it.
3. Real backend work implied by this UX (separate from this branch):
   `POST /agents` for dynamic agent creation, a routines/schedule API,
   per-agent workspace/computer backend.

## Blocker

None. Ready for PR review.
