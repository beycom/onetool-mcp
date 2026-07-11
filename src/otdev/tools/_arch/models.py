"""Shared models and constants for arch pack internals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODEL_VERSION = "1.0"

DEFAULT_LIST_CELL_SEPARATOR = ";"
PASSTHROUGH_KEY = "_passthrough"

SHEET_SYS = "sys"
SHEET_APP = "app"
SHEET_CMP = "cmp"
SHEET_INTERFACE = "interface"
SHEET_USR = "usr"
SHEET_PROJECT = "project"
SHEET_PROJECT_SCOPE = "project_scope"
SHEET_DIAGRAM = "diagram"

CORE_SHEETS: tuple[str, ...] = (
    SHEET_SYS,
    SHEET_APP,
    SHEET_CMP,
    SHEET_INTERFACE,
    SHEET_USR,
    SHEET_PROJECT,
    SHEET_PROJECT_SCOPE,
)
DIAGRAM_SHEETS: tuple[str, ...] = (SHEET_DIAGRAM,)
SHEETS: tuple[str, ...] = CORE_SHEETS + DIAGRAM_SHEETS

SHEET_ALIASES: dict[str, tuple[str, ...]] = {
    SHEET_SYS: ("sys", "system"),
    SHEET_APP: ("app", "application"),
    SHEET_CMP: ("cmp", "component", "components"),
    SHEET_INTERFACE: ("interface", "int"),
    SHEET_USR: ("usr", "user", "users"),
    SHEET_PROJECT: ("project",),
    SHEET_PROJECT_SCOPE: ("project_scope", "project_scopes"),
    SHEET_DIAGRAM: ("diagram", "diagrams"),
}
SHEET_CANONICAL_BY_ALIAS: dict[str, str] = {
    alias: canonical
    for canonical, aliases in SHEET_ALIASES.items()
    for alias in aliases
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "sys": ("sys", "system", "system_id", "sys_id"),
    "app": ("app", "application", "app_id", "application_id"),
    "cmp": ("cmp", "component", "components", "component_id", "cmp_id"),
    "interface": ("interface", "int", "interface_id", "int_id"),
}
FIELD_CANONICAL_BY_ALIAS: dict[str, str] = {
    alias: canonical
    for canonical, aliases in FIELD_ALIASES.items()
    for alias in aliases
}

SYS_REF_KEYS: tuple[str, ...] = FIELD_ALIASES["sys"]
APP_REF_KEYS: tuple[str, ...] = FIELD_ALIASES["app"]

DEFAULT_ARROW_DIRECTION = "consumer_to_provider"
ARROW_DIRECTIONS = {"consumer_to_provider", "provider_to_consumer", "none", "bidirectional"}

# Accepted project-scope `item_type` spellings -> canonical entity kind.
PROJECT_SCOPE_ITEM_TYPES: dict[str, str] = {
    "sys": "sys",
    "system": "sys",
    "app": "app",
    "application": "app",
    "cmp": "cmp",
    "component": "cmp",
    "components": "cmp",
    "int": "interface",
    "interface": "interface",
}

STD_SYS_KEYS = {"id", "name", "type", "system_type", "tag", "tags", "description"}
STD_APP_KEYS = {"id", "name", *SYS_REF_KEYS, "tag", "tags", "description"}
STD_INTERFACE_KEYS = {
    "id",
    "key",
    "name",
    "provider",
    "consumer",
    "interaction_type",
    "arrow_direction",
    "tag",
    "tags",
    "description",
}
STD_PROJECT_KEYS = {
    "id",
    "name",
    "status",
    "owner",
    "sponsor",
    "start_date",
    "target_date",
    "detail_level",
    "connect_level",
    "tag",
    "tags",
    "description",
}
STD_PROJECT_SCOPE_KEYS = {
    "project",
    "project_id",
    "stage",
    "item_type",
    "item_id",
    "change_type",
    "name",
    "description",
    "owner",
    "status",
    "tag",
    "tags",
}


class MissingDependencyError(RuntimeError):
    """Raised when an optional dependency required by the arch pack is absent."""


def ensure_openpyxl() -> Any:
    """Import and return openpyxl, raising MissingDependencyError when absent."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - import guard
        raise MissingDependencyError(
            "openpyxl is required for arch pack. Install with: pip install onetool-mcp[dev]"
        ) from exc
    return openpyxl


