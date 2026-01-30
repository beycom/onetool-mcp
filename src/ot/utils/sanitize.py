"""Output sanitization for prompt injection protection.

Protects against indirect prompt injection by sanitizing tool outputs
that may contain malicious payloads designed to trick the LLM.

Three-layer defense:
1. Trigger sanitization: Replace __ot, mcp__onetool patterns
2. Tag sanitization: Remove <external-content-*> patterns
3. GUID-tagged boundaries: Wrap content in unpredictable tags
"""

from __future__ import annotations

import re
import uuid

__all__ = [
    "sanitize_output",
    "sanitize_tag_closes",
    "sanitize_triggers",
    "wrap_external_content",
]

# Regex patterns for trigger detection (case-insensitive)
# Matches: __ot, mcp__onetool, mcp__onetool__run
TRIGGER_PATTERN = re.compile(
    r"(__ot\b|mcp__onetool\w*)",
    re.IGNORECASE,
)

# Pattern for tag injection attempts (both opening and closing)
# Matches: <external-content-*> and </external-content-*>
TAG_PATTERN = re.compile(
    r"</?external-content-[a-f0-9-]*>?",
    re.IGNORECASE,
)


def sanitize_triggers(content: str) -> str:
    """Replace trigger patterns that could invoke OneTool.

    Replaces patterns like __ot, mcp__onetool, mcp__onetool__run
    with [REDACTED:trigger] to prevent indirect prompt injection.

    Args:
        content: String content that may contain trigger patterns

    Returns:
        Content with triggers replaced by [REDACTED:trigger]
    """
    if not content:
        return content

    return TRIGGER_PATTERN.sub("[REDACTED:trigger]", content)


def sanitize_tag_closes(content: str) -> str:
    """Remove boundary tag patterns that could escape or confuse boundaries.

    Attackers may include </external-content-*> to close the boundary early,
    or <external-content-*> to create fake boundaries and confuse parsing.

    Args:
        content: String content that may contain boundary tag attempts

    Returns:
        Content with boundary tag patterns replaced by [REDACTED:tag]
    """
    if not content:
        return content

    return TAG_PATTERN.sub("[REDACTED:tag]", content)


def wrap_external_content(
    content: str,
    source: str | None = None,
) -> str:
    """Wrap external content in GUID-tagged boundaries.

    Applies all three defense layers:
    1. Sanitize trigger patterns
    2. Sanitize tag patterns
    3. Wrap in unpredictable GUID boundary tags

    Args:
        content: External content to wrap
        source: Optional source identifier (e.g., URL, tool name)

    Returns:
        Content wrapped in boundary tags with sanitization applied.
        Empty content is still wrapped (boundaries always apply).
    """
    # Generate unique boundary ID (12 hex chars = 48 bits entropy)
    boundary_id = uuid.uuid4().hex[:12]

    # Apply sanitization layers
    content = sanitize_triggers(content)
    content = sanitize_tag_closes(content)

    # Build source attribute if provided
    source_attr = f' source="{source}"' if source else ""

    # Wrap in boundary tags
    return f"<external-content-{boundary_id}{source_attr}>\n{content}\n</external-content-{boundary_id}>"


def sanitize_output(
    content: str,
    source: str | None = None,
    enabled: bool = True,
) -> str:
    """Sanitize tool output for prompt injection protection.

    Main entry point for output sanitization. When enabled, wraps content
    in boundary tags and sanitizes trigger patterns.

    Args:
        content: Tool output content
        source: Optional source identifier (e.g., tool name, URL)
        enabled: Whether sanitization is enabled (default True)

    Returns:
        Sanitized content wrapped in boundary tags, or original if disabled
    """
    if not enabled:
        return content

    return wrap_external_content(content, source=source)
