"""Secret-literal redaction for log output.

Redacts secret-shaped literals (API keys, tokens, passwords, connection strings)
that may be inlined into a command, prepared code, or error message before they
reach any emitted log line.
"""

from __future__ import annotations

import re

# (pattern, replacement) tuples applied in order. Kept as the single source of
# truth for secret-shaped literal detection (also used by mem.write() redaction).
SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED:api_key]"),
    (r"ghp_[a-zA-Z0-9]{36,}", "[REDACTED:github_token]"),
    (r"gho_[a-zA-Z0-9]{36,}", "[REDACTED:github_token]"),
    (r"github_pat_[a-zA-Z0-9_]{22,}", "[REDACTED:github_token]"),
    (r"xoxb-[a-zA-Z0-9\-]+", "[REDACTED:slack_token]"),
    (r"xoxp-[a-zA-Z0-9\-]+", "[REDACTED:slack_token]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED:aws_key]"),
    (r"(?i)password\s*[=:]\s*\S+", "[REDACTED:password]"),
    (
        r"(?i)(?:api[_-]?key|token|secret)\s*[=:]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?",
        "[REDACTED:secret]",
    ),
    (
        r"(?i)(?:postgres|mysql|mongodb|redis)://\S+:\S+@\S+",
        "[REDACTED:connection_string]",
    ),
]

_COMPILED = [
    (re.compile(pattern), replacement) for pattern, replacement in SECRET_PATTERNS
]


def redact_secrets(value: str) -> str:
    """Redact secret-shaped literals from a string, applying each pattern in order."""
    for regex, replacement in _COMPILED:
        value = regex.sub(replacement, value)
    return value
