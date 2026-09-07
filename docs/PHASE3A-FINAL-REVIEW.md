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
