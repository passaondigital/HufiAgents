# V1.2 Release Candidate Gate

**Branch / PR:** `codex/v1-2-final-integration`, PR #25  
**Head:** `c4cbf6092b5c5949aca36159985852e5e16c4210`  
**Base:** `origin/main` `84d2b5e`  
**Included:** PR #22 backend, PR #24 Digital Company UI, PR #26 acceptance fixes

Backend regression suite: 292 passed. Ruff, format, compileall and touched JavaScript syntax checks pass. Claude's independent acceptance report records P0=0, P1=0 and desktop/tablet/mobile/keyboard/branding/browser smoke success. Codex browser recheck is environment-blocked because Chromium/Playwright is unavailable.

Migration and restart validation passed against a copy of the production-shaped SQLite database; legacy counts were preserved. Production DB/service were not touched.

Open P2: direct project↔resource attribution, richer `/work-summary` frontend consumption, and large-graph density. Environment-blocked optional proofs: real Qwen runtime, learning/memory/skill reuse, and runtime no-LLM call-count telemetry. Latest PR CI passed; merge and deployment remain separate explicitly authorized steps.
