"""Last-line defence against credentials reaching local technical logs."""

from __future__ import annotations

import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]+"),
    re.compile(
        r"(?i)\b(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|password|secret)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
)


def redact_log_text(value: str) -> str:
    redacted = value
    redacted = _SECRET_PATTERNS[0].sub("Bearer [REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[1].sub("sk-[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[2].sub(r"\1\2[REDACTED]", redacted)
    return redacted
