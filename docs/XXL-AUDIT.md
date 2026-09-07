# XXL Server Audit

Read-only audit. No installs, no service changes, no deletions were performed to
produce this report. All data below was collected on the live host with
non-destructive commands (`free`, `df`, `ps`, `ss`, `systemctl status/cat`,
`docker ps/info`, config reads, `journalctl -k`, `crontab -l`).

## Host

- Hostname: `cloud-server-10634828`
- OS: Ubuntu 26.04.1 LTS (Resolute Raccoon)
- Kernel: `7.0.0-31-generic`
- Architecture: x86-64 (KVM guest, OpenStack Nova)
- Uptime: 3+ days at audit time (2026-09-07 16:46 CEST), 6 logged-in sessions
- GPU/accelerator: none. `lspci` shows only a Virtio VGA stub; no NVIDIA/AMD compute
  GPU. All local model inference is CPU-only.

## Capacity

- CPU: AMD EPYC-Rome, 16 vCPU, 1 thread/core, no NUMA-relevant split
- RAM total: 31 GiB
- RAM free at audit time: **~350 MiB free, ~11 GiB buff/cache, ~11 GiB "available"**
- Swap: 8 GiB total, **~5.3 GiB in use** at audit time
- Load average: 0.48 / 0.76 / 0.98 (16 cores) — CPU headroom exists, **memory does not**
- Disk (`/`, ext4): 775 GB total, 68 GB used, 708 GB free, 9% used — plenty of space
- Inodes: 1% used — no constraint
- No OOM kills found in `dmesg`/`journalctl -k` over the last 7 days despite the
  swap pressure — the system is currently absorbing load via swap, not crashing.
  Treat this as a **soft warning, not a green light**: swap already at 66%
  utilization means there is very little slack before either OOM kills start or
  swap-induced latency spikes hit the local model workers.

**Read this as the single most important capacity fact for HufiAgents V1: the
box is memory-constrained, not CPU- or disk-constrained.** Any new persistent
process budget must be small and bounded.

## Runtime/tooling

- Docker: 29.1.3, Compose plugin 2.40.3 — primary container runtime in use
- Podman: not installed
- systemd: primary service supervisor for all first-class Hufi services
  (no PM2, no PM2 process found anywhere on the host)
- Reverse proxy: nginx 1.28.3, active, TLS via certbot/Let's Encrypt, two vhosts
  configured (see below)
- Git: 2.53.0; GitHub CLI (`gh`) installed and authenticated as `passaondigital`
  (contradicts the `hostinger-audit` note that `gh` was missing — it has since
  been installed)
- Python: 3.14.4 (system); Hermes runs its own pinned venv at Python 3.11.16
- Node: v22.23.2, npm 10.9.8; no pnpm, no bun
- Ollama: **not installed, no `ollama` binary, no `ollama.service`.** Despite
  `README.md`/`AGENTS.md` referring to "Ollama/Qwen", the actual running local
  model stack is **llama.cpp `llama-server` in Docker**, fronted by a
  custom OpenAI-compatible router (see below). This is a documentation/reality
  mismatch that HufiAgents' Model Router must design against the real
  endpoint, not the aspirational one. See `docs/DECISIONS.md` ADR-003.

## Existing AI/agent components

This host already runs a working, hand-built agent stack under
`/srv/hufi/lab/factory/` ("HufiFactory") that predates this repository. It is
**not** a design draft — it is live, systemd-persisted infrastructure with its
own audit trail (`/srv/hufi/lab/factory/FACTORY-STATUS.md`,
`/srv/hufi/shared/knowledge/CHRONICLE.jsonl`). HufiAgents V1 must treat it as
an existing production dependency, not greenfield space.

### Local model workers (Docker)

| Container | Model | Bind | Status |
|---|---|---|---|
| `hufi-qwen9-worker` | Qwen3.5-9B (`duolaf/Qwen3.5-9B-GGUF:Q4_K_M`), ctx 65536 | `127.0.0.1:8081` | healthy, `restart: unless-stopped`, **PRIMARY**, ~12–14 GB RSS under load |
| `hufi-gemma-worker` | Gemma-2-9B-it (`bartowski/gemma-2-9b-it-GGUF:Q4_K_M`), ctx 8192 | `127.0.0.1:8082` | healthy, `restart: unless-stopped`, **SECONDARY/failover** |
| `hufi-qwen35-worker` | Qwen3.5-35B | shares 8081 with the 9B worker | **Exited (137)**, `restart: no`, currently unused — cannot run concurrently with the 9B worker on the same port |

