# Security and Autonomy Policy

**Updated:** 2026-09-08  
**Current baseline:** production `v1.1.2`; V1.2 adds Work Evidence, Company Graph and Credential Foundation.

## Purpose

HufiAgents should be highly autonomous without turning autonomy into uncontrolled blast radius.

Security and product truthfulness are coupled: the system must not hide dangerous actions behind a simple UI, but it must also avoid forcing normal users to understand internal risk codes.

## Risk classes

### R0 — Read only
Examples: inspect code, logs, configs, metrics, repo history.

Default: automatic.

### R1 — Reversible development change
Examples: edit code on a feature branch, run tests, start dev containers, create local test data.

Default: automatic.

### R2 — Low-impact external change
Examples: create a draft PR, update a non-production development environment, restart a dedicated development worker.

Default: automatic only when policy explicitly allows it; otherwise require reviewer approval.

### R3 — Production/security-sensitive
Examples: production deploy, production database migration, firewall/SSH changes, secret rotation with possible outage, DNS changes.

Default: explicit Pascal approval.

### R4 — Irreversible/financial/high criticality
Examples: deleting production data, purchasing resources, contractual commitments, public customer communication, irreversible infrastructure actions.

Default: explicit Pascal approval.

## Tool policy

Every tool invocation should have:

- requesting agent,
- task/mission id,
- action summary,
- target resource,
- risk class,
- policy decision,
- timestamp,
- result,
- bounded/redacted error or output where necessary.

The normal UI translates consequences into human language; the internal risk class remains available under technical details/audit.

## Secrets — binding rules

- Never commit real secrets.
- Never print secret values into logs.
- Never ask a user to paste a secret into ordinary chat.
- Never store raw secret values in Memory, Skills, Work Evidence, mission results or human-readable audit summaries.
- Never include raw secrets in screenshots, URLs, browser console output or client-visible errors.
- Use placeholders in `.env.example`.
- Prefer runtime-injected secrets or a dedicated credential/secret store.
- Agents receive only the credential capability required for the current scope.
- Agents should receive a scoped handle/capability rather than plaintext whenever possible.
- Normal GET APIs must not return full secret values after registration.
- Credential replacement and revocation must be supported.
- If safe encryption-at-rest cannot be implemented in the current iteration, fail closed and document the boundary instead of inventing weak cryptography.

### Secret-like chat input

Product surfaces should detect likely access keys before sending when practical.

Expected UX:

> Das sieht nach einem Zugangsschlüssel aus.

Offer secure handling or discard; do not echo the value back into the conversation.

Client-side detection is only a UX guard. Backend security must never depend on it.

## Credential store separation

Credential data is logically separate from:

- chat messages,
- agent records,
- team/project membership,
- Memory,
- Skills,
- Audit text,
- Work Evidence,
- artifacts/results.

Connector/resource records store credential references/handles, not secret values.

A team/project/resource relationship does **not** grant credentials automatically.

## Work Evidence / Visible Work security

Work Evidence is a user-facing trust layer derived from real events/artifacts. It is not permission to expose raw technical output.

Before evidence is stored or displayed, apply appropriate sanitation/redaction.

Never expose:

- passwords,
- API keys,
- Personal Access Tokens,
- private keys,
- `.env` contents,
- session secrets,
- Authorization headers,
- cookies,
- credential-bearing URLs,
- known injected secret values.

Prefer structured evidence extraction and allowlisting over blindly publishing full terminal/log output.

A screenshot/artifact must not become user-visible evidence unless it passes the relevant sanitation path.

### Adversarial evidence tests

Use controlled fake values for tests such as:

- fake GitHub PAT,
- `PASSWORD=fake-secret`,
- fake Authorization header,
- fake cookie/session value,
- credential-bearing test URL,
- private-key-shaped text.

Verify both:

1. secret-like values are removed/masked,
2. harmless text is not over-redacted.

## Company Graph / Org-Canvas security

Org-Canvas relationships describe organization/context; they do not supersede capability/risk policy.

Examples:

