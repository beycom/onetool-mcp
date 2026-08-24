"""Architecture schema-v3 file workflows."""

from __future__ import annotations

pack = "arch"

__all__ = [
    "advance",
    "convert",
    "diff",
    "export",
    "generate",
    "import_excel",
    "init",
    "resolve",
    "validate",
]

from typing import Any

from otdev.tools._arch.v3.api import (
    advance_file,
    diff_file,
    init_file,
    resolve_file,
    validate_file,
)
from otdev.tools._arch.v3.excel import export_workbook, import_workbook
from otdev.tools._arch.v3.report import generate_report
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
    *, input_path: str, at: str = "base", timeline: str | None = None
) -> dict[str, Any]:
    """Resolve an architecture state.

    Args:
        input_path: Architecture YAML file path.
        at: ``base``, a milestone id, or ``end``.
        timeline: Timeline id when the architecture declares several.
    """
    with LogSpan(span="arch.resolve", inputPath=input_path, at=at, timeline=timeline):
        return resolve_file(
            resolve_cwd_path(input_path), StateSelector(at=at, timeline=timeline)
        )


def diff(
    *,
    input_path: str,
    at_a: str = "base",
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


def import_excel(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Import an Excel workbook into canonical schema-v3 YAML."""
    with LogSpan(
        span="arch.import_excel", inputPath=input_path, outputPath=output_path
    ):
        return import_workbook(
            resolve_cwd_path(input_path), resolve_cwd_path(output_path)
        )


def convert(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Import an Excel workbook into canonical schema-v3 YAML."""
    with LogSpan(span="arch.convert", inputPath=input_path, outputPath=output_path):
        return import_workbook(
            resolve_cwd_path(input_path), resolve_cwd_path(output_path)
        )


def export(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Export canonical schema-v3 YAML to an Excel workbook."""
    with LogSpan(span="arch.export", inputPath=input_path, outputPath=output_path):
        return export_workbook(
            resolve_cwd_path(input_path), resolve_cwd_path(output_path)
        )


def generate(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Generate a self-contained architecture HTML report."""
    with LogSpan(span="arch.generate", inputPath=input_path, outputPath=output_path):
        return generate_report(
            resolve_cwd_path(input_path), resolve_cwd_path(output_path)
        )
