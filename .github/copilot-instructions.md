# HUFI Account Project Standard for GitHub Copilot

Before substantial work, read and follow the repository `AGENTS.md` plus existing project-specific instructions.

Core workflow:

**DISCOVER → VERIFY → REUSE → IMPLEMENT → TEST → VERIFY LIVE → DOCUMENT**

Rules:
- Never guess production state; use `UNKNOWN` when evidence is missing.
- `NOT TESTED` is never `PASS`; `BUILT` is not `PRODUCTION`.
- Reuse existing code, services, schemas and components before adding parallel architecture.
- Keep deterministic authority for identity, permissions, money, billing state and destructive actions.
- Never expose raw secrets in Git, prompts, normal docs, memory or work evidence.
- Require suitable tests, rollback and post-deploy verification before calling work production-ready.
- Persist a handover/status update after substantial work.

Public account foundation:
- `passaondigital/hufi-architecture-board/docs/00_UNIVERSAL_PROJECT_STANDARD.md`
- `passaondigital/hufi-architecture-board/docs/01_PROJECT_BOOTSTRAP.md`
- `passaondigital/hufi-architecture-board/docs/02_AGENT_RELEASE_STANDARD.md`

Authorized internal HUFI agents may additionally use:
- `passaondigital/hufi-factory/skills/`
- `passaondigital/hufi-factory/templates/PROJECT_STARTER/`

Project-specific instructions in this repository override generic workflow preferences where they are stricter or more specific.
