"""Schema-v2 architecture state, roadmap, explorer, and export tools."""

from __future__ import annotations

pack = "arch"

__all__ = ["bundle", "convert", "diff", "export", "generate", "init", "resolve", "validate"]

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from otdev.tools._arch.v2 import api
from otdev.tools._arch.v2.models import Presentation
from otpack import LogSpan, get_tool_config


class Config(BaseModel):
    """Architecture pack configuration discovered by the registry."""

    model_config = ConfigDict(extra="forbid")

    presentation: Presentation = Field(
        default_factory=Presentation,
        description="Explorer defaults, themes, palettes, and table presentation",
    )


def _get_config() -> Config:
    """Return validated tools.arch configuration."""
    return get_tool_config("arch", Config)


def init(*, output_path: str, template: str = "solution") -> dict[str, Any]:
    """Create a canonical paired schema-v2 architecture workspace.

    Args:
        output_path: New workspace directory.
        template: Workspace template. Only ``solution`` is supported.

    Returns:
        Common operation envelope with created artifacts and diagnostics.
    """
    with LogSpan(span="arch.init", outputPath=output_path, template=template):
        return api.init(output_path=output_path, template=template)


def validate(
    *,
    input_path: str,
    roadmaps: list[str] | None = None,
    views: list[str] | None = None,
) -> dict[str, Any]:
    """Validate a schema-v2 architecture workspace through production paths.

    Args:
        input_path: YAML file, Excel workbook, or workspace directory.
        roadmaps: Optional roadmap IDs to validate.
        views: Optional saved view IDs to validate.

    Returns:
        Common operation envelope with validity, summary, and diagnostics.
    """
    with LogSpan(span="arch.validate", inputPath=input_path):
        return api.validate(
            input_path=input_path,
            roadmaps=roadmaps,
            views=views,
            presentation=_get_config().presentation,
        )


def convert(*, input_path: str, output_path: str) -> dict[str, Any]:
    """Convert a schema-v2 YAML or Excel workspace/state.

    Args:
        input_path: Source YAML file or Excel workbook.
        output_path: Destination inferred from its YAML or Excel extension.

    Returns:
        Common operation envelope with conversion artifact and diagnostics.
    """
    with LogSpan(span="arch.convert", inputPath=input_path, outputPath=output_path):
        return api.convert(
            input_path=input_path,
            output_path=output_path,
            presentation=_get_config().presentation,
        )


def resolve(
    *,
    input_path: str,
    output_path: str,
    state: str | None = None,
    roadmap: str | None = None,
    through: str | None = None,
    order: int | None = None,
    output_state_id: str | None = None,
) -> dict[str, Any]:
    """Resolve and materialize one complete architecture state.

    Args:
        input_path: Source workspace.
        output_path: Complete YAML or Excel state destination.
        state: Optional authored complete-state ID.
        roadmap: Optional roadmap ID.
        through: Optional change ID or ``base`` endpoint.
        order: Optional numeric roadmap order, including base order 0.
        output_state_id: Optional explicit materialized state ID.

    Returns:
        Common operation envelope with resolved selection and artifact.
    """
    with LogSpan(span="arch.resolve", inputPath=input_path, outputPath=output_path):
        return api.resolve(
            input_path=input_path,
            output_path=output_path,
            state=state,
            roadmap=roadmap,
            through=through,
            order=order,
            output_state_id=output_state_id,
            presentation=_get_config().presentation,
        )


def diff(
    *,
    base_path: str,
    target_path: str,
    output_path: str | None = None,
    change_id: str | None = None,
) -> dict[str, Any]:
    """Compare complete states and optionally materialize a derived change.

    Args:
        base_path: Base complete state or workspace selection.
        target_path: Target complete state or workspace selection.
        output_path: Optional derived change destination.
        change_id: Required stable ID when materializing a derived change.

    Returns:
        Common operation envelope with net differences and contributing history.
    """
    with LogSpan(span="arch.diff", basePath=base_path, targetPath=target_path):
        return api.diff(
            base_path=base_path,
            target_path=target_path,
            output_path=output_path,
            change_id=change_id,
            presentation=_get_config().presentation,
        )


def generate(
    *,
    input_path: str,
    output_path: str,
    selections: list[str | dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Generate the self-contained offline OneTool architecture explorer.

    Args:
        input_path: Source schema-v2 workspace.
        output_path: Explorer output file or directory.
        selections: Optional saved-view IDs or typed ad hoc selections.
        force: Replace a user-owned destination when true.

    Returns:
        Common operation envelope with generated explorer artifacts.
    """
    with LogSpan(span="arch.generate", inputPath=input_path, outputPath=output_path):
        return api.generate(
            input_path=input_path,
            output_path=output_path,
            selections=selections,
            force=force,
            presentation=_get_config().presentation,
        )


def export(
    *,
    input_path: str,
    output_path: str,
    formats: list[str],
    selections: list[str | dict[str, Any]] | None = None,
    drawio_mode: str = "per-view",
    continue_on_error: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Export normalized architecture selections in production formats.

    Args:
        input_path: Source schema-v2 workspace.
        output_path: Owned export destination.
        formats: Requested output formats.
        selections: Optional saved-view IDs or typed ad hoc selections.
        drawio_mode: ``per-view`` or ``multi-tab`` Draw.io output.
        continue_on_error: Continue independent artifacts after a failure.
        force: Replace a user-owned destination when true.

    Returns:
        Common operation envelope with per-artifact outcomes and fidelity issues.
    """
    with LogSpan(span="arch.export", inputPath=input_path, outputPath=output_path):
        return api.export(
            input_path=input_path,
            output_path=output_path,
            formats=formats,
            selections=selections,
            drawio_mode=drawio_mode,
            continue_on_error=continue_on_error,
            force=force,
            presentation=_get_config().presentation,
        )


def bundle(
    *, input_path: str, output_path: str, include_generated: bool = False
) -> dict[str, Any]:
    """Create a deterministic portable schema-v2 workspace bundle.

    Args:
        input_path: Source workspace.
        output_path: Destination archive.
        include_generated: Include only manifest-owned generated outputs.

    Returns:
        Common operation envelope with deterministic bundle artifact.
    """
    with LogSpan(span="arch.bundle", inputPath=input_path, outputPath=output_path):
        return api.bundle(
            input_path=input_path,
            output_path=output_path,
            include_generated=include_generated,
        )