def resolve_sheet_name(
    *,
    workbook: Any,
    canonical_sheet: str,
    workbook_path: Any,
    error_cls: type[Exception],
    label: str = "Workbook",
) -> str | None:
    """Return the unique worksheet name matching a canonical sheet key, if any."""
    matches = [
        sheet_name
        for sheet_name in workbook.sheetnames
        if canonical_sheet_name(sheet_name) == canonical_sheet
    ]
    if len(matches) > 1:
        raise error_cls(
            f"{label} '{workbook_path}' has multiple sheets for '{canonical_sheet}': {matches}"
        )
    return matches[0] if matches else None


@dataclass(slots=True)
class Issue:
    """Structured validation issue."""

    code: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return issue as serializable mapping."""
        return {"code": self.code, "message": self.message, "details": self.details}


def error_payload(
    *, operation: str, code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Structured error payload shared by the arch facade and generation pipeline."""
    return {
        "ok": False,
        "operation": operation,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


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


def canonical_sheet_name(value: Any) -> str | None:
    """Return the canonical sheet key for a sheet/section name."""
    normalized = normalize_key(value)
    if not normalized:
        return None
    return SHEET_CANONICAL_BY_ALIAS.get(normalized)


def normalize_cell(value: Any) -> Any:
    """Normalize cell values while preserving multiline text."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped
    return value


def parse_cell_list(value: Any, *, separator: str) -> Any:
    """Parse a bracketed Excel-cell list (e.g. ``[core;internal]``) into a list.

    A trimmed string wrapped in ``[ ... ]`` is split on ``separator`` with each item
    trimmed; ``[]`` yields an empty list. Any other value (including unbracketed
    strings) is returned unchanged, so plain scalar cells stay scalars.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if len(stripped) < 2 or stripped[0] != "[" or stripped[-1] != "]":
        return value
    inner = stripped[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(separator)]


def format_cell_list(value: Any, *, separator: str) -> Any:
    """Serialize a list value into bracketed Excel-cell text (e.g. ``[core;internal]``).

    Non-list values are returned unchanged.
    """
    if isinstance(value, list):
        return "[" + separator.join(str(item) for item in value) + "]"
    return value


def option_as_bool(value: Any, *, default: bool) -> bool:
    """Coerce profile-data option values into booleans."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


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
    "APP_REF_KEYS",
    "ARROW_DIRECTIONS",
    "CORE_SHEETS",
    "DEFAULT_ARROW_DIRECTION",
    "DEFAULT_LIST_CELL_SEPARATOR",
    "DIAGRAM_SHEETS",
    "FIELD_ALIASES",
    "FIELD_CANONICAL_BY_ALIAS",
    "MODEL_VERSION",
    "PASSTHROUGH_KEY",
    "PROJECT_SCOPE_ITEM_TYPES",
    "SHEETS",
    "SHEET_ALIASES",
    "SHEET_APP",
    "SHEET_CANONICAL_BY_ALIAS",
    "SHEET_CMP",
    "SHEET_DIAGRAM",
    "SHEET_INTERFACE",
    "SHEET_PROJECT",
    "SHEET_PROJECT_SCOPE",
    "SHEET_SYS",
    "SHEET_USR",
    "STD_APP_KEYS",
    "STD_INTERFACE_KEYS",
    "STD_PROJECT_KEYS",
    "STD_PROJECT_SCOPE_KEYS",
    "STD_SYS_KEYS",
    "SYS_REF_KEYS",
    "Issue",
    "MissingDependencyError",
    "canonical_sheet_name",
    "ensure_openpyxl",
    "error_payload",
    "first_value",
    "format_cell_list",
    "normalize_cell",
    "normalize_key",
    "option_as_bool",
    "parse_cell_list",
    "resolve_sheet_name",
    "tags_for_row",
]
