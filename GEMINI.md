# Gemini / Antigravity Project Instructions

Read and follow this repository's `AGENTS.md` before substantial work.

Core workflow:

**DISCOVER → VERIFY → REUSE → IMPLEMENT → TEST → VERIFY LIVE → DOCUMENT**

Account-wide rules:
- Never guess production state; use `UNKNOWN` when evidence is missing.
- `NOT TESTED` is never `PASS`; `BUILT` is not `PRODUCTION`.
- Reuse existing components and domain models before creating parallel architecture.
- Keep deterministic authority for identity, permissions, money, billing state and destructive actions.
- Never expose raw secrets in Git, prompts, normal docs, memory or work evidence.
- Production requires appropriate tests, security checks, rollback and live verification.
- Persist durable handover/status after substantial work.

Public foundation:
- `passaondigital/hufi-architecture-board/docs/00_UNIVERSAL_PROJECT_STANDARD.md`
- `passaondigital/hufi-architecture-board/docs/01_PROJECT_BOOTSTRAP.md`
- `passaondigital/hufi-architecture-board/docs/02_AGENT_RELEASE_STANDARD.md`

Authorized internal HUFI work may also use the reusable skill library in `passaondigital/hufi-factory/skills/`.

Existing stricter project-specific instructions remain authoritative for this repository.