Both active workers together already consume roughly **20+ GB RSS** at peak.
This is the dominant cause of the host's memory pressure.

### HUFI Local AI Router V1

- Path: `/srv/hufi/lab/factory/ai/local-ai-router/router.py` (stdlib Python,
  no framework dependency), config `registry.json` in the same directory
- systemd unit `hufi-local-ai-router.service`, runs as dedicated low-priv user
  `hufirouter` (no sudo, no docker group), hardened (`ProtectSystem=strict`,
  `NoNewPrivileges=true`)
- Listens on `127.0.0.1:8090`, OpenAI-compatible `/v1/chat/completions` and
  `/v1/models`, status at `/router/status`
- Routing: `hufi-qwen9` (PRIMARY, caller-controlled `enable_thinking`),
  `hufi-qwen9-fast` (same backend, server forces `enable_thinking=false` and a
  256-token output floor to prevent the reasoning-token-truncation bug the
  team already diagnosed and fixed), `hufi-gemma` (SECONDARY, direct route).
  PRIMARY→SECONDARY failover and recovery are verified working
  (`CHRONICLE.jsonl`, 2026-09-05).
- Backend timeout tuned to 180s; real agent turns through this router run
  60–180s+ end to end because Qwen3.5-9B on CPU is a reasoning model at
  roughly 14 tok/s with large (>3000 token) system prompts.
- **This router already fulfils most of the role planned for HufiAgents'
  "local model provider adapter."** V1 should treat `http://127.0.0.1:8090/v1`
  as the local provider endpoint, not install or manage Ollama, and not run a
  second, competing local-model router. See ADR-003.

### Hermes (agent/delegation layer)

- NousResearch Hermes-Agent 0.21.0, checked out at
  `/srv/hufi/lab/factory/agents/hermes/.hermes/hermes-agent`, own venv
- Runs as dedicated Linux user `hermes` (uid 1002), **no sudo, no docker
  group**, home directories `drwx------` (owner-only)
- systemd unit `hufi-hermes-a2a.service` ("Hufi Hermes A2A Gateway"),
  `A2A_HOST=127.0.0.1` — deliberately local-only; a comment in the unit notes
  MrEqui is meant to get an SSH tunnel "later" — **this tunnel does not exist
  yet**
- `config.yaml` points at the local-ai-router (`http://127.0.0.1:8090/v1`,
  model `hufi-qwen9`), already verified end-to-end (Hermes → Router → Qwen →
  real response, including a nested `delegate_task` sub-agent call)
- SQLite/WAL local state, no external DB dependency

### MrEqui / OpenClaw (remote)

- A **separate physical/virtual server**, `mrequi-openclaw` at
  `85.190.105.24`, referred to in project docs as "OpenClaw" — this is the
  planned upstream mission source ("Werkstattmanager"), not something running
  on the XXL host itself.
- Connects **into** the XXL host via SSH as local user `mrequi` (uid 1001),
  **no sudo**, member only of `hufifactory-read` (read-only access to
  `intake/hostinger-audit` and similar). Auth key label: "MrEqui OpenClaw ->
  HufiFactory".
- A local SSH keypair `xxl-to-mrequi` exists under
  `/home/administrator/.ssh/`, suggesting an XXL→MrEqui direction is also
  being prepared, but no working channel from MrEqui to Hermes exists yet
  (confirmed gap in `FACTORY-STATUS.md`, item "OFFEN #2/#3").
- **HufiAgents has no credentials or access to the MrEqui server itself.**
  Any MrEqui integration is out of scope for read-only audit and for V1
  unless Pascal explicitly provides access.

### HufiBoss / HufiOS / HufiLab

- No component literally named "HufiBoss" or "HufiOS" is running as a service
  on this host; those names currently describe the **target hierarchy**
  (`README.md`: `Pascal -> HufiBoss/Chief Agent -> ...`), not a deployed
  system.
- What **is** deployed under that umbrella today is **HufiLab**, a Next.js
  portal at `/srv/hufi/lab/factory/projects/hufilab`, systemd unit
  `hufilab.service`, user `hufilab` (dedicated, no sudo, no docker group),
  bound to `127.0.0.1:4100` only, reverse-proxied by nginx at
  `https://lab.huficloud.heyhufi.com`. It has real server-enforced
  bcrypt+session auth with `owner` (Pascal) / `junior` (Jamie) roles enforced
  on every route, not just hidden in the UI.
