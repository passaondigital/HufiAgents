"""Server-side login for the V1 web UI/API (docs/DECISIONS.md ADR-015).

Stdlib only -- no new dependency. A password is stored as a salted PBKDF2
hash (never plaintext); a session is a signed, expiring cookie value the
server can verify without any server-side session store. Auth is opt-in: if
`admin_username`/`admin_password_hash` are not both configured, `enabled` is
False and callers must treat every request as already authorized (this keeps
the existing test suite, which never sets these, unaffected).
"""

import hashlib
import hmac
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

PBKDF2_ITERATIONS = 260_000
SESSION_TTL_SECONDS = 7 * 24 * 3600
COOKIE_NAME = "hufi_session"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(candidate, expected)


def issue_session(username: str, secret: str, *, now: float | None = None) -> str:
    expires_at = int((now if now is not None else time.time()) + SESSION_TTL_SECONDS)
    payload = f"{username}:{expires_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}"
    return urlsafe_b64encode(token.encode()).decode()


def verify_session(cookie_value: str, secret: str, *, now: float | None = None) -> str | None:
    try:
        token = urlsafe_b64decode(cookie_value.encode()).decode()
        username, expires_at, signature = token.rsplit(":", 2)
    except (ValueError, UnicodeDecodeError):
        return None
    payload = f"{username}:{expires_at}"
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    if int(expires_at) < (now if now is not None else time.time()):
        return None
    return username
