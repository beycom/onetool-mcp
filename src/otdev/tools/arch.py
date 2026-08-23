"""Architecture schema-v3 file workflows."""

from __future__ import annotations

pack = "arch"

__all__ = ["advance", "diff", "init", "resolve", "validate"]

from typing import Any

from otdev.tools._arch.v3.api import (
    advance_file,
    diff_file,
    init_file,
    resolve_file,
    validate_file,
)
from otdev.tools._arch.v3.resolver import StateSelector
from otpack import LogSpan, resolve_cwd_path


def init(*, output_path: str) -> dict[str, Any]:
    """Create a minimal schema-v3 YAML file without overwriting an existing file."""
    with LogSpan(span="arch.init", outputPath=output_path):
        return init_file(resolve_cwd_path(output_path))


def validate(*, input_path: str) -> dict[str, Any]:
    """Validate a schema-v3 architecture YAML file."""
    with LogSpan(span="arch.validate", inputPath=input_path):
        return validate_file(resolve_cwd_path(input_path))


def resolve(
    *, input_path: str, at: str = "current", timeline: str | None = None
) -> dict[str, Any]:
    """Resolve an architecture state.

    Args:
        input_path: Architecture YAML file path.
        at: ``current``, a milestone id, or ``end``.
        timeline: Timeline id when the architecture declares several.
    """
    with LogSpan(span="arch.resolve", inputPath=input_path, at=at, timeline=timeline):
        return resolve_file(
            resolve_cwd_path(input_path), StateSelector(at=at, timeline=timeline)
        )


def diff(
    *,
    input_path: str,
    at_a: str = "current",
    at_b: str = "end",
    timeline_a: str | None = None,
    timeline_b: str | None = None,
) -> dict[str, Any]:
    """Diff two architecture states.

    Args:
        input_path: Architecture YAML file path.
        at_a: Origin state selector.
        at_b: Destination state selector.
        timeline_a: Optional origin timeline id.
        timeline_b: Optional destination timeline id.
    """
    with LogSpan(span="arch.diff", inputPath=input_path):
        return diff_file(
            resolve_cwd_path(input_path),
            StateSelector(at=at_a, timeline=timeline_a),
            StateSelector(at=at_b, timeline=timeline_b),
        )


def advance(*, input_path: str, through: str) -> dict[str, Any]:
    """Rewrite a file after advancing its baseline through a milestone."""
    with LogSpan(span="arch.advance", inputPath=input_path, through=through):
        return advance_file(resolve_cwd_path(input_path), through)
