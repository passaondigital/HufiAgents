import re

SENSITIVE = re.compile(
    r"secret|password|passwd|token|authorization|api[_-]?key|credential|"
    r"private[_-]?key|cookie|session(?:[_-]?id)?|client[_-]?secret|access[_-]?key",
    re.I,
)
PATTERNS = [
    # Explicit test/sentinel-style secret identifiers must not survive in any
    # visible surface even when they are not written as key=value.
    re.compile(r"\b[A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|API_KEY)[A-Z0-9_]*\b(?!\s*[=:])"),
    # Header values (including Basic auth) and cookie/session headers.
    re.compile(r"(?i)((?:authorization|proxy-authorization)\s*:\s*)[^\r\n]+"),
    re.compile(r"(?i)((?:cookie|set-cookie)\s*:\s*)[^\r\n]+"),
    re.compile(r"(?i)(bearer\s+)[\w.\-]+"),
    re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|"
        r"(?:memory|browser|test)-secret-[A-Za-z0-9_-]+)"
    ),
    # Environment/config and command output key/value forms.  The key is
    # retained for diagnostics, while its value is never persisted.
    re.compile(
        r"(?i)((?:password|passwd|token|secret|api[_-]?key|client[_-]?secret|"
        r"access[_-]?key|private[_-]?key|session(?:[_-]?id)?|cookie)\s*[=:]\s*)"
        r"[^\s,;&]+"
    ),
    # URLs such as https://user:password@example.test or a credentialized git
    # remote.  Redact the complete URL to avoid leaking the username too.
    re.compile(r"(?i)\b(?:https?|ssh|git)://[^\s/@]+:[^\s@]+@[^\s]+"),
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----"),
]


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if SENSITIVE.search(k) and k not in {"tokens", "budget_tokens"}
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern in PATTERNS:
            value = pattern.sub(
                lambda match: f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]",
                value,
            )
        return value[:16000]
    return value
