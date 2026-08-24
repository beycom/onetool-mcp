"""Generated identifiers for architecture entity rows."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Architecture

PREFIXES = {
    "systems": "s",
    "containers": "c",
    "components": "cp",
    "code": "cd",
    "users": "u",
    "interfaces": "i",
    "relationships": "r",
}


def next_id(kind: str, existing_ids: list[str] | set[str] | tuple[str, ...]) -> str:
    """Return the next generated id for a canonical collection name."""
    try:
        prefix = PREFIXES[kind]
    except KeyError as exc:
        raise ValueError(f"unknown entity kind {kind!r}") from exc
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    highest = max(
        (
            int(match.group(1))
            for value in existing_ids
            if (match := pattern.fullmatch(value))
        ),
        default=0,
    )
    number = highest + 1
    return f"{prefix}-{number:04d}"


def assign_missing_ids(
    architecture: Architecture,
) -> dict[str, list[tuple[int, str]]]:
    """Assign ids to incomplete rows in collection and row order."""
    assigned: dict[str, list[tuple[int, str]]] = {}
    for kind in PREFIXES:
        rows = getattr(architecture, kind)
        existing = {row.id for row in rows if getattr(row, "id", None)}
        for index, row in enumerate(rows):
            if getattr(row, "id", None):
                continue
            generated = next_id(kind, existing)
            row.id = generated
            existing.add(generated)
            assigned.setdefault(kind, []).append((index, generated))
    return assigned
