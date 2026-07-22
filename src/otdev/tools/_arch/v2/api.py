"""Dependency-ordered schema-v2 public operation implementations."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from otpack import resolve_cwd_path

from .compare import compare_states, materialize_change
from .exporter import EXPORT_EXCEPTIONS, export_architecture, export_error_result
from .frontend import ExplorerBuildError, generate_explorer, resolve_workspace_source
from .load import WorkspaceLoadError, load_workspace
from .portable import (
    PortableWorkspaceError,
    bundle_workspace,
    convert_workspace,
    initialize_workspace,
)
from .replay import replay_roadmap
from .result import (
    ArtifactOutcome,
    Issue,
    IssueCollection,
    OperationName,
    OperationResult,
    ResultSummary,
    result_payload,
)
from .selection import selection_identity
from .validation import validate_workspace
from .viewgraph import normalize_selection
from .write import WorkspaceWriteError, write_complete_state, write_derived_change

if TYPE_CHECKING:
    from pathlib import Path

    from .models import CompleteState, Presentation


def _issue(*, code: str, message: str) -> Issue:
    return Issue(code=code, severity="error", message=message)


def _error_result(
    *,
    operation: OperationName,
    issues: list[Issue],
    requested: int = 0,
    artifacts: list[ArtifactOutcome] | None = None,
) -> dict[str, Any]:
    outcomes = artifacts or []
    return result_payload(
        OperationResult(
            ok=False,
            operation=operation,
            issues=IssueCollection(errors=issues),
            summary=ResultSummary(
                errors=len(issues),
                requested=requested,
                failed=sum(item.status == "failed" for item in outcomes),
            ),
            artifacts=outcomes,
        )
    )


def _path(value: str) -> Path:
    return resolve_cwd_path(value).resolve()


def _load_single_state(path: Path, *, presentation: Presentation | None = None) -> CompleteState:
    loaded = load_workspace(path, presentation=presentation)
    if len(loaded.workspace.states) != 1:
        raise WorkspaceLoadError(
            f"State comparison input '{path}' must contain exactly one complete state"
        )
    return loaded.workspace.states[0]


def init(*, output_path: str, template: str) -> dict[str, Any]:
    """Create a schema-v2 workspace."""
    if template != "solution":
        return _error_result(
            operation="init",
            issues=[
                _issue(
                    code="arch.unknown_template",
                    message=f"Unknown architecture workspace template '{template}'",
                )
            ],
        )
    destination = _path(output_path)
    try:
        created = initialize_workspace(output=destination)
    except (OSError, PortableWorkspaceError, ValueError) as exc:
        return _error_result(
            operation="init",
            issues=[_issue(code="arch.init_failed", message=str(exc))],
        )
    artifacts = [
        ArtifactOutcome(
            id=f"workspace-{path.relative_to(destination).as_posix().replace('/', '-')}",
            path=str(path),
            status="generated",
            format=path.suffix.removeprefix("."),
            content_hash=content_hash,
        )
        for path, content_hash in created
    ]
    return result_payload(
        OperationResult(
            ok=True,
            operation="init",
            summary=ResultSummary(
                requested=len(artifacts),
                generated=len(artifacts),
            ),
            artifacts=artifacts,
            data={"workspace": str(destination), "template": template},
        )
    )


def validate(
    *,
    input_path: str,
    roadmaps: list[str] | None,
    views: list[str] | None,
    presentation: Presentation | None = None,
) -> dict[str, Any]:
    """Validate a schema-v2 workspace through the production pipeline."""
    try:
        source, workspace_root = resolve_workspace_source(_path(input_path))
        workspace = load_workspace(source, presentation=presentation).workspace
        issues, counts = validate_workspace(
            workspace=workspace,
            workspace_root=workspace_root,
            roadmaps=roadmaps,
            views=views,
        )
    except (OSError, WorkspaceLoadError, ValueError) as exc:
        return _error_result(
            operation="validate",
            issues=[_issue(code="arch.validation_failed", message=str(exc))],
        )
    return result_payload(
        OperationResult(
            ok=not issues.errors,
            valid=not issues.errors,
            operation="validate",
            issues=issues,
            summary=ResultSummary(
                errors=len(issues.errors),
                warnings=len(issues.warnings),
                requested=counts["roadmaps"] + counts["views"],
            ),
            data={"counts": counts},
        )
    )


def convert(
    *, input_path: str, output_path: str, presentation: Presentation | None = None
) -> dict[str, Any]:
    """Convert a YAML or Excel workspace/state after semantic normalization."""
    source = _path(input_path)
    destination = _path(output_path)
    artifact_id = "converted-workspace"
    try:
        content_hash = convert_workspace(
            source=source,
            destination=destination,
            presentation=presentation,
        )
    except (OSError, PortableWorkspaceError, ValueError) as exc:
        artifact = ArtifactOutcome(
            id=artifact_id,
            path=str(destination),
            status="failed",
            format=destination.suffix.removeprefix("."),
        )
        return _error_result(
            operation="convert",
            requested=1,
            artifacts=[artifact],
            issues=[_issue(code="arch.convert_failed", message=str(exc))],
        )
    artifact = ArtifactOutcome(
        id=artifact_id,
        path=str(destination),
        status="generated",
        format=destination.suffix.removeprefix("."),
        content_hash=content_hash,
    )
    return result_payload(
        OperationResult(
            ok=True,
            operation="convert",
            summary=ResultSummary(requested=1, generated=1),
            artifacts=[artifact],
            data={"source_format": source.suffix.removeprefix(".")},
        )
    )


def resolve(
    *,
    input_path: str,
    output_path: str,
    state: str | None,
    roadmap: str | None,
    through: str | None,
    order: int | None,
    output_state_id: str | None,
    presentation: Presentation | None = None,
) -> dict[str, Any]:
    """Resolve and materialize exactly one complete state."""
    if state is not None and roadmap is not None:
        return _error_result(
            operation="resolve",
            requested=1,
            issues=[
                _issue(
                    code="arch.selection_conflict",
                    message="state and roadmap are mutually exclusive",
                )
            ],
        )
    if through is not None and order is not None:
        return _error_result(
            operation="resolve",
            requested=1,
            issues=[
                _issue(
                    code="arch.selection_conflict",
                    message="through and order are mutually exclusive",
                )
            ],
        )
    if state is not None and (through is not None or order is not None):
        return _error_result(
            operation="resolve",
            requested=1,
            issues=[
                _issue(
                    code="arch.selection_conflict",
                    message="through and order require roadmap resolution",
                )
            ],
        )

    source_path = _path(input_path)
    destination = _path(output_path)
    try:
        workspace = load_workspace(source_path, presentation=presentation).workspace
    except (OSError, WorkspaceLoadError, ValueError) as exc:
        return _error_result(
            operation="resolve",
            requested=1,
            issues=[_issue(code="arch.load_failed", message=str(exc))],
        )

    try:
        selection = normalize_selection(
            workspace=workspace,
            value={
                key: value
                for key, value in {
                    "state": state,
                    "roadmap": roadmap,
                    "through": through,
                    "order": order,
                }.items()
                if value is not None
            },
        )
    except ValueError as exc:
        return _error_result(
            operation="resolve",
            requested=1,
            issues=[_issue(code="arch.invalid_selection", message=str(exc))],
        )
    chosen_roadmap = selection.roadmap
    chosen_state = selection.state
    resolved_history: list[dict[str, Any]] = []
    warnings: list[Issue] = []
    if chosen_state is not None:
        matches = [item for item in workspace.states if item.id == chosen_state]
        if not matches:
            return _error_result(
                operation="resolve",
                requested=1,
                issues=[
                    _issue(
                        code="arch.unknown_state",
                        message=f"Unknown complete state '{chosen_state}'",
                    )
                ],
            )
        complete_state = matches[0]
        selected_order = None
        selected_through = None
    else:
        assert chosen_roadmap is not None
        replayed = replay_roadmap(
            workspace=workspace,
            roadmap_id=chosen_roadmap,
            through=selection.through,
            order=selection.order,
        )
        if replayed.issues.errors:
            return _error_result(
                operation="resolve",
                requested=1,
                issues=replayed.issues.errors,
            )
        assert replayed.resolved is not None
        complete_state = replayed.resolved.state
        selected_order = replayed.resolved.order
        selected_through = replayed.resolved.through
        resolved_history = [
            item.model_dump(mode="json", exclude_none=True)
            for item in replayed.resolved.history
        ]
        warnings = replayed.issues.warnings

    materialized_id = output_state_id or selection_identity(selection)
    complete_state = complete_state.model_copy(update={"id": materialized_id})
    artifact_id = f"resolved-state-{materialized_id}"
    try:
        content_hash = write_complete_state(path=destination, state=complete_state)
    except (OSError, ValueError, WorkspaceWriteError) as exc:
        artifact = ArtifactOutcome(
            id=artifact_id,
            path=str(destination),
            status="failed",
            format=destination.suffix.removeprefix("."),
        )
        return _error_result(
            operation="resolve",
            requested=1,
            artifacts=[artifact],
            issues=[_issue(code="arch.write_failed", message=str(exc))],
        )

    artifact = ArtifactOutcome(
        id=artifact_id,
        path=str(destination),
        status="generated",
        format=destination.suffix.removeprefix("."),
        content_hash=content_hash,
        selection_id=selection_identity(selection),
    )
    return result_payload(
        OperationResult(
            ok=True,
            operation="resolve",
            issues=IssueCollection(warnings=warnings),
            summary=ResultSummary(
                warnings=len(warnings),
                requested=1,
                generated=1,
            ),
            selections=[selection_identity(selection)],
            artifacts=[artifact],
            data={
                "state": complete_state.model_dump(mode="json", exclude_none=True),
                "roadmap": chosen_roadmap,
                "through": selected_through,
                "order": selected_order,
                "history": resolved_history,
            },
        )
    )


def diff(
    *,
    base_path: str,
    target_path: str,
    output_path: str | None,
    change_id: str | None,
    presentation: Presentation | None = None,
) -> dict[str, Any]:
    """Compare complete states and optionally materialize a derived change."""
    if output_path is not None and change_id is None:
        return _error_result(
            operation="diff",
            requested=1,
            issues=[
                _issue(
                    code="arch.change_id_required",
                    message="change_id is required when materializing a derived change",
                )
            ],
        )

    try:
        base = _load_single_state(_path(base_path), presentation=presentation)
        target = _load_single_state(_path(target_path), presentation=presentation)
    except (OSError, WorkspaceLoadError, ValueError) as exc:
        return _error_result(
            operation="diff",
            requested=int(output_path is not None),
            issues=[_issue(code="arch.load_failed", message=str(exc))],
        )
    comparison = compare_states(base=base, target=target, change_id=change_id)
    artifacts: list[ArtifactOutcome] = []
    if output_path is not None:
        assert change_id is not None
        destination = _path(output_path)
        artifact_id = f"derived-change-{change_id}"
        try:
            content_hash = write_derived_change(
                path=destination,
                change=materialize_change(comparison=comparison, change_id=change_id),
            )
        except (OSError, ValueError, WorkspaceWriteError) as exc:
            artifact = ArtifactOutcome(
                id=artifact_id,
                path=str(destination),
                status="failed",
                format=destination.suffix.removeprefix("."),
            )
            return _error_result(
                operation="diff",
                requested=1,
                artifacts=[artifact],
                issues=[_issue(code="arch.write_failed", message=str(exc))],
            )
        artifacts.append(
            ArtifactOutcome(
                id=artifact_id,
                path=str(destination),
                status="generated",
                format=destination.suffix.removeprefix("."),
                content_hash=content_hash,
            )
        )
    return result_payload(
        OperationResult(
            ok=True,
            operation="diff",
            summary=ResultSummary(
                requested=int(output_path is not None),
                generated=len(artifacts),
            ),
            artifacts=artifacts,
            data={
                "comparison": comparison.model_dump(mode="json", exclude_none=True),
            },
        )
    )


def generate(
    *,
    input_path: str,
    output_path: str,
    selections: list[str | dict[str, Any]] | None,
    force: bool,
    presentation: Presentation | None = None,
) -> dict[str, Any]:
    """Generate the self-contained offline architecture explorer."""
    try:
        content_hash, status, report, manifest, data = generate_explorer(
            input_path=_path(input_path),
            output_path=_path(output_path),
            selections=None if selections is None else list(selections),
            force=force,
            presentation=presentation,
        )
    except (OSError, ExplorerBuildError, ValueError) as exc:
        return _error_result(
            operation="generate",
            requested=1,
            issues=[_issue(code="arch.generate_failed", message=str(exc))],
        )
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    artifacts = [
        ArtifactOutcome(
            id="architecture-explorer",
            path=str(report),
            status=status,
            format="html",
            content_hash=content_hash,
        ),
        ArtifactOutcome(
            id="architecture-explorer-manifest",
            path=str(manifest),
            status="generated",
            format="json",
            content_hash=manifest_hash,
        ),
    ]
    return result_payload(
        OperationResult(
            ok=True,
            operation="generate",
            summary=ResultSummary(
                requested=2,
                generated=sum(item.status == "generated" for item in artifacts),
                reused=sum(item.status == "reused" for item in artifacts),
            ),
            selections=[graph["selection"]["id"] for graph in data["graphs"]],
            artifacts=artifacts,
            data={
                "prepared_graphs": len(data["graphs"]),
                "unavailable_orders": data["unavailableOrders"],
            },
        )
    )


def export(
    *,
    input_path: str,
    output_path: str,
    formats: list[str],
    selections: list[str | dict[str, Any]] | None,
    drawio_mode: str,
    continue_on_error: bool,
    force: bool,
    presentation: Presentation | None = None,
) -> dict[str, Any]:
    """Export normalized selections in one or more production formats."""
    try:
        result = export_architecture(
            input_path=_path(input_path),
            output_path=_path(output_path),
            formats=formats,
            selections=None if selections is None else list(selections),
            drawio_mode=drawio_mode,
            continue_on_error=continue_on_error,
            force=force,
            presentation=presentation,
        )
    except EXPORT_EXCEPTIONS as exc:
        result = export_error_result(exc)
    return result_payload(result)


def bundle(*, input_path: str, output_path: str, include_generated: bool) -> dict[str, Any]:
    """Create a deterministic portable workspace bundle."""
    source = _path(input_path)
    destination = _path(output_path)
    artifact_id = "workspace-bundle"
    try:
        content_hash, archived = bundle_workspace(
            input_path=source,
            output_path=destination,
            include_generated=include_generated,
        )
    except (OSError, PortableWorkspaceError, ValueError) as exc:
        artifact = ArtifactOutcome(
            id=artifact_id,
            path=str(destination),
            status="failed",
            format="zip",
        )
        return _error_result(
            operation="bundle",
            requested=1,
            artifacts=[artifact],
            issues=[_issue(code="arch.bundle_failed", message=str(exc))],
        )
    artifact = ArtifactOutcome(
        id=artifact_id,
        path=str(destination),
        status="generated",
        format="zip",
        content_hash=content_hash,
    )
    return result_payload(
        OperationResult(
            ok=True,
            operation="bundle",
            summary=ResultSummary(requested=1, generated=1),
            artifacts=[artifact],
            data={"archived_files": archived, "include_generated": include_generated},
        )
    )
