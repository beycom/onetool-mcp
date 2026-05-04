"""Shared models and constants for arch pack internals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODEL_VERSION = "1.0"
CORE_SHEETS: tuple[str, ...] = ("sys", "app", "cmp", "int", "usr")
DIAGRAM_SHEETS: tuple[str, ...] = ("diagram",)
SHEETS: tuple[str, ...] = CORE_SHEETS + DIAGRAM_SHEETS


@dataclass(slots=True)
class Issue:
    """Structured validation issue."""

    code: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return issue as serializable mapping."""
        return {"code": self.code, "message": self.message, "details": self.details}


def normalize_key(value: Any) -> str:
    """Normalize worksheet header names into stable keys."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    normalized = "".join(out)
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def normalize_cell(value: Any) -> Any:
    """Normalize cell values while preserving multiline text."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped
    return value


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return first non-empty value from a set of keys."""
    for key in keys:
        if key in row:
            value = row[key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def tags_for_row(row: dict[str, Any]) -> set[str]:
    """Extract lowercase tag set from a row."""
    value = first_value(row, ("tags", "tag", "labels"))
    if value is None:
        return set()
    if isinstance(value, str):
        normalized = value.replace(";", ",").replace("\n", ",")
        raw_items = normalized.split(",")
    elif isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [str(value)]
    return {item.strip().lower() for item in raw_items if item and item.strip()}


__all__ = [
    "CORE_SHEETS",
    "DIAGRAM_SHEETS",
    "MODEL_VERSION",
    "SHEETS",
    "Issue",
    "first_value",
    "normalize_cell",
    "normalize_key",
    "tags_for_row",
]
