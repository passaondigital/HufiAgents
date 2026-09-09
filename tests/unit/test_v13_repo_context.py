"""Unit tests for V1.3A Repository Context Service.

Covers:
- Objective-driven file selection and search term extraction
- Related test file discovery
- Exclusion of secret files (.env, .key, id_rsa, credentials, etc.)
- Exclusion of binary files (.png, .zip, etc.)
- Path traversal and symlink escape blocking
- File excerpt bounding and line numbering
- Objective terms ranking
- Secret redaction within source excerpts
- Bounded traversal for large repositories
- Git diff / status summary inclusion
"""

import subprocess

from hufiagents.repo_context import RepoContextService, is_binary_file, is_secret_file


def test_secret_file_filtering():
    assert is_secret_file(".env") is True
    assert is_secret_file(".env.production") is True
    assert is_secret_file("id_rsa") is True
    assert is_secret_file("id_rsa.pub") is True
    assert is_secret_file("server.key") is True
    assert is_secret_file("credentials.json") is True
    assert is_secret_file("secrets.yaml") is True
    assert is_secret_file("auth.py") is False


def test_binary_file_filtering():
    assert is_binary_file("image.png") is True
    assert is_binary_file("archive.zip") is True
    assert is_binary_file("module.pyc") is True
    assert is_binary_file("main.py") is False


def test_objective_selects_relevant_source_and_related_test(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "tests").mkdir()

    (repo / "src" / "auth.py").write_text("def login_session_recovery(): pass\n", encoding="utf-8")
    (repo / "src" / "billing.py").write_text("def process_invoice(): pass\n", encoding="utf-8")
    (repo / "tests" / "test_auth.py").write_text(
        "def test_login_session(): pass\n", encoding="utf-8"
    )
    (repo / ".env").write_text("SECRET=123456\n", encoding="utf-8")
    (repo / "server.key").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    (repo / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    svc = RepoContextService()
    ctx = svc.assemble_context(repo, "Investigate login session recovery issue")

    selected_paths = [f["path"] for f in ctx["selected_files"]]
    assert any("auth.py" in p for p in selected_paths)
    assert any("test_auth.py" in p for p in selected_paths)
    assert not any(".env" in p for p in selected_paths)
    assert not any("server.key" in p for p in selected_paths)
    assert not any("billing.py" in p for p in selected_paths)
    assert ctx["secret_exclusions_count"] >= 2


def test_objective_terms_affect_ranking(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "auth.py").write_text("def login(): pass\n" * 20, encoding="utf-8")
    (repo / "payment.py").write_text("def stripe_pay(): pass\n" * 20, encoding="utf-8")

    svc = RepoContextService()
    ctx_auth = svc.assemble_context(repo, "login auth check")
    assert ctx_auth["selected_files"][0]["path"] == "auth.py"

    ctx_pay = svc.assemble_context(repo, "stripe payment processing")
    assert ctx_pay["selected_files"][0]["path"] == "payment.py"


def test_path_traversal_and_symlink_blocking(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "valid.py").write_text("print('hello')", encoding="utf-8")

    outside = tmp_path / "outside.py"
    outside.write_text("SECRET_OUTSIDE = 1", encoding="utf-8")

    # Attempt symlink escape
    symlink_path = repo / "symlink_escape.py"
    try:
        symlink_path.symlink_to(outside)
    except OSError:
        pass

    svc = RepoContextService()
    ctx = svc.assemble_context(repo, "search valid outside")

    selected_paths = [f["path"] for f in ctx["selected_files"]]
    assert not any("symlink_escape.py" in p for p in selected_paths)
    assert not any("outside.py" in p for p in selected_paths)


def test_large_file_line_excerpt_bounding(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    # Generate a 500-line file
    lines = [f"line {i}: regular text" for i in range(500)]
    lines[250] = "line 250: TARGET_RECOVERY_KEYWORD = True"
    (repo / "large.py").write_text("\n".join(lines), encoding="utf-8")

    svc = RepoContextService()
    ctx = svc.assemble_context(repo, "TARGET_RECOVERY_KEYWORD")

    assert len(ctx["selected_files"]) == 1
    selected = ctx["selected_files"][0]
    assert selected["path"] == "large.py"
    assert "251:" in selected["content"]  # line numbers 1-indexed
    assert "TARGET_RECOVERY_KEYWORD" in selected["content"]
    assert selected["lines"] != "1-500"  # properly excerpted window


def test_large_repo_bounding(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create 600 small files
    for i in range(600):
        (repo / f"file_{i:03d}.py").write_text(f"# file {i}\n", encoding="utf-8")

    svc = RepoContextService(max_tree_entries=100)
    ctx = svc.assemble_context(repo, "search")

    assert ctx["tree_summary"]["total_entries"] <= 100
    assert ctx["truncated"] is True


def test_secret_redaction_in_source_excerpt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "config.py").write_text(
        "DB_TOKEN = 'secretval123456'\n# auth config for login\n", encoding="utf-8"
    )

    svc = RepoContextService()
    ctx = svc.assemble_context(repo, "login auth config")

    assert len(ctx["selected_files"]) == 1
    content = ctx["selected_files"][0]["content"]
    assert "secretval123456" not in content
    assert "[REDACTED]" in content


def test_git_diff_summary_inclusion(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    (repo / "file.py").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "file.py"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )
    (repo / "file.py").write_text("modified_text", encoding="utf-8")

    svc = RepoContextService()
    ctx = svc.assemble_context(repo, "file modified")
    assert ctx["git_diff_summary"] is not None
    assert "Status:" in ctx["git_diff_summary"]


def test_invalid_repository_root_returns_error(tmp_path):
    svc = RepoContextService()
    ctx = svc.assemble_context(tmp_path / "nonexistent", "check")
    assert "error" in ctx
