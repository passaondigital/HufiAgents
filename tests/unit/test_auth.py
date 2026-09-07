import time

from hufiagents import auth


def test_hash_and_verify_password_roundtrip():
    stored = auth.hash_password("correct horse battery staple")
    assert auth.verify_password("correct horse battery staple", stored)
    assert not auth.verify_password("wrong", stored)


def test_password_hash_is_salted_and_never_plaintext():
    first = auth.hash_password("same-password")
    second = auth.hash_password("same-password")
    assert first != second  # different salt each time
    assert "same-password" not in first


def test_verify_password_rejects_malformed_stored_value():
    assert not auth.verify_password("anything", "not-a-real-hash")
    assert not auth.verify_password("anything", "bcrypt$4$salt$digest")


def test_session_roundtrip_and_expiry():
    secret = "session-secret"
    token = auth.issue_session("pascal", secret, now=1000)
    assert auth.verify_session(token, secret, now=1000) == "pascal"
    # still valid just before TTL expiry
    assert auth.verify_session(token, secret, now=1000 + auth.SESSION_TTL_SECONDS - 1) == "pascal"
    # expired
    assert auth.verify_session(token, secret, now=1000 + auth.SESSION_TTL_SECONDS + 1) is None


def test_session_rejects_wrong_secret_and_tampering():
    token = auth.issue_session("pascal", "secret-a", now=time.time())
    assert auth.verify_session(token, "secret-b") is None
    assert auth.verify_session(token[:-1] + ("A" if token[-1] != "A" else "B"), "secret-a") is None
    assert auth.verify_session("not-base64!!", "secret-a") is None
