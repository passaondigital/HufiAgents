# V1.1 Release Fixes — MUSS Gates Closed

**Branch:** `claude/v1-1-release-product-fixes` (based on `origin/codex/v1x-final-integration`)
**Status:** all three MUSS-level release blockers from `PRODUCT-FLOW-FINDINGS.md` fixed and verified live against the fully integrated stand (Workforce + Dynamic Agents + Routinen + Chat UI). Real browser (Playwright, ephemeral), real local Qwen router, real `POST /agents`/`POST /routines`/`POST /approvals` APIs — nothing simulated in the frontend layer.

## MUSS 1 — Routinen im Chat erkannt, nicht mehr fehlinterpretiert

`chat.js`'s `detectRoutineIntent()` recognizes the German phrasings the task required, maps only what the backend's actual, narrow schedule grammar (`every day at HH:MM` / `every <weekday> at HH:MM`, `hufiagents/workforce/routines.py`) can represent, and asks rather than guesses for anything ambiguous (weekly-without-a-day, monthly — unsupported by the grammar, "morgen um" — no one-time scheduling exists at all). A clear match renders a confirmation card (Erstellen/Ändern/Abbrechen) that calls the real `POST /routines` on confirm.

**Live-verified (browser):** "Prüfe HufManager jeden Montag um 8 Uhr." → confirmation card → Erstellen → real routine created → survives a page reload → Pausieren/Fortsetzen toggle real API calls → archived via real API. All real, none faked.

## MUSS 2 — Keine falsche Erfolgsanzeige

Root cause was the backend review contract, not the frontend: a model refusal/incident report is non-empty text, so it mechanically passed `nonempty`/`file_exists` and the mission completed green. Fixed at the reviewer, not with a frontend string check (per the task's own guidance):

- `reviewer.py`: new `not_refusal` mechanical acceptance criterion, bounded German/English refusal-phrase list.
- `planner.py`: `not_refusal` added to the *default* `acceptance_criteria`, so every task gets it, chat-originated ones included.
- Unit-tested deterministically (`tests/unit/test_reviewer.py`, 5 cases: real refusal wording in German and English rejected, a legitimate result that merely *mentions* limits still passes, empty result still fails).

**Live-verified (browser):** a mission whose review cannot approve (deterministic test harness — see note below) renders the red "Nicht geschafft" pill, never green "Fertig". `chat.js`'s existing failure rendering needed no change — it was already correct; only the backend ever mislabeled the state.

*Methodology note:* the live local model is non-deterministic — an earlier attempt to reproduce the original finding with the exact same provocative prompt got a legitimate, well-formed safety-analysis response instead of refusal-shaped text (correctly rendered "Fertig" — that actually IS a usable deliverable). Rather than fish for a model response matching the phrase list, the browser proof uses a deterministic unsatisfiable acceptance criterion (same mechanism, same UI code path) to prove the *contract* — review-not-approved never renders green — independent of model wording on any given run. The phrase-matching itself is proven separately and deterministically by the unit tests.

## MUSS 3 — Freigaben im normalen Chat erreichbar

Two layers removed, plus one previously-hidden bug found and fixed while proving it live:

1. **`chat.js`** no longer hardcodes `risk_ceiling: 'R1'` — the field is omitted; the backend decides.
2. **`planner.py`**: `MissionCreate.risk_ceiling` default raised R1 → R2 (still safe: R2 stays policy-gated and denied outright for any agent below R2; R3/R4 always require approval regardless). Default `TaskSpec.allowed_tools` raised from `["files"]` to `["files","shell","git"]` — matching what the shipped `builder` agent already declares capable of using; this was a tighter artificial cap than the agent's own policy, not a security boundary.
3. **Found via the live browser proof, not by reading code**: `ensureApprovalCard()` only matched a pending `ApprovalRequest` by `task_id` — but a real R3 gate (a specific tool call, e.g. one `git push`) only ever carries `tool_call_id` (the two are mutually exclusive per `docs/ARCHITECTURE.md` Sec3.7). The approval card would **never** have rendered for the single most realistic case, even after the ceiling fix. Fixed with a fallback cross-reference against the tracked task(s)' own `/tool-calls`.

**Live-verified (browser), full loop, git-remote-level proof:** a simulated R3 request (real `integrator` agent temporarily elevated to R3 in a throwaway test DB — the same pattern `docs/V1-RELEASE.md`'s own V1.0.1 acceptance evidence used, reverted immediately after) reaches `waiting_approval` → real pending `ApprovalRequest` (`risk_class: R3`) → approval card renders in the actual chat UI → Ablehnen → real `POST /approvals/{id}/deny` → mission `cancelled` → **the bare git remote used for the test has zero commits afterward**, proving deny blocks execution at the actual git level, not just in UI state.

## Bonus fix found during this pass

`agents.js`'s routine list (added by the workforce-integration commit, `0cefad5`) rendered the raw backend schedule string ("every monday at 08:00") and a raw ISO timestamp in the normal view. `scheduleLabelDe()` translates the known grammar to German; falls back to the raw string for anything unrecognised. Not a MUSS item, but the same class of issue and a one-line-scope, safe fix — applied per the task's "weitere eindeutig sichere Polish-Fixes" allowance.

## PR #15 polish carried over

Six CSS fixes + two small self-contained JS fixes from `claude/product-qa-v1x` (contrast, touch targets, focus ring, modal focus trap, tablet z-index, humanized agent name in chat) — `app.css`/`chat.css`/`chat.js` applied as an identical patch (byte-identical base); `agents.css`/`agents.js` re-applied by hand since Codex's integration commit had already modified those two files.

## Full verification matrix (this session)

| Check | Result |
|---|---|
| `uv run pytest` | 282/282 passing (9 new: `test_reviewer.py`, `test_planner_defaults.py`) |
| `ruff check` / `ruff format --check` | clean |
| `python -m compileall` | clean |
| `node --check` (all static JS) | clean |
| Browser, 7 breakpoints (1920×1080 → 360×800) | no horizontal scroll, composer always reachable, sidebar/rightpane overlay correct, 0 console errors, 0 network errors |
| Flow: login → real mission (local Qwen) → progress → result | pass |
| Flow: "+ Neuer Hufi" → real `POST /agents` → reload → still present → archive | pass |
| Flow: routine detection → confirm → real `POST /routines` → reload → present → pause/resume → archive | pass |
| Flow: simulated R3 → approval card → deny → git remote has zero commits | pass |
| Flow: unapprovable review → never renders green "Fertig" | pass |
| Flow: sidebar shows no raw UUIDs in the normal view | pass |

No production data touched; all test servers ran against throwaway SQLite databases (deleted after) and a throwaway local bare git remote (deleted after); no secrets committed.
