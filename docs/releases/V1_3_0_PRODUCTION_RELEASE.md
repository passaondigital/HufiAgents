# HufiAgents v1.3.0 Production Release Record

## Release Details
- **Release Version**: 1.3.0
- **Release Tag**: `v1.3.0`
- **Previous Version**: 1.2.0
- **Pre-Release Backup**: `/srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.2.0-pre-v1.3-20260909-211516.sqlite3`
- **PR #36 Merge SHA**: `713e7c098050c1abacfb2ddef22ff92690e4a282`
- **Hotfix PR #37 Merge SHA**: `686698106a9f3832bea5461ffee002f7b8b58d38`
- **Deployed Commit SHA**: `686698106a9f3832bea5461ffee002f7b8b58d38`
- **GitHub Release URL**: `https://github.com/passaondigital/HufiAgents/releases/tag/v1.3.0`

## Migration 011 Summary
- **Migration**: `011_v1_3_memory_skills_runtime.py`
- **Description**: Additive and idempotent migration adding column `status VARCHAR NOT NULL DEFAULT 'approved'` to table `scoped_memories` if missing.
- **DB Integrity Check**: `ok`
- **Recorded Migration Versions**: 1 through 11

## Production Verification & Smoke Results
- **Workforce Builder**: PASSED (Agent provisioned, profile history recorded, evidence logged, archived safely)
- **Memory / Skills Reuse**: PASSED (Approved skill & memory retrieved, unapproved draft and cross-project scopes excluded)
- **Routine Scheduler Runtime**: PASSED (Due routine claimed atomically, dispatched, `next_run` advanced, duplicate claim blocked)
- **Room -> Runtime Bridge**: PASSED (Room message persisted, reloaded, work evidence recorded)
- **Real Browser Worker**: PASSED (Chromium headless process launched, navigation to health endpoint, content read, valid PNG screenshot signature `\x89PNG\r\n\x1a\n`, SSRF and `file://` guards enforced, 0 orphan Chromium processes)
- **Workspace & MCP**: PASSED (Controlled workspace CRUD, cross-agent isolation enforced, path traversal blocked, MCP adapter operational)
- **Local Model Execution**: PASSED (Real router endpoint `127.0.0.1:8090` using `hufi-qwen9-fast`, 0 paid remote calls)
- **Security Negatives**: PASSED (54 automated security tests passed covering auth, workspace isolation, scope boundaries, browser guards, raw secret rejection, and budget ceilings)
- **Post-Deploy Stability**: Service `hufiagents.service` is ACTIVE and stable, memory footprint ~61.5M, 0 severe log errors.

## Rollback Procedure
If rollback to V1.2.0 is ever required:
1. Stop service: `sudo systemctl stop hufiagents.service`
2. Restore repository commit: `sudo -u hufiagents git -C /srv/hufi/lab/factory/projects/hufiagents checkout v1.2.0`
3. Restore database backup: `sudo -u hufiagents cp /srv/hufi/lab/factory/projects/hufiagents/run/hufiagents-v1.2.0-pre-v1.3-20260909-211516.sqlite3 /srv/hufi/lab/factory/projects/hufiagents/run/hufiagents.sqlite3`
4. Sync dependencies: `sudo -u hufiagents uv sync --directory /srv/hufi/lab/factory/projects/hufiagents`
5. Restart service: `sudo systemctl restart hufiagents.service`
