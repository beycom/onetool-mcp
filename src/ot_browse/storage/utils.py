"""Storage utilities - YAML dumping, text cleaning, file helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ot_browse.config import get_config

# Default max text length for YAML output (overridden by config)
_max_text_length: int = 400


def set_max_text_length(length: int) -> None:
    """Set the max text length for YAML output."""
    global _max_text_length
    _max_text_length = length


def clean_text(data: str, max_length: int | None = None) -> str:
    """Clean and truncate text for YAML block style output.

    This is the central function for preparing text fields for YAML serialization.
    It handles:
    - Normalizing line endings (CRLF/CR -> LF)
    - Replacing tabs with spaces
    - Removing BOM and control characters
    - Collapsing runs of whitespace to single space
    - Truncating to max length with ellipsis

    Args:
        data: Raw text to clean
        max_length: Max chars (None uses global config, 0 for unlimited)

    Returns:
        Cleaned text ready for YAML output
    """
    if not data:
        return ""

    import re

    # Remove BOM
    cleaned = data.lstrip("\ufeff")
    # Remove control characters (keep only printable + whitespace)
    cleaned = "".join(c for c in cleaned if ord(c) >= 32 or c in "\t\n\r")
    # Collapse all whitespace (spaces, tabs, newlines) to single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()

    # Truncate if needed
    if max_length is None:
        max_length = _max_text_length
    if max_length > 0 and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "..."

    return cleaned


# Custom YAML Dumper with block style for long strings
class _BlockStyleDumper(yaml.Dumper):
    """Custom Dumper that uses block style for multiline/long strings."""

    pass


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Use block style for multiline or long strings."""
    if "\n" in data or len(data) > 60:
        cleaned = clean_text(data)
        if cleaned:
            return dumper.represent_scalar("tag:yaml.org,2002:str", cleaned, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockStyleDumper.add_representer(str, _str_representer)


def yaml_dump(data: Any) -> str:
    """Dump data to YAML with block style for long strings."""
    return yaml.dump(
        data,
        Dumper=_BlockStyleDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def _get_sessions_dir() -> Path:
    """Get the sessions directory from config."""
    config = get_config()
    return config.get_sessions_path()


def get_file_size(path: Path) -> str:
    """Get human-readable file size.

    Args:
        path: Path to file.

    Returns:
        Size string like "1.2KB", "3.5MB", or "0B" if not found.
    """
    if not path.exists():
        return "0B"
    size_bytes = path.stat().st_size
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def find_line_numbers(
    html_content: str, annotations: list[dict[str, Any]]
) -> dict[str, int]:
    """Find line numbers for annotations in HTML content.

    Searches for x-inspect attributes to locate each annotation.

    Args:
        html_content: Full HTML content.
        annotations: List of annotation dicts with 'id' key.

    Returns:
        Dict mapping annotation ID to line number.
    """
    result: dict[str, int] = {}
    if not html_content or not annotations:
        return result

    # Build search patterns for each annotation
    search_terms: dict[str, str] = {}  # term -> ann_id
    for ann in annotations:
        ann_id = ann.get("id", "")
        if ann_id:
            # Search for x-inspect="id" or x-inspect="id:label"
            search_terms[f'x-inspect="{ann_id}"'] = ann_id
            search_terms[f"x-inspect='{ann_id}'"] = ann_id

    if not search_terms:
        return result

    # Single pass through HTML
    remaining = set(search_terms.keys())
    for line_num, line in enumerate(html_content.splitlines(), 1):
        found = []
        for term in remaining:
            if term in line:
                ann_id = search_terms[term]
                if ann_id not in result:  # First occurrence wins
                    result[ann_id] = line_num
                found.append(term)
        for term in found:
            remaining.discard(term)
        if not remaining:
            break

    return result
