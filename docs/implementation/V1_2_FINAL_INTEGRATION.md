# V1.2 Final Integration Release Candidate

Backend PR #22 (`8298e8e`), Digital Company UI PR #24 (`f46dc9b`), and Claude acceptance fixes PR #26 (`32dc5e7`) are contained in PR #25 / `codex/v1-2-final-integration` at `c4cbf60`, based on `origin/main` `84d2b5e`.

## Integration status

- Org Canvas, cards, rooms and work views use the real API-first adapters. When the API is unavailable, the release candidate shows an empty/unavailable state rather than fabricated company or evidence data.
- Drag/drop relationship mutations call `/relationships`; graph cycle and self-edge errors remain backend-enforced.
- Work Evidence and Work Summary read persisted records. Evidence rendering requires redaction metadata; no screenshots or fake terminal state are generated.
- Chat secret interception is wired before send. Secure storage is truthfully unavailable until a secure encrypted credential store exists; raw values are not persisted in browser state.
- Existing V1.1.2 chat, auth, routines and project APIs are retained by the merge.
- Acceptance fixes add German graph-error translation, private-key and assignment-pattern detection, and truthful unavailable/mock banners.

## Validation

- Backend: 292 tests passed; Ruff, format and compileall passed.
- Migration: production-shaped copy migrated idempotently; legacy counts preserved; restart persistence passed.
- Real Qwen, browser Playwright QA, and runtime no-LLM call-count proof are `ENVIRONMENT_BLOCKED` in this execution environment (local router namespace unavailable). No production service or database was changed.
- Remaining mocks are isolated development fixtures only and are not used in normal API-unavailable RC flow.

## Open P2 follow-ups

- Project↔resource attribution is inferred through agents rather than a direct edge.
- The Work view remains evidence-backed; richer `/work-summary` consumption can be added later.
- Graph visualization should add clustering/focus modes for 50+ nodes.