- A **separate, private** GitHub repo `passaondigital/hufi-factory`
  ("HUFI Factory – self-hosted visual AI software factory") exists and was
  not inspected in depth (out of scope for this read-only pass on
  `HufiAgents`). Flag for Pascal/Codex: verify this does not duplicate
  HufiAgents' mandate before investing further design effort.

### Shared knowledge / audit infrastructure (already exists)

- `/srv/hufi/shared/knowledge/` already implements exactly the kind of
  memory/audit separation `docs/ARCHITECTURE.md` calls for:
  `canonical/`, `historical/`, `systems/`, `projects/`, `quarantine/`,
  `registry.json` (service/agent inventory), and `CHRONICLE.jsonl` — an
  **append-only, timestamped, actor-tagged JSONL event log** with per-event
  test evidence and a `production_changes`/`hufmanager_changes` counter
  convention.
- HufiAgents V1 should **not** duplicate this. Its own `audit_log` stays the
  source of truth for HufiAgents-originated actions; whether/how to mirror
  into `CHRONICLE.jsonl` is deferred to a future decision (do not write into
  shared infrastructure state owned by the broader system without an explicit
  ADR and Pascal's sign-off, since other agents already depend on its
  format).

## Running services / ports

| Service | Port | Process/container | Production-relevant? | Notes |
|---|---:|---|---|---|
| nginx | 80/443 | systemd `nginx` | yes | TLS termination, 2 vhosts |
| ssh | 22 | systemd `ssh` | yes | fail2ban active |
| Supabase Kong gateway | 54321 | docker `supabase_kong_...` | yes | proxied at `/auth,/rest,/realtime,/storage,/functions,/graphql` for `hufmanager-staging` |
| Supabase Postgres | 54322 | docker `supabase_db_...` | yes | backing DB for HufManager staging |
| Supabase Studio | 54323 | docker `supabase_studio_...` | dev/admin | not proxied publicly |
| Supabase Mailpit | 54324 | docker `supabase_inbucket_...` | dev | test email capture |
| Supabase Logflare/analytics | 54327 | docker `supabase_analytics_...` | supporting | |
| Qwen9 worker | 127.0.0.1:8081 | docker `hufi-qwen9-worker` | yes | PRIMARY local model, do not stop |
| Gemma worker | 127.0.0.1:8082 | docker `hufi-gemma-worker` | yes | SECONDARY/failover |
| HUFI Local AI Router | 127.0.0.1:8090 | systemd `hufi-local-ai-router` | yes | intended local Model Router endpoint for HufiAgents |
| HufiLab portal | 127.0.0.1:4100 | systemd `hufilab` (Next.js) | yes | proxied at `lab.huficloud.heyhufi.com` |
| hufi-stt server | 127.0.0.1:8179 | user process (`administrator`) | yes (voice pipeline) | own venv, not containerized |
| unidentified local service | 127.0.0.1:9900 | unclear owner | unknown | not inspected further (read-only scope); do not assume free |
| unidentified local service | 127.0.0.1:37965 | unclear owner | unknown | not inspected further |
| DNS stub resolver | 127.0.0.54:53, 127.0.0.53:53 | systemd-resolved | infra | standard Ubuntu resolver, ignore |

No PostgreSQL or Redis run as native systemd services; the only Postgres
instance is the Supabase-managed one in Docker above. There is no standalone
Redis anywhere on the host.

## Resource constraints

- **Current heavy processes:** the two llama.cpp workers dominate RAM
  (~20 GB RSS combined); Supabase's docker stack (13 containers) adds a
  meaningful but secondary share; `hufi-stt` (~1 GB RSS) and the Logflare/
  Realtime Elixir BEAM processes are minor by comparison.
- **Existing limits:** swap already at 66% utilization at idle-ish load
  (0.48 load average) — there is very little memory headroom for a new
  always-on process.
- **Storage constraints:** none (708 GB free).
- **Port conflicts:** ports 8080 inside both llama.cpp containers collide by
  design (only one is meant to run at a time on the host-mapped side); no
  conflict for HufiAgents as long as it picks unused ports (see recommended
  profile below). Two unidentified local listeners (9900, 37965) were left
  untouched and unexplained — do not blindly bind adjacent ports without
  checking first.
