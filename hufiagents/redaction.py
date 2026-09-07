import re

SENSITIVE = re.compile(r"secret|password|token|authorization|api[_-]?key|credential", re.I)
PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[\w.\-]+"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+)"),
    re.compile(r"(?i)((?:password|token|secret|api[_-]?key)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----"),
]


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SENSITIVE.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern in PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value[:16000]
    return value
