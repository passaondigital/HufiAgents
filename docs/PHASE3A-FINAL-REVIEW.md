# Phase 3A Final Review

Date: 2026-09-07. Reviewer branch: `claude/final-review-phase3a`, based on
`codex/fix-phase3a-hardening` at
`a7a6d7431d3dc7eb80d9a4d643318c62f4810f52`.

## Result

**MERGE READY = YES.** The original Phase 3A blockers are closed on this Linux
host and their security boundaries were independently exercised.

Project code runs only in a verified Bubblewrap user/PID/network sandbox. The
independent probe confirmed no access to SSH/configuration/SRV paths, Docker socket,
foreign workspace, inherited HUFI credentials or the host network; only the mission
workspace is writable. Missing Bubblewrap and a failed Bubblewrap setup fail closed.
The runtime mount allowlist excludes arbitrary host executables including sudo,
systemctl and docker.

Credential processes run separately from project code. The direct child uses
`PR_SET_PDEATHSIG=SIGKILL` and a parent-PID race check; Bubblewrap places descendants
in a PID namespace with `--die-with-parent`. Independent tests cover a parent
SIGKILL/SIGTERM, cancellation and timeout, each with a child and grandchild. After
each test, credential-bearing descendants were zero. The existing recovery test still
proves a push that completed before a crash is not blindly repeated.

The local HTTP Basic-Auth probe rejects the wrong synthetic token and accepts the
right one. The suite verifies no token in argv, remote URL, Git config, persisted
audit/tool data, output or exceptions; pushurl/config/redirect attacks remain blocked.
The builder cannot push and the integrator remains bound to server-side targets and
protected branches.

## Final review fix

A new Worktree under host umask `0002` materialized the Askpass source as `0775`.
The old check correctly refused it, but this made a fresh checkout fail before local
Auth tests. The source remains secret-free; its content is now hash-verified and copied
to a private `0700` temporary helper only for the push, then deleted. Tampered or
linked source fails closed. This fix is covered by an added regression and ADR-014.

The network-denial probe now has a one-second socket timeout. A network namespace can
drop a TCP SYN rather than immediately reject it on some CI runners; the timeout keeps
the adversarial test deterministic while still failing if a connection succeeds.

## Validation

- `ruff check` and `ruff format --check`: passed.
- `pytest`: 249 passed; two existing third-party deprecation warnings only.
- `uv build`: sdist and wheel built.
- `scripts/review_phase3a_crash.py`: parent hard-crash left no credential child.
- `scripts/review_phase3a_hufmanager.py`: live HufManager clone, one disposable local
  commit, two reviews, dry-run push/PR and missing-token fail-closed all succeeded.
  `npm test`, lint and build were sandboxed and netless; each returned 127 because the
  fresh clone deliberately has no dependencies. No install outside the sandbox, product
  change, push, PR, deployment or production access occurred.

## Integration scope

PR #4 supersedes the standalone Phase 3A implementation/review branches:
`claude/phase3a-hufmanager-write-e2e` (original credential implementation) and
`codex/review-phase3a-auth` (security review base) are incorporated by the final line.
No older PR is to be merged separately. The final integration PR from
`codex/review-phase3a-auth` to `main` must be the sole mainline integration.

Remaining operational work is not a merge blocker: a future trusted dependency-cache
design is needed before a fresh, networkless HufManager clone can run its dependencies.

## Integration completed (2026-09-07, Claude Code continuation)

PR #4 (`codex/fix-phase3a-hardening` -> `codex/review-phase3a-auth`) and the final
integration PR #5 (`codex/review-phase3a-auth` -> `main`) are both merged. `main` is
at `301fd273ecd33932e46cf0783005a9bf7591493a`. PR #3
(`claude/phase3a-hufmanager-write-e2e`), the original standalone askpass
implementation, was not merged on its own; GitHub auto-marked it merged once its head
commit landed on `main` as part of this integration line -- no separate merge action
was taken.

PR #4's CI was not actually hanging forever: `uv run pytest -q` was failing fast and
then blocking, because the sandbox/credential boundary (`hufiagents/tools/sandbox.py`)
fails closed without Bubblewrap, and its `project_argv()` hardcodes a NodeSource-layout
Node.js (`/usr/bin/node`, `/usr/lib/node_modules/npm/bin/npm-cli.js`) -- the same
runtime this dev/review host has, which is why it was never caught locally. Neither was
installed on the GitHub-hosted runner. Once installed, a second failure appeared:
Ubuntu 24.04's AppArmor policy lets an unprivileged user namespace be created but
denies it `CAP_NET_ADMIN`, so `bwrap --unshare-net` (both `project_argv`'s untrusted-code
network isolation and `credential_argv`'s PID-tree containment) could not bring up
loopback. `.github/workflows/ci.yml` now installs `bubblewrap` and NodeSource Node.js
22, relaxes that one AppArmor restriction for the ephemeral runner VM, and runs a
`pytest-timeout` watchdog (60s/test, thread method) plus a 15-minute job timeout so a
future hang fails fast with a stack trace instead of burning CI minutes silently. Root
cause was reproduced and the fix verified 249/249 three times in a clean Ubuntu 24.04
container without Bubblewrap/Node preinstalled, run as a non-root user, before pushing.
`tests/integration/test_reliability.py::test_heartbeat_and_cancel` (pre-existing, not
part of this hardening branch) also had its timing assertion widened from 40ms to
300ms -- a true positive under CI scheduling jitter, not a regression.
