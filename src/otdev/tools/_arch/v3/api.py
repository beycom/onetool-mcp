"""File-oriented schema-v3 operations shared by the CLI and tool facade."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .ids import assign_missing_ids
from .model import Architecture
from .resolver import StateSelector, advance, diff, resolve
from .validate import validate
from .yamlio import dump_architecture, load_architecture

if TYPE_CHECKING:
    from pathlib import Path


class ArchitectureValidationError(ValueError):
    """Raised when an operation requires structurally valid input."""


def _starter() -> Architecture:
    architecture = Architecture(
        schema_version=3,
        milestones=[],
        systems=[],
        subsystems=[],
        containers=[],
        components=[],
        code=[],
        users=[],
        interfaces=[],
        relationships=[],
    )
    assign_missing_ids(architecture)
    return architecture


def _row_payload(row: object) -> dict[str, Any]:
    return row.model_dump(mode="json", by_alias=True, exclude_none=True)  # type: ignore[attr-defined,no-any-return]


def _load_valid(path: Path) -> Architecture:
    architecture = load_architecture(path)
    errors = [item for item in validate(architecture) if item.severity == "error"]
    if errors:
        codes = ", ".join(dict.fromkeys(item.code for item in errors))
        raise ArchitectureValidationError(
            f"architecture has validation errors: {codes}"
        )
    return architecture


def init_file(path: Path) -> dict[str, Any]:
    """Create a minimal valid architecture without overwriting a file."""
    if path.exists():
        raise FileExistsError(f"architecture already exists: {path}")
    architecture = _starter()
    dump_architecture(architecture, path)
    return {"ok": True, "path": str(path)}


def validate_file(path: Path) -> dict[str, Any]:
    """Load a file and return its structured validation payload."""
    findings = validate(load_architecture(path))
    errors = [asdict(item) for item in findings if item.severity == "error"]
    warnings = [asdict(item) for item in findings if item.severity == "warning"]
    return {
        "ok": not errors,
        "valid": not errors,
        "path": str(path),
        "summary": {"errors": len(errors), "warnings": len(warnings)},
        "issues": {"errors": errors, "warnings": warnings},
    }


def resolve_file(path: Path, selector: StateSelector) -> dict[str, Any]:
    """Load, validate, and resolve one selected state."""
    state = resolve(_load_valid(path), selector)
    return {
        "ok": True,
        "timeline": state.timeline.id,
        "at": selector.at,
        "position": state.position,
        "entities": {
            kind: [_row_payload(row) for row in rows]
            for kind, rows in state.entities.items()
        },
        "clips": [asdict(item) for item in state.clips],
    }


def diff_file(
    path: Path, selector_a: StateSelector, selector_b: StateSelector
) -> dict[str, Any]:
    """Load, validate, and diff two selected states."""
    result = asdict(diff(_load_valid(path), selector_a, selector_b))
    return {"ok": True, **result}


def advance_file(path: Path, through: str) -> dict[str, Any]:
    """Load, validate, advance, and atomically rewrite an architecture."""
    rewritten = advance(_load_valid(path), through)
    dump_architecture(rewritten, path)
    return {"ok": True, "path": str(path), "through": through}
