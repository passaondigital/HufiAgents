# HufiAgents V1 — Operations

Server: this XXL host. Everything below assumes the deployment layout set up
for V1.0.

## Layout

```
/srv/hufi/lab/factory/projects/hufiagents/   # WorkingDirectory, git checkout of main
  .venv/                                     # self-contained: own Python 3.12 under .uv-python/, not administrator's
  .env                                       # secrets, mode 600, owner hufiagents:hufifactory
  run/hufiagents.sqlite3                     # SQLite DB (+ -wal/-shm/.lock)
  workspaces/                                # per-mission scratch checkouts
/srv/hufi/lab/factory/logs/hufiagents.log    # stdout+stderr
/etc/systemd/system/hufiagents.service
/etc/nginx/sites-available/agents.heyhufi.com.conf (+ sites-enabled symlink)
/etc/letsencrypt/live/agents.heyhufi.com/    # cert, certbot-managed renewal
```

Runs as a dedicated, unprivileged system user `hufiagents` (own group,
member of nothing else) — never as `administrator`. The service binds only
`127.0.0.1:8765` (`HUFI_PORT`); nginx is the only public listener,
terminating TLS and reverse-proxying to that loopback port.

## Service control

```bash
sudo systemctl status hufiagents.service
sudo systemctl restart hufiagents.service
sudo systemctl stop hufiagents.service   # do not do this without reason -- see "Stopping" below
sudo journalctl -u hufiagents.service -f     # systemd's own view of stdout/stderr
tail -f /srv/hufi/lab/factory/logs/hufiagents.log
```

Enabled for boot (`systemctl is-enabled hufiagents.service` → `enabled`).
`Restart=on-failure`, `RestartSec=5`: a crash restarts automatically within
seconds; systemd does not restart on a clean `stop`.

### Stopping deliberately

A clean `stop`/restart lets the in-flight `asyncio` runner get cancelled and
its heartbeat go stale in an orderly way — no special drain step is needed
for correctness (recovery handles both a clean stop and a hard kill the same
way, see below), but a mission mid-flight will pause until the service is
back and its heartbeat is detected stale.

## Restart / crash recovery

Proven live during V1 acceptance testing (`docs/V1-RELEASE.md`): the process
was `kill -9`'d mid model-call; on restart, `Orchestrator.recover()` (called
from `start()`) detects any task whose `heartbeat_at` is older than
`HUFI_HEARTBEAT_TIMEOUT_SECONDS` (120s in production), logs a `recovery`
audit event, and re-queues it. It re-runs from that point (a fresh model
call — nothing already-completed like a tool call's real-world effect is
blindly repeated; see `docs/DECISIONS.md` ADR-011/ADR-013 for the credential/
process-tree side of this). No manual intervention needed after a crash
beyond systemd's own automatic restart.

SQLite persists across restarts (`run/hufiagents.sqlite3`, WAL mode) —
missions, tasks, audit history and approvals all survive.

## Backup

The entire durable state is one file:
`/srv/hufi/lab/factory/projects/hufiagents/run/hufiagents.sqlite3` (plus its
`-wal`/`-shm` siblings, which SQLite reconciles into the main file on a clean
checkpoint). To back up safely without stopping the service:

```bash
sudo -u hufiagents sqlite3 /srv/hufi/lab/factory/projects/hufiagents/run/hufiagents.sqlite3 \
  ".backup '/srv/hufi/lab/factory/projects/hufiagents/run/backup-$(date +%Y%m%d-%H%M%S).sqlite3'"
```

`workspaces/` is disposable scratch space (mission checkouts) and does not
need backing up. `.env` contains secrets — back it up separately, out of
git, with the same access control as the original.

## Redeploying new code

```bash
sudo -u hufiagents bash -c '
  cd /srv/hufi/lab/factory/projects/hufiagents
  git fetch origin main
  git checkout main && git reset --hard origin/main
'
# If dependencies changed (check `git diff --stat` on uv.lock/pyproject.toml):
sudo -u hufiagents bash -c '
  cd /srv/hufi/lab/factory/projects/hufiagents
  export UV_PYTHON_INSTALL_DIR=/srv/hufi/lab/factory/projects/hufiagents/.uv-python
  /home/administrator/.local/bin/uv sync --frozen --no-dev --python-preference only-managed
'
sudo systemctl restart hufiagents.service
curl -s http://127.0.0.1:8765/health
```

