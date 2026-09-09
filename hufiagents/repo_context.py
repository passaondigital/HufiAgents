"""V1.3A Repository Context Service for Engineering Agents.

Provides objective-driven, bounded, local repository inspection for engineering tasks.
Assembles relevant source excerpts, test files, and git diff summaries into model context
without relying on external vector databases, embeddings, or network search services.
"""

import os
import re
from pathlib import Path
from typing import Any

from hufiagents.redaction import redact

# Common directories to exclude from automatic indexing
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    ".cache",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

# Binary and non-text file extensions to skip
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".bin",
    ".dat",
}

# Secret-bearing files to exclude strictly from model context
SECRET_FILE_PATTERNS = [
    re.compile(r"^\.env(?:\..*)?$", re.I),
    re.compile(r"^.*\.pem$", re.I),
    re.compile(r"^.*\.key$", re.I),
    re.compile(r"^id_rsa(?:\..*)?$", re.I),
    re.compile(r"^id_ed25519(?:\..*)?$", re.I),
    re.compile(r"^.*credentials.*$", re.I),
    re.compile(r"^.*secrets.*$", re.I),
    re.compile(r"^.*credential.*$", re.I),
]

STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "in",
    "it",
    "to",
    "for",
    "and",
    "or",
    "on",
    "of",
    "at",
    "by",
    "with",
    "this",
    "that",
    "from",
    "as",
    "be",
    "bug",
    "issue",
    "problem",
    "fix",
    "check",
    "test",
    "investigate",
    "please",
    "prüfe",
    "bitte",
}


def is_secret_file(filename: str) -> bool:
    """Return True if filename matches sensitive/secret file patterns."""
    return any(pat.match(filename) for pat in SECRET_FILE_PATTERNS)


def is_binary_file(filename: str) -> bool:
    """Return True if filename extension indicates a binary file."""
    ext = Path(filename).suffix.lower()
    return ext in BINARY_EXTENSIONS


def extract_search_terms(objective: str) -> list[str]:
    """Extract distinct search terms from the objective text."""
    words = re.findall(r"\w+", objective.lower())
    terms = [w for w in words if len(w) > 1 and w not in STOP_WORDS]
    return list(dict.fromkeys(terms))  # preserve order, dedup


