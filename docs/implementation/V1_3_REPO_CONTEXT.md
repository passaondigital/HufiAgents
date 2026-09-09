# V1.3 Repository Context Service (RepoContextService)

Bounded, deterministic, local repository context discovery and injection for Engineering Agents in HufiAgents V1.3.

## Overview
`RepoContextService` provides objective-driven local workspace inspection for engineering tasks. It extracts search terms from task objectives, inspects directory trees, scores source files and test candidates, bounds excerpts, redacts secrets, and injects structured repository context into Orchestrator model completion requests without using vector databases, external embeddings, or remote code intelligence APIs.

## Key Architecture & Features

### 1. Discovery & Search Terms
- Objective text is tokenized into search terms, excluding common stop words (`the`, `a`, `check`, `fix`, `prüfe`, etc.).
- Bounded traversal (`os.walk`) lists relative file paths up to depth 6 and maximum 500 tree entries.

### 2. Candidate Selection & Scoring
- Files are scored based on:
  - Path matches against extracted objective search terms (10 points per term match).
  - Bounded content search (2 points per term occurrence, capped at 10 per term).
- Source files with top scores are selected for excerpt extraction.

### 3. Related Test Discovery
- Automatically locates test files matching selected source file stems in standard test directories (`tests/`, `test/`, `spec/`).
- Includes matching test files in candidate list for inspection.

### 4. Excerpt Bounding & Line Ranges
- Small files (<= 200 lines, <= 64 KB) are included in full with 1-indexed line numbers (`1-N`).
- Large files are excerpted around search term matches (window offset -20 to +80 lines) with line number prefixes.
- Hard limits: max 500 tree entries, max depth 6, max candidate files 20, max selected files 8, max file size 64 KB, total context 160 KB.

### 5. Exclusion Rules & Secret Handling
- **Directory Exclusions:** `.git`, `node_modules`, `vendor`, `dist`, `build`, `coverage`, `.cache`, `__pycache__`, `.venv`, `venv`.
- **Binary Exclusions:** Images (`.png`, `.jpg`), archives (`.zip`, `.gz`), compiled binaries (`.pyc`, `.exe`, `.so`, `.db`).
- **Secret File Exclusion:** Hard blocked before content reading: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `credentials*`, `secrets*`.
- **Inline Secret Redaction:** All extracted text excerpts and git summaries are processed through `redact()` before context inclusion.

### 6. Path Isolation & Symlink Safety
- Repository root must exist, be a directory, and not be a symlink.
- Absolute paths outside root and symlinks escaping the workspace boundary are strictly blocked.

### 7. Git Status & Diff Summary
- Includes safe `git status --short` and `git diff --stat` output (bounded to 2000 characters with secret redaction) if workspace is a git repository.

### 8. Orchestrator Integration
- Automatically activated in `Orchestrator._execute` for engineering tasks (`is_engineering=True` based on agent role or allowed tools like `files`, `git`, `code`, `repo`, `terminal`, `workspace`) when workspace root exists.
- Injects structured `repository_context` dictionary into CompletionRequest JSON payload.

## Model Request Verification
In integration tests (`test_golden_engineering_repo_context`), synthetic mission requests with objective *"Investigate the login session recovery problem"* verified that:
1. `src/auth.py` containing `AUTH_SESSION_SENTINEL_47391` reached model `CompletionRequest`.
2. `.env` containing `SUPER_SECRET_TOKEN=repo_secret_999` was strictly excluded and absent from the provider payload.
3. Inline secrets in source were sanitized via `[REDACTED]`.

## Known Limitations
- Purely local and deterministic keyword search; no semantic vector search or AST cross-file jump resolution.
- Bounded file excerpts cover primary term match windows rather than full multi-file call-graph traces.
