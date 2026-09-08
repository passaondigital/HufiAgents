# V1.x Release Validation

## XXL host / security validation (2026-09-08)

- Isolated staging used a `/tmp` copy of the V1.0.1 SQLite database. Before:
  migrations `[1, 2]`, 6 missions. After opening with PR-14: `[1, 2, 3, 4]`,
  the same 6 missions, 160 audit events, and new workforce tables present.
- Full suite on the actual XXL host: **273 passed in 22.97s**. This includes
  TestClient/lifespan, loopback, Bubblewrap sandbox/process cleanup, auth,
  approval, audit and workforce coverage.
- `ruff check .`, `ruff format --check .`, and `compileall` passed after the
  formatting-only CI repair `20baf15`.
- Controlled staging verified same-origin `POST /agents` -> 201 and a foreign
  Origin -> 403; the temporary R0 agent and routine were archived.
- Real local-router HufManager team mission completed with reviewer approval;
  no GitHub write was performed.

## Browser / controlled staging (2026-09-08)

- Started an isolated PR-14 server on `127.0.0.1:8876` with a fresh
  `.release-validation` SQLite database and workspace. Production `:8765`
  was not changed.
- `GET /health` returned 200. `GET /models` reported the local router healthy
  and exposed `hufi-qwen9-fast`, `hufi-qwen9`, and `hufi-gemma`.
- A same-origin R0 `POST /agents` created `HufiReleaseTest`; it persisted in
  the API and was then archived. The archived state was confirmed by `GET`.
- A mismatched `Origin` on `POST /agents` returned 403. This confirms the
  browser cross-origin write boundary in the controlled instance.
- `/` and `/legacy` both returned 200. The delivered HTML contained no
  `coming soon` or `nicht verf\u00fcgbar` product placeholder text.
- Routines use the intentionally limited product grammar (`every day at
  HH:MM` / `every monday at HH:MM`). The UI prompt documents the supported
  weekly form. An ad-hoc German hourly string was correctly rejected.
- No Chromium/Chrome, Playwright, Selenium, or equivalent browser automation
  tooling was available on this host. Therefore the required real visual
  breakpoint, touch/keyboard, console-error, and network-error pass is still
  unproven; do not mark it passed from static/API checks alone.

## Pending from this workstream

- The isolated HufManager team/Qwen request completed: mission
  `8534f457-768e-49d2-9795-3d31598f5bb2` returned `completed`, a 2,609-character
  report, and reviewer verdict `approve`. The staging mission list showed the
  generated missions completed.
- A safe R0 routine completed its create, pause, resume, and archive lifecycle
  and reported a persisted `next_run`; its test owner was archived as well.
  The team-mission audit contained 19 events, including delegation, specialist
  result, review, and completion events.
- Remove the isolated staging process/data after the complete validation run.
- Remaining release gate: a real browser at the required breakpoints; no
  browser automation binary exists on the XXL host and none was installed.