class RepoContextService:
    """Bounded, deterministic repository context assembler."""

    def __init__(
        self,
        max_tree_entries: int = 500,
        max_depth: int = 6,
        max_candidate_files: int = 20,
        max_selected_files: int = 8,
        max_file_bytes: int = 64000,
        max_total_context_bytes: int = 160000,
    ):
        self.max_tree_entries = max_tree_entries
        self.max_depth = max_depth
        self.max_candidate_files = max_candidate_files
        self.max_selected_files = max_selected_files
        self.max_file_bytes = max_file_bytes
        self.max_total_context_bytes = max_total_context_bytes

    def assemble_context(self, root_path: Path, objective: str) -> dict[str, Any]:
        """Assemble structured repository context for the given objective.

        Safety guarantees:
        - Root must exist, be a directory, and not be a symlink.
        - Absolute paths outside root or symlink escapes are strictly blocked.
        - Secret files (.env, keys, etc.) are excluded before content reading.
        - Redaction is applied to all source text excerpts.
        """
        root = Path(root_path).resolve()
        if not root.exists() or not root.is_dir():
            return {"error": "invalid repository root"}
        if root.is_symlink():
            raise PermissionError("workspace root cannot be a symlink")

        terms = extract_search_terms(objective)
        tree_entries: list[str] = []
        candidates: list[dict[str, Any]] = []
        secret_exclusions_count = 0
        truncated = False

        # 1. Traversal & Discovery
        for current_root, dirs, files in os.walk(root):
            rel_dir = Path(current_root).relative_to(root)
            depth = len(rel_dir.parts)

            # Prune excluded directories
            dirs[:] = [
                d for d in dirs if d not in EXCLUDED_DIRS and not (root / rel_dir / d).is_symlink()
            ]

            if depth > self.max_depth:
                dirs.clear()
                continue

            for f in files:
                if len(tree_entries) >= self.max_tree_entries:
                    truncated = True
                    dirs.clear()
                    break

                rel_path = (rel_dir / f) if rel_dir != Path(".") else Path(f)
                rel_str = str(rel_path)
                tree_entries.append(rel_str)

                # Check secret exclusion
                if is_secret_file(f):
                    secret_exclusions_count += 1
                    continue

                # Skip binary files
                if is_binary_file(f):
                    continue

                full_path = root / rel_path
                # Safety check against symlinks / workspace escape
                if full_path.is_symlink():
                    continue
                try:
                    if not full_path.resolve().is_relative_to(root):
                        continue
                except Exception:
                    continue

                # 2. Ranking & Scoring
                score, match_reasons = self._score_file(rel_str, full_path, terms)
                if score > 0:
                    candidates.append(
                        {
                            "rel_path": rel_str,
                            "full_path": full_path,
                            "score": score,
                            "reasons": match_reasons,
                        }
                    )

        # Sort candidates by score descending
        candidates.sort(key=lambda c: c["score"], reverse=True)
        candidates = candidates[: self.max_candidate_files]

        # 3. Find related tests for top source candidates
        top_selected, related_tests = self._select_and_find_tests(candidates, root)

        # 4. Read source excerpts and package context
        selected_files_output: list[dict[str, Any]] = []
        total_bytes = 0

        for item in top_selected[: self.max_selected_files]:
            if total_bytes >= self.max_total_context_bytes:
                truncated = True
                break

            excerpt = self._read_file_excerpt(
                item["full_path"], terms, max_bytes=self.max_file_bytes
            )
            if not excerpt:
                continue

            content_text = redact(excerpt["content"])
            total_bytes += len(content_text.encode("utf-8"))

            selected_files_output.append(
                {
                    "path": item["rel_path"],
                    "lines": excerpt["lines"],
                    "reason": ", ".join(item["reasons"]),
                    "content": content_text,
                }
            )

        # Build git diff summary if git repo
        git_diff_summary = self._git_diff_summary(root)

        return {
            "repository_root": str(root),
            "objective": objective,
            "tree_summary": {
                "total_entries": len(tree_entries),
                "sample_entries": tree_entries[:20],
            },
            "selected_files": selected_files_output,
            "related_tests": related_tests,
            "git_diff_summary": git_diff_summary,
            "secret_exclusions_count": secret_exclusions_count,
            "truncated": truncated,
        }

    def _score_file(
        self, rel_path: str, full_path: Path, terms: list[str]
    ) -> tuple[int, list[str]]:
        """Score file candidate based on path match and term hits in content."""
        score = 0
        reasons: list[str] = []
        rel_lower = rel_path.lower()

        # Path matching
        for term in terms:
            if term in rel_lower:
                score += 10
                reasons.append(f"path match: '{term}'")

        # Content matching (bounded check)
        try:
            stat = full_path.stat()
            if stat.st_size > 500000:  # skip files > 500 KB for scoring
                return score, reasons

            with full_path.open("r", encoding="utf-8", errors="ignore") as f:
                content = f.read(32000).lower()

            for term in terms:
                count = content.count(term)
                if count > 0:
                    score += min(count * 2, 10)
                    reasons.append(f"content match: '{term}' ({count}x)")
        except Exception:
            pass

        return score, reasons

    def _select_and_find_tests(
        self, candidates: list[dict[str, Any]], root: Path
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Select top source files and discover matching test files."""
        selected: list[dict[str, Any]] = []
        related_tests: set[str] = set()

        for c in candidates:
            selected.append(c)
            path_stem = Path(c["rel_path"]).stem.lower()

            # Find matching test files in repo
            for test_dir in ["tests", "test", "spec"]:
                t_dir = root / test_dir
                if t_dir.exists() and t_dir.is_dir():
                    for t_root, _, files in os.walk(t_dir):
                        for f in files:
                            f_lower = f.lower()
                            stripped = f_lower.replace("test_", "").replace("_test", "")
                            if path_stem in f_lower or stripped.startswith(path_stem):
                                rel_t = str(Path(t_root, f).relative_to(root))
                                related_tests.add(rel_t)

        # Also add related test files to candidate list if not already selected
        for test_path_str in related_tests:
            full_t_path = root / test_path_str
            if full_t_path.exists() and not any(s["rel_path"] == test_path_str for s in selected):
                selected.append(
                    {
                        "rel_path": test_path_str,
                        "full_path": full_t_path,
                        "score": 15,
                        "reasons": ["related test file"],
                    }
                )

        return selected, sorted(related_tests)

    def _read_file_excerpt(
        self, full_path: Path, terms: list[str], max_bytes: int = 64000
    ) -> dict[str, Any] | None:
        """Read file content with line numbers. Excerpt if file is large."""
        try:
            with full_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return None

        total_lines = len(lines)
        if total_lines == 0:
            return None

        # Small file -> include full file with line numbers
        full_text = "".join(lines)
        if len(full_text.encode("utf-8")) <= max_bytes and total_lines <= 200:
            numbered_lines = [f"{i + 1:4d}: {line.rstrip()}" for i, line in enumerate(lines)]
            return {
                "lines": f"1-{total_lines}",
                "content": "\n".join(numbered_lines),
            }

        # Large file -> find best excerpt window around term matches
        match_line_indices = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(term in line_lower for term in terms):
                match_line_indices.append(i)

        if not match_line_indices:
            # Fall back to first 100 lines
            start, end = 0, min(100, total_lines)
        else:
            first_match = match_line_indices[0]
            start = max(0, first_match - 20)
            end = min(total_lines, first_match + 80)

        excerpt_lines = lines[start:end]
        numbered_excerpt = [
            f"{start + i + 1:4d}: {line.rstrip()}" for i, line in enumerate(excerpt_lines)
        ]

        return {
            "lines": f"{start + 1}-{end}",
            "content": "\n".join(numbered_excerpt),
        }

    def _git_diff_summary(self, root: Path) -> str | None:
        """Return safe git diff/status summary if root is a git repository."""
        git_dir = root / ".git"
        if not git_dir.exists():
            return None

        try:
            import subprocess

            status_res = subprocess.run(
                ["git", "-C", str(root), "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            diff_res = subprocess.run(
                ["git", "-C", str(root), "diff", "--stat"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            summary_parts = []
            if status_res.returncode == 0 and status_res.stdout.strip():
                summary_parts.append("Status:\n" + status_res.stdout.strip()[:1000])
            if diff_res.returncode == 0 and diff_res.stdout.strip():
                summary_parts.append("Diff Stat:\n" + diff_res.stdout.strip()[:1000])

            if summary_parts:
                return redact("\n".join(summary_parts)[:2000])
        except Exception:
            pass
        return None
