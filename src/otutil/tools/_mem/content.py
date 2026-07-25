"""Content helpers: hashing, SQL filters, redaction, validation, markdown."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from loguru import logger

from ot.logging import LogEntry
from otutil.tools._content_util import HEADING_RE as _HEADING_RE
from otutil.tools._content_util import build_toc as _build_toc
from otutil.tools._content_util import parse_headings as _parse_headings

from .config import _BUILTIN_REDACTION_PATTERNS, VALID_CATEGORIES, _get_config


def _content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for dedup."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _topic_filter(topic: str | None, *, column: str = "topic") -> tuple[str, list[Any]]:
    """Build SQL WHERE clause for topic filtering.

    Supports exact match and prefix matching with trailing /. `column` allows
    a qualified name (e.g. "m.topic") in joined queries.
    Returns (sql_fragment, params).
    """
    if not topic:
        return "", []

    if topic.endswith("/"):
        return f" AND ({column} = ? OR {column} LIKE ?)", [
            topic.rstrip("/"),
            topic + "%",
        ]
    elif "*" in topic:
        like_pattern = topic.replace("*", "%")
        return f" AND {column} LIKE ?", [like_pattern]
    else:
        return f" AND {column} = ?", [topic]


def _tags_filter_sql(tags: list[str], *, column: str = "tags") -> tuple[str, list[str]]:
    """Build SQL WHERE clause fragment for tag filtering.

    Tags are stored as a JSON array in a TEXT column. Uses json_each() to
    check if any of the provided tags exist in the stored array. `column`
    allows a qualified name (e.g. "m.tags") in joined queries.
    Returns (sql_fragment, params).
    """
    placeholders = ", ".join("?" for _ in tags)
    sql = f" AND EXISTS (SELECT 1 FROM json_each({column}) WHERE json_each.value IN ({placeholders}))"
    return sql, tags


def _redact(content: str) -> str:
    """Redact secrets and PII from content.

    Uses built-in patterns plus any additional patterns from config.
    """
    config = _get_config()
    if not config.redaction_enabled:
        return content

    result = content
    for pattern, replacement in _BUILTIN_REDACTION_PATTERNS:
        result = re.sub(pattern, replacement, result)

    for pattern in config.redaction_patterns:
        try:
            result = re.sub(pattern, "[REDACTED]", result)
        except re.error as e:
            logger.warning(
                LogEntry(
                    event="mem.content.redaction_pattern_invalid",
                    pattern=pattern,
                    errorType=type(e).__name__,
                    error=str(e),
                )
            )

    return result


def _validate_tags(tags: list[str] | None) -> list[str]:
    """Validate tags against whitelist if configured.

    Returns validated tags or raises ValueError.
    """
    if not tags:
        return []

    config = _get_config()
    if not config.tags_whitelist:
        return tags

    validated = []
    for tag in tags:
        allowed = False
        for prefix in config.tags_whitelist:
            if prefix.endswith("/*"):
                if tag.startswith(prefix[:-1]) or tag == prefix[:-2]:
                    allowed = True
                    break
            elif tag == prefix:
                allowed = True
                break
        if not allowed:
            raise ValueError(
                f"Tag '{tag}' not in whitelist. Allowed: {config.tags_whitelist}"
            )
        validated.append(tag)
    return validated


def _validate_category(category: str) -> str:
    """Validate category value."""
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    return category


def _encode_sections(headings: list[dict[str, Any]]) -> str:
    """Encode parsed headings into pipe-delimited section index string.

    Format: ``heading:start-end|heading:start-end``

    Pipes in headings are escaped as ``\\|`` to avoid splitting ambiguity.
    """
    parts = []
    for h in headings:
        escaped = h["heading"].replace("\\", "\\\\").replace("|", "\\|")
        parts.append(f"{escaped}:{h['start']}-{h['end']}")
    return "|".join(parts)


def _decode_sections(encoded: str) -> list[dict[str, Any]]:
    """Decode pipe-delimited section index string back to heading dicts.

    Handles escaped pipes (``\\|``) in headings.
    """
    if not encoded:
        return []
    # Split on unescaped pipes: split on | that is not preceded by \
    # We use a two-pass approach: replace escaped pipes with a placeholder,
    # split, then restore.
    placeholder = "\x00"
    safe = encoded.replace("\\|", placeholder)
    sections = []
    for part in safe.split("|"):
        part = part.replace(placeholder, "|")
        # Split on last colon to handle headings containing colons
        colon_idx = part.rfind(":")
        if colon_idx == -1:
            continue
        heading = part[:colon_idx].replace("\\\\", "\\")
        range_str = part[colon_idx + 1 :]
        dash_idx = range_str.find("-")
        if dash_idx == -1:
            continue
        try:
            start = int(range_str[:dash_idx])
            end = int(range_str[dash_idx + 1 :])
        except ValueError:
            continue
        sections.append({"heading": heading, "start": start, "end": end})
    return sections


def _check_staleness(meta: dict[str, str]) -> str:
    """Check staleness of a file-backed memory.

    Returns one of: "fresh", "stale", "missing", "skipped".
    """
    source = meta.get("source")
    source_mtime = meta.get("source_mtime")
    if not source or not source_mtime:
        return "skipped"
    source_path = Path(source)
    if not source_path.exists():
        return "missing"
    current_mtime = source_path.stat().st_mtime
    if current_mtime > float(source_mtime):
        return "stale"
    return "fresh"


__all__ = [
    "VALID_CATEGORIES",
    "_BUILTIN_REDACTION_PATTERNS",
    "_HEADING_RE",
    "_build_toc",
    "_check_staleness",
    "_content_hash",
    "_decode_sections",
    "_encode_sections",
    "_parse_headings",
    "_redact",
    "_tags_filter_sql",
    "_topic_filter",
    "_validate_category",
    "_validate_tags",
]
