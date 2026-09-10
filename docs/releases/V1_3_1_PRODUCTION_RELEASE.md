# HufiAgents v1.3.1 Production Release Record

## Release Details
- **Release Version**: 1.3.1
- **Release Tag**: `v1.3.1`
- **Previous Version**: 1.3.0
- **Pre-Release Backup**: `/srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.3.0-pre-v1.3.1-20260910-084806.sqlite3`
- **PR #38 Merge SHA**: `ac0f01d161b6f84d0fbf348a10bc605420505ade`
- **CI Fix SHA**: `a3287d7`
- **Deployed Commit SHA**: `ac0f01d161b6f84d0fbf348a10bc605420505ade`
- **GitHub Release URL**: `https://github.com/passaondigital/HufiAgents/releases/tag/v1.3.1`

## Incident & Fix Summary
- **Incident**: 2026-09-09 ~22:18 CEST Pascal submitted a large Owner/Dogfood request via production UI resulting in `"Das hat leider nicht geklappt: Das hat leider nicht geklappt."`
- **Root Cause**:
  1. Payload validation cap (`Mission.outcome`, `MissionCreate.outcome`, `TaskSpec.objective`) limited at 16,000 / 8,000 chars, returning HTTP 422 before engine execution.
  2. UI error translation double-wrapping generic error strings in `org-data.js` / `chat.js`.
- **Fix**:
  - Increased `Mission.outcome`, `MissionCreate.outcome`, `TaskSpec.objective` max length limits to 32,000 chars.
  - De-duplicated error string formatting in `chat.js` and added specific German regex error mappings in `org-data.js`.
  - Added Playwright Chromium installation to CI workflow to resolve pre-existing CI failure on `test_golden_real_browser_flow`.

## Production Verification & Smoke Results
- **Full Test Suite**: 483 PASSED, 0 FAILED (up from 478 at v1.3.0)
- **Ruff Lint & Format**: PASSED
- **Health Check**: `GET /health` returned `status: ok`
- **DB Integrity**: PASSED (11 Agents, DB integrity intact)
- **Short Production Smoke**: `POST /missions` with short instruction returned HTTP 202, Mission created (`c0442fce-f460-479c-965b-98bfce1aa7f2`), 1 task queued. PASSED.
- **Large Production Smoke (Incident Class)**: `POST /missions` with 21,173 char instruction returned HTTP 202 (was 422 before fix), Mission created (`dc35c798-c1d6-4385-936b-8b9cb4ceb425`), 1 task queued. PASSED.
- **Security Boundaries**: PASSED (0 paid remote calls, budget 0 maintained, no privilege escalation)
- **Post-Deploy Stability**: Service `hufiagents.service` is ACTIVE and stable.

## Rollback Procedure
If rollback to V1.3.0 is ever required:
1. Stop service: `sudo systemctl stop hufiagents.service`
2. Restore repository commit: `sudo -u hufiagents git -C /srv/hufi/lab/factory/projects/hufiagents checkout v1.3.0`
3. Restore database backup: `sudo -u hufiagents cp /srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.3.0-pre-v1.3.1-20260910-084806.sqlite3 /srv/hufi/lab/factory/projects/hufiagents/run/hufiagents.sqlite3`
4. Sync dependencies: `sudo -u hufiagents uv sync --directory /srv/hufi/lab/factory/projects/hufiagents`
5. Restart service: `sudo systemctl restart hufiagents.service`