The venv's Python interpreter is installed *inside* the project directory
(`.uv-python/`), not shared from `administrator`'s home — that home
directory isn't readable by the `hufiagents` user, so a venv pointing there
fails with `Permission denied` at every invocation. Keep using
`--python-preference only-managed` with `UV_PYTHON_INSTALL_DIR` set into the
project tree for any future rebuild.

## Configuration (`.env`, mode 600)

All `HUFI_*` variables are documented in `.env.example` at the repo root.
Notable production values:

- `HUFI_DEFAULT_PROVIDER=hufi-local-router`, `HUFI_LOCAL_ROUTER_BASE_URL=http://127.0.0.1:8090/v1` — the existing `hufi-local-ai-router` systemd service (Qwen primary, Gemma secondary), untouched by this deployment.
- `HUFI_ADMIN_USERNAME` / `HUFI_ADMIN_PASSWORD_HASH` — web login. Change the
  password:
  ```bash
  sudo -u hufiagents /srv/hufi/lab/factory/projects/hufiagents/.venv/bin/python -c \
    "from hufiagents.auth import hash_password; print(hash_password('NEW-PASSWORD'))"
  # paste the output into HUFI_ADMIN_PASSWORD_HASH in .env, then:
  sudo systemctl restart hufiagents.service
  ```
- `HUFI_SESSION_SECRET` — rotating it invalidates every existing browser
  session (forces re-login); it does not need to change on a password change.
- `HUFI_PUBLIC_HOSTNAME=agents.heyhufi.com` — required for the reverse proxy
  to reach the app at all (`TrustedHostMiddleware` rejects any other Host
  header).
- `HUFI_APPROVAL_TOKEN` — a bearer token for non-interactive (script/API,
  not the logged-in web UI) approve/deny calls. Not needed for normal
  browser use.
- `HUFI_MAX_CONCURRENT_TASKS=2`, `MemoryMax=768M` in the systemd unit — kept
  modest; this host already runs under real memory/swap pressure from other
  services (`free -h` at deploy time: ~20Gi/31Gi used, ~6.3Gi/8Gi swap used).
  Raise only if the host's actual headroom improves.

## Logs

`/srv/hufi/lab/factory/logs/hufiagents.log` (append, per the systemd unit).
Not yet wired into logrotate — matches this host's other `hufi-*` services,
none of which rotate either; monitor size (`ls -lh`) and address logrotate
for the whole `hufi-*` fleet together if it becomes a problem, not just for
this service.

## TLS renewal

Certbot's own systemd timer handles renewal (same mechanism already used for
`lab.huficloud.heyhufi.com`); nothing HufiAgents-specific to do. Verify with
`sudo certbot certificates` and `sudo systemctl list-timers | grep certbot`.

## Nginx

`/etc/nginx/sites-available/agents.heyhufi.com.conf`: HTTP→HTTPS redirect
(with an ACME challenge passthrough to `/var/www/certbot`) plus a TLS vhost
proxying to `127.0.0.1:8765`. No other vhost was touched. Reload after any
edit: `sudo nginx -t && sudo systemctl reload nginx`.

## Health monitoring

`GET https://agents.heyhufi.com/health` is unauthenticated by design (for
monitoring) and returns `{"status":"ok","provider":...,"max_concurrent_tasks":...,"auth_enabled":true}`.
It does not prove the local model itself is reachable — check `GET /models`
(authenticated) or the Models page for that (`router.status.primary_down`).

## Known operational risks

- No automated off-host backup of `run/hufiagents.sqlite3` is configured yet
  — only the manual `.backup` command above.
- No logrotate for `hufiagents.log`.
- `HUFI_MAX_CONCURRENT_TASKS=2` and `HUFI_HEARTBEAT_TIMEOUT_SECONDS=120`
  were chosen for this host's current resource pressure, not benchmarked
  against real mission load; revisit if missions queue up visibly on the
  Dashboard.