- dragging an agent onto a project may assign project membership,
- dragging an agent onto a repo/resource may propose a resource relationship,
- neither action silently grants production write/deploy/credential authority.

Required invariants:

- no self `reports_to`,
- prevent/handle obvious reporting cycles,
- archived agents cannot silently gain new active permissions,
- removing team membership does not delete agent identity,
- resource membership does not bypass approval policy,
- child agents cannot raise their own capability/risk ceiling,
- project/team membership does not reveal credential material.

Any rights-changing action that crosses policy boundaries must use the existing approval model.

## Memory and Skills security

- Never persist credentials in Memory or Skills.
- Project/agent memory remains scoped and is not globally loaded by default.
- Explicitly shared knowledge is separate from implicit cross-project leakage.
- Learned procedures that involve production writes, destructive actions, credentials, protected branches or other high-risk behavior remain draft/unapproved until policy allows reuse.
- A failed/rejected mission must not silently train an approved skill.

## Cost Governor security boundary

Cost/budget limits are policy, not agent preference.

- child agents cannot disable or raise external budgets,
- external budget `0` means no paid remote call,
- privacy/security policy can block a remote call even when budget exists,
- retry/spawn loops must be bounded,
- actual/estimated external cost should be auditable without exposing secrets.

## No-LLM routines

Deterministic routines should use no model when a model is unnecessary.

This improves both cost and attack surface.

Healthy checks such as HTTP/service/disk/SSL/backup/Git state should complete deterministically. Model escalation occurs only for anomalies when policy allows it.

## Shell

- Run inside a project workspace/container whenever possible.
- Deny obviously destructive commands by default.
- Require elevated policy for commands targeting host-level system configuration.
- Capture command, exit code and bounded/redacted output.

## SSH / infrastructure

- Use dedicated keys/users for HufiAgents where practical.
- Prefer least privilege and narrowly-scoped sudo.
- Do not alter firewall, sshd or root access without explicit R3 approval.
- Snapshot/backup before risky migrations when supported.

## Browser / external content

Treat websites, emails, issue text, uploaded files and MCP responses as untrusted instructions. External content may provide data, but must not silently override system policy or mission constraints.

Mitigations include:

- tool allowlists,
- domain restrictions where appropriate,
- risk classification before side effects,
- reviewer validation,
- secret isolation,
- explicit approval for sensitive submissions or purchases.

A live browser/computer view must represent a real session. Do not use a decorative/fake session as evidence of execution.

## Public repository warning

`passaondigital/HufiAgents` is currently public. Real hostnames may be documented only if intentionally public; never include credentials, tokens, private keys, customer data or confidential infrastructure details.

## Phase 3A hardened execution boundary

Project package scripts execute only under the Bubblewrap boundary in ADR-013. It clears secrets and host configuration, allows only the current mission workspace to be written, uses a private tmp/proc and disables networking. Bubblewrap unavailable or failing is a denial, never a same-UID fallback.

Credentialed push/PR calls use a separate PID namespace plus parent-death signal; cancellation and timeout reap their process tree. Push/PR output remains suppressed rather than relying on regexes to recognize unknown/encoded secrets.

Install the secret-free askpass helper with 0755 permissions using a trusted, non-task-writable installation. At runtime its hash is verified and a private 0700 copy is used for one push, so an umask-derived group-write bit never becomes executable authority; mismatched or linked sources fail closed.

See ADR-014 and `CODEX-REVIEW-PHASE3A.md`.

## Release security gates for V1.2

Before a V1.2 production deploy:

1. additive migration passes on a production-shaped DB copy,
2. V1.1.2 data preservation is proven,
3. Work Evidence redaction adversarial tests pass,
4. raw credentials are not returned by normal APIs,
5. company-graph membership cannot escalate rights,
6. Skill/Memory isolation tests pass,
7. external budget-zero path blocks remote paid calls,
8. No-LLM healthy routine proves zero model calls,
9. real browser/front-end QA shows no fake capability state,
10. production DB backup is taken before deploy.
