"""Shared attachment path validation and text loading."""

from __future__ import annotations

import re
from pathlib import Path

PATH_PATTERN = re.compile(r"[A-Za-z0-9._/-]+\Z")
MAX_ATTACHMENT_BYTES = 256 * 1024


def inspect_attachment(
    model_dir: Path, relative: str
) -> tuple[str | None, str | None, int]:
    """Validate and read one relative UTF-8 attachment path."""
    if (
        PATH_PATTERN.fullmatch(relative) is None
        or relative.startswith("/")
        or any(part in ("", "..") for part in relative.split("/"))
    ):
        return "invalid_path", None, 0
    root = model_dir.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return "invalid_path", None, 0
    if not candidate.is_file():
        return "unresolved_file", None, 0
    try:
        content = candidate.read_bytes()
        return None, content.decode("utf-8"), len(content)
    except (OSError, UnicodeDecodeError):
        return "invalid_file", None, 0


def attachment_language(relative: str) -> str:
    """Return the payload language name derived from a path extension."""
    suffix = Path(relative).suffix.lower()
    suffix = ".yaml" if suffix == ".yml" else suffix
    return suffix[1:] if suffix in {".json", ".xml", ".csv", ".yaml"} else "text"
