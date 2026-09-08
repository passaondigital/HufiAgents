# V1.2 Release Candidate Gate

**Branch / PR:** `codex/v1-2-final-integration`, PR #25  
**Head:** `887ce6871da2f1fd420d1b0ecf4ae830941fab23`  
**Base:** `origin/main` `887ce687`  
**Included:** PR #22 backend, PR #24 Digital Company UI, PR #26 acceptance fixes

Backend regression suite: 292 passed. Ruff, format, compileall and touched JavaScript syntax checks pass. Claude's independent acceptance report records P0=0, P1=0 and desktop/tablet/mobile/keyboard/branding/browser smoke success. Codex browser recheck is environment-blocked because Chromium/Playwright is unavailable.

Migration and restart validation passed against a copy of the production-shaped SQLite database; legacy counts were preserved. Production DB/service were not touched.

Open P2: direct project↔resource attribution, richer `/work-summary` frontend consumption, and large-graph density. Environment-blocked optional proofs: learning/memory/skill reuse and runtime no-LLM call-count telemetry. The release was deployed after a verified retry backup and authenticated server-signed smoke; production now runs v1.2.0 at https://agents.heyhufi.com. The real smoke mission completed through hufi-local-router using hufi-qwen9 with paid remote calls 0. Automatic Work Evidence emission was not present, so no evidence was fabricated.
