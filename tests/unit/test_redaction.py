"""redact() is the only barrier between model/tool output and persisted audit/API
data (docs/SECURITY.md: never print secret values into logs). It had no direct
test coverage before this review; only exercised incidentally through other tests."""

from hufiagents.redaction import redact


def test_redacts_known_secret_key_names():
    out = redact({"password": "hunter2", "api_key": "abc", "tokens": 42, "budget_tokens": 10})
    assert out["password"] == "[REDACTED]"
    assert out["api_key"] == "[REDACTED]"
    # Numeric usage-accounting fields share the "token" substring but are not secrets.
    assert out["tokens"] == 42
    assert out["budget_tokens"] == 10


def test_redacts_nested_structures():
    out = redact({"outer": {"inner": [{"secret": "x"}, "plain"]}})
    assert out["outer"]["inner"][0]["secret"] == "[REDACTED]"
    assert out["outer"]["inner"][1] == "plain"


def test_redacts_bearer_tokens_in_free_text():
    assert redact("Authorization: Bearer sk-abc123.def") == "Authorization: [REDACTED]"


def test_redacts_known_credential_prefixes():
    for token in ["ghp_" + "a" * 36, "github_pat_" + "b" * 20, "sk-" + "c" * 20]:
        assert token not in redact(f"leaked {token} in output")


def test_redacts_key_value_pairs_in_free_text():
    assert "hunter2" not in redact("password=hunter2; continuing")
    assert "hunter2" not in redact("token: hunter2\n")


def test_redacts_private_key_blocks():
    block = "-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----"
    assert "MIIB" not in redact(f"key follows: {block}")


def test_bounds_string_length():
    assert len(redact("x" * 20000)) == 16000


def test_passthrough_for_non_secret_scalars():
    assert redact(42) == 42
    assert redact(None) is None
    assert redact(True) is True


def test_redacts_adversarial_pat_and_environment_secret():
    fake_pat = "ghp_" + "a" * 36
    output = redact(f"tool output: {fake_pat}\nPASSWORD=hunter2")
    assert fake_pat not in output
    assert "hunter2" not in output
    assert "tool output" in output


def test_redacts_credentialized_git_remote_and_http_headers():
    value = (
        "remote=https://alice:super-secret@example.test/repo.git\n"
        "Authorization: Basic dXNlcjpzZWNyZXQ=\n"
        "Cookie: sessionid=private-session"
    )
    output = redact(value)
    for secret in ("super-secret", "dXNlcjpzZWNyZXQ=", "private-session"):
        assert secret not in output
    assert "Authorization: [REDACTED]" in output


def test_harmless_text_is_not_over_redacted():
    value = "The tokenizer contract is stable; this session discusses a token budget."
    assert redact(value) == value
