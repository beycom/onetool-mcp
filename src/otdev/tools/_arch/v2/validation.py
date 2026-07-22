"""Unified production validation across schema-v2 execution boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from .diagram import DiagramCatalogError, extend_with_diagram_catalog
from .likec4 import LikeC4BoundaryError, compile_likec4, generate_prepared_likec4
from .models import SourceLocation
from .normalize import KIND_FIELDS, normalize_change, state_index
from .presentation import PresentationError, resolve_graph_presentation, resolve_theme
from .replay import (
    RoadmapReplayTimeline,
    prepare_roadmap_timeline,
    replay_roadmap,
    validate_roadmap,
)
from .result import Issue, IssueCollection, IssueIdentity
from .viewgraph import normalize_selection, resolve_view_graph

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .models import ArchitectureWorkspace, EntityKind, ViewGraph


def _issue(
    *,
    code: str,
    message: str,
    severity: Literal["error", "warning"] = "error",
    locations: Iterable[SourceLocation | None] = (),
    identity: IssueIdentity | None = None,
    details: dict[str, Any] | None = None,
) -> Issue:
    return Issue(
        code=code,
        severity=severity,
        message=message,
        locations=[location for location in locations if location is not None],
        identity=identity or IssueIdentity(),
        details=details or {},
    )


def _duplicates(
    *,
    kind: str,
    values: list[Any],
    identity_field: str,
) -> list[Issue]:
    by_id: dict[str, list[Any]] = {}
    for value in values:
        by_id.setdefault(value.id, []).append(value)
    return [
        _issue(
            code="arch.duplicate_id",
            message=f"Duplicate {kind} ID '{identifier}'",
            locations=[
                getattr(item, "source", None) or getattr(item, "source_location", None)
                for item in duplicates
            ],
            identity=IssueIdentity.model_validate({identity_field: identifier}),
            details={"kind": kind, "id": identifier, "count": len(duplicates)},
        )
        for identifier, duplicates in sorted(by_id.items())
        if len(duplicates) > 1
    ]


def _identity_issues(workspace: ArchitectureWorkspace) -> list[Issue]:
    issues: list[Issue] = []
    for kind, values, field in (
        ("state", workspace.states, "state"),
        ("change", workspace.changes, "change"),
        ("roadmap", workspace.roadmaps, "roadmap"),
        ("view", workspace.views, "view"),
        ("diagram", workspace.diagrams, "diagram"),
        ("theme", workspace.presentation.themes, "view"),
        ("table", workspace.presentation.tables, "artifact"),
    ):
        issues.extend(_duplicates(kind=kind, values=values, identity_field=field))
    for state in workspace.states:
        all_entities = [
            entity
            for field in KIND_FIELDS.values()
            for entity in getattr(state, field)
        ]
        issues.extend(
            _duplicates(kind=f"entity in state {state.id}", values=all_entities, identity_field="entity")
        )
    for table in workspace.presentation.tables:
        issues.extend(
            _duplicates(
                kind=f"column in table {table.id}",
                values=table.columns,
                identity_field="artifact",
            )
        )
    return issues


def _state_reference_issues(workspace: ArchitectureWorkspace) -> list[Issue]:
    issues: list[Issue] = []
    for state in workspace.states:
        index = state_index(state)
        endpoint_kinds: tuple[EntityKind, ...] = (
            "system",
            "application",
            "component",
            "user",
        )
        endpoints = {
            identifier
            for kind in endpoint_kinds
            for identifier in index[kind]
        }
        for application in state.applications:
            if application.system not in index["system"]:
                issues.append(
                    _issue(
                        code="arch.missing_parent",
                        message=f"Application '{application.id}' references missing system '{application.system}'",
                        locations=[application.source],
                        identity=IssueIdentity(state=state.id, entity=application.id),
                    )
                )
        for component in state.components:
            if component.application not in index["application"]:
                issues.append(
                    _issue(
                        code="arch.missing_parent",
                        message=f"Component '{component.id}' references missing application '{component.application}'",
                        locations=[component.source],
                        identity=IssueIdentity(state=state.id, entity=component.id),
                    )
                )
        for interface in state.interfaces:
            for field in ("provider", "consumer"):
                endpoint = getattr(interface, field)
                if endpoint not in endpoints:
                    issues.append(
                        _issue(
                            code="arch.missing_interface_endpoint",
                            message=f"Interface '{interface.id}' references missing {field} '{endpoint}'",
                            locations=[interface.source],
                            identity=IssueIdentity(state=state.id, interface=interface.id),
                            details={"endpoint_field": field, "endpoint": endpoint},
                        )
                    )
        for relationship in state.relationships:
            for field in ("source_id", "target_id"):
                endpoint = getattr(relationship, field)
                if endpoint not in endpoints:
                    issues.append(
                        _issue(
                            code="arch.missing_relationship_endpoint",
                            message=f"Relationship '{relationship.id}' references missing {field} '{endpoint}'",
                            locations=[relationship.source],
                            identity=IssueIdentity(state=state.id, entity=relationship.id),
                        )
                    )
    return issues


def validate_workspace(
    *,
    workspace: ArchitectureWorkspace,
    workspace_root: Path,
    roadmaps: list[str] | None = None,
    views: list[str] | None = None,
) -> tuple[IssueCollection, dict[str, int]]:
    """Exercise the production normalizer, replay, selector, renderer, and asset paths."""
    errors = [*_identity_issues(workspace), *_state_reference_issues(workspace)]
    warnings: list[Issue] = []
    for theme in workspace.presentation.themes:
        try:
            resolve_theme(workspace=workspace, theme_id=theme.id)
        except PresentationError as exc:
            errors.append(
                _issue(
                    code=exc.code,
                    message=str(exc),
                    locations=[exc.source],
                    details={"theme": theme.id},
                )
            )
    roadmap_by_id = {roadmap.id: roadmap for roadmap in workspace.roadmaps}
    view_by_id = {view.id: view for view in workspace.views}
    requested_roadmaps = roadmaps or sorted(roadmap_by_id)
    requested_views = views or sorted(view_by_id)
    for roadmap_id in requested_roadmaps:
        if roadmap_id not in roadmap_by_id:
            errors.append(
                _issue(
                    code="arch.unknown_roadmap",
                    message=f"Unknown requested roadmap '{roadmap_id}'",
                    identity=IssueIdentity(roadmap=roadmap_id),
                )
            )
    for view_id in requested_views:
        if view_id not in view_by_id:
            errors.append(
                _issue(
                    code="arch.unknown_view",
                    message=f"Unknown requested view '{view_id}'",
                    identity=IssueIdentity(view=view_id),
                )
            )

    operations = 0
    generated_operations = 0
    normalized_change_ids: set[str] = set()
    replay_by_roadmap: dict[str, RoadmapReplayTimeline] = {}
    for roadmap in workspace.roadmaps:
        if roadmap.id not in requested_roadmaps:
            continue
        roadmap_issues = validate_roadmap(workspace=workspace, roadmap=roadmap)
        errors.extend(roadmap_issues.errors)
        normalized_change_ids.update(item.change for item in roadmap.items)
        replay_timeline = prepare_roadmap_timeline(
            workspace=workspace,
            roadmap_id=roadmap.id,
        )
        replay_by_roadmap[roadmap.id] = replay_timeline
        replayed = replay_roadmap(
            workspace=workspace,
            roadmap_id=roadmap.id,
            timeline=replay_timeline,
        )
        errors.extend(replayed.issues.errors)
        warnings.extend(replayed.issues.warnings)
        if replayed.resolved is not None:
            for history in replayed.resolved.history:
                operations += len(history.operations)
                for operation in history.operations:
                    if not operation.generated:
                        continue
                    generated_operations += 1
                    warnings.append(
                        _issue(
                            code="arch.cascade_expansion",
                            severity="warning",
                            message=(
                                f"Removal of '{operation.initiating_ancestor}' generated "
                                f"{operation.entity_kind} removal '{operation.entity_id}'"
                            ),
                            locations=[operation.source],
                            identity=IssueIdentity(
                                roadmap=roadmap.id,
                                order=history.order,
                                change=history.change_id,
                                operation=operation.id,
                                entity=operation.entity_id,
                            ),
                            details={
                                "initiating_ancestor": operation.initiating_ancestor,
                                "cascade_path": operation.cascade_path,
                                "cause": operation.cause,
                            },
                        )
                    )
    if workspace.states:
        fallback = workspace.states[0]
        for change in workspace.changes:
            if change.id in normalized_change_ids:
                continue
            normalized = normalize_change(state=fallback, change=change)
            errors.extend(normalized.issues.errors)
            operations += len(normalized.change.operations)

    graphs: dict[str, ViewGraph] = {}
    selection_values: list[Any] = [view_id for view_id in requested_views if view_id in view_by_id]
    selection_values.extend(
        {"roadmap": roadmap_id, "order": 0}
        for roadmap_id in requested_roadmaps
        if roadmap_id in roadmap_by_id
    )
    selection_values.extend(
        {"roadmap": roadmap_id}
        for roadmap_id in requested_roadmaps
        if roadmap_id in roadmap_by_id
    )
    if not selection_values and workspace.states:
        selection_values.append({"state": workspace.states[0].id})
    for value in selection_values:
        try:
            normalized_selection_value = normalize_selection(
                workspace=workspace,
                value=value,
            )
        except ValueError:
            selection_timeline = None
        else:
            selection_timeline = (
                replay_by_roadmap.get(normalized_selection_value.roadmap)
                if normalized_selection_value.roadmap is not None
                else None
            )
        resolved = resolve_view_graph(
            workspace=workspace,
            value=value,
            replay_timeline=selection_timeline,
        )
        if isinstance(value, str):
            errors.extend(
                issue.model_copy(
                    update={
                        "identity": issue.identity.model_copy(update={"view": value})
                    }
                )
                for issue in resolved.issues.errors
            )
        else:
            errors.extend(resolved.issues.errors)
        warnings.extend(resolved.issues.warnings)
        if resolved.graph is None:
            continue
        try:
            graph = resolve_graph_presentation(
                graph=resolved.graph,
                workspace=workspace,
                workspace_root=workspace_root,
            )
        except PresentationError as exc:
            errors.append(
                _issue(
                    code=exc.code,
                    message=str(exc),
                    locations=[exc.source],
                    identity=IssueIdentity(view=resolved.graph.selection.id),
                )
            )
            continue
        graphs.setdefault(graph.id, graph)
    if graphs:
        prepared = generate_prepared_likec4(list(graphs.values()))
        try:
            source, _catalog, _attachments = extend_with_diagram_catalog(
                generated=prepared,
                graphs=list(graphs.values()),
                workspace=workspace,
                workspace_root=workspace_root,
            )
            compile_likec4(source)
        except DiagramCatalogError as exc:
            locations = (
                [SourceLocation(kind="generated", path=str(exc.path))]
                if exc.path is not None
                else []
            )
            errors.append(
                _issue(
                    code=exc.code,
                    message=str(exc),
                    locations=locations,
                    identity=IssueIdentity(diagram=exc.diagram_id),
                    details={
                        "path": str(exc.path) if exc.path else None,
                        "line": exc.line,
                        "identifier": exc.identifier,
                    },
                )
            )
        except LikeC4BoundaryError as exc:
            errors.append(_issue(code="arch.likec4_compile", message=str(exc)))

    warnings.append(
        _issue(
            code="arch.drawio_fidelity_difference",
            severity="warning",
            message=(
                "Draw.io preserves editable architecture semantics but omits React-only "
                "inspector fields and non-color status glyphs"
            ),
            details={
                "format": "drawio",
                "fields": ["inspector", "status_glyph"],
                "manifest_entry": True,
            },
        )
    )
    counts = {
        "states": len(workspace.states),
        "changes": len(workspace.changes),
        "roadmaps": len([item for item in requested_roadmaps if item in roadmap_by_id]),
        "views": len([item for item in requested_views if item in view_by_id]),
        "diagrams": len(workspace.diagrams),
        "operations": operations,
        "generated_operations": generated_operations,
        "resolved_views": len(graphs),
    }
    return IssueCollection(errors=errors, warnings=warnings), counts


def validation_failure(issues: IssueCollection) -> str:
    """Return a concise stable message for generation/export publication gates."""
    return "; ".join(f"{issue.code}: {issue.message}" for issue in issues.errors)