- **Known production dependencies:** Supabase stack (HufManager staging),
  both llama.cpp workers + router (Hermes and, prospectively, HufiAgents),
  HufiLab portal, nginx/TLS, Hermes agent, fail2ban/ssh hardening. All are
  **do-not-touch** for HufiAgents V0/V1 except as a read-only client.

## Recommended HufiAgents profile

- [x] **Low resource**
- [ ] Medium resource
- [ ] High resource

**Reasoning:** CPU and disk are abundant, but RAM/swap are already under real
pressure from existing production workloads (local LLM workers + Supabase).
HufiAgents V1 must run as a **single bounded process** (API + in-process
orchestrator, no dedicated worker fleet, no new Postgres/Redis instance,
default concurrency capped low, e.g. 2 concurrent tasks). It should consume
the **existing** local-model router instead of standing up its own inference
stack, and default to **SQLite** for its own state rather than adding another
always-on database daemon. Re-evaluate toward Medium once real usage data
(from `docs/EVALUATION.md` metrics) shows the Low profile is the bottleneck,
not before.

## Safe installation plan

1. Add HufiAgents as a new, isolated systemd service (own dedicated low-priv
   user, following the `hufirouter`/`hufilab` pattern: no sudo, no docker
   group unless a specific tool genuinely needs it), bound to `127.0.0.1`
   only, with an explicit, small memory/CPU budget (`MemoryMax=`,
   `CPUQuota=` in the unit) so a runaway HufiAgents process cannot starve the
   model workers or Supabase.
2. Give it its own workspace root (e.g.
   `/srv/hufi/lab/factory/projects/hufiagents/` or a repo-local
   `./workspaces/` in dev) — never operate directly inside `hermes`'s,
   `hufilab`'s, or Supabase's directories.
3. Point its Model Router's local provider adapter at the existing
   `http://127.0.0.1:8090/v1` router; do not install Ollama, do not start a
   third local model worker without a documented capacity re-check.
4. Reverse-proxy any future HufiAgents web UI through nginx on a **new**
   subdomain/vhost, `127.0.0.1`-bound upstream, same TLS/certbot pattern as
   `lab.huficloud.heyhufi.com` — do not add it to the existing vhosts.
5. Before enabling the systemd unit at boot, verify `free -h` headroom and
   consider lowering local-model concurrency (e.g. confirm the 35B worker
   stays stopped) so HufiAgents' own footprint does not tip the host into
   active OOM territory.

## Risks / do-not-touch list

- Do not stop, restart, reinstall or reconfigure `hufi-qwen9-worker`,
  `hufi-gemma-worker`, `hufi-local-ai-router`, `hufi-hermes-a2a`, `hufilab`,
  or any `supabase_*` container. All are live production/near-production
  dependencies for Hermes, HufManager staging, or HufiLab.
- Do not modify `nginx` site configs for `lab.huficloud.heyhufi.com` or
  `hufmanager-staging.huficloud.heyhufi.com`.
- Do not touch the `hermes`, `hufilab`, `hufirouter`, or `mrequi` Linux
  accounts, their home directories, or group memberships.
- Do not write into `/srv/hufi/shared/knowledge/` (canonical knowledge base
  and `CHRONICLE.jsonl`) without a dedicated ADR and Pascal's sign-off —
  other agents already depend on its exact format.
- Do not assume ports `9900` and `37965` (127.0.0.1) are free; they are
  bound by an unidentified process.
- `/srv/hufi/junior/` is permission-restricted (`Permission denied` even for
  `administrator` via directory listing at depth 2); this was **not**
  bypassed and should stay untouched — it is a separate, deliberately
  isolated learning workspace.
- The `passaondigital/hufi-factory` private repo was not reviewed; confirm
  scope overlap with Pascal/Codex before duplicating effort.

## Audit timestamp

- Date/time: 2026-09-07 16:46–16:53 CEST
- Agent: Claude Code (Architect & Reliability Lead), read-only tools only
  (`free`, `df`, `ps`, `ss`, `systemctl status|cat`, `docker ps|info`,
  config file reads, `journalctl -k`, `crontab -l`, `du`, `gh repo list`).
  No file was modified, no service was started/stopped/restarted, no package
  was installed.
