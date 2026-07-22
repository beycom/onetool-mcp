"""Manifest-owned deterministic production exports for normalized selections."""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal

from .cache import LIKEC4_EXPORT_CACHE
from .diagram import DiagramCatalogError, extend_with_diagram_catalog
from .drawio_export import drawio_document
from .frontend import resolve_workspace_source
from .likec4 import (
    LikeC4BoundaryError,
    generate_prepared_likec4,
    selection_page_name,
)
from .load import WorkspaceLoadError, load_workspace
from .presentation import PresentationError, resolve_graph_presentation
from .projection import prepare_solution_snapshots, project_solution
from .replay import RoadmapReplayTimeline, prepare_roadmap_timeline
from .result import (
    ArtifactOutcome,
    Issue,
    IssueCollection,
    OperationResult,
    ResultSummary,
)
from .validation import validate_workspace, validation_failure
from .viewgraph import normalize_selection, resolve_view_graph
from .write import WorkspaceWriteError, write_complete_state

if TYPE_CHECKING:
    from .models import (
        PreparedSolutionSnapshots,
        Presentation,
        SelectionInput,
        SolutionLayoutResult,
        ViewGraph,
    )

_OWNER = "onetool-arch-v2-export"
_EXPORTER_VERSION = 1
_SUPPORTED_FORMATS = frozenset({"svg", "drawio", "likec4", "yaml", "excel"})
_STATUS_COLORS = {
    "out_of_scope": ("#f3f4f6", "#6b7280"),
    "future": ("#eef2ff", "#6366f1"),
    "new": ("#ecfdf5", "#059669"),
    "change": ("#fff7ed", "#ea580c"),
    "no_change": ("#f8fafc", "#64748b"),
    "decommission": ("#fef2f2", "#dc2626"),
}


class ExportError(ValueError):
    """Raised when an export cannot be safely prepared or published."""


def _frontend_root() -> Path:
    return Path(__file__).parents[1] / "frontend"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "selection"


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent, delete=False, prefix=f".{path.name}."
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    temporary.replace(path)


def _issue(*, code: str, message: str, artifact: str | None = None) -> Issue:
    from .result import IssueIdentity

    return Issue(
        code=code,
        severity="error",
        message=message,
        identity=IssueIdentity(artifact=artifact),
    )


def _prepare_graphs(
    *,
    input_path: Path,
    selections: list[SelectionInput] | None,
    presentation: Presentation | None = None,
) -> tuple[Any, Path, list[ViewGraph], list[dict[str, Any]]]:
    source, workspace_root = resolve_workspace_source(input_path)
    workspace = load_workspace(source, presentation=presentation).workspace
    validation_issues, _counts = validate_workspace(
        workspace=workspace,
        workspace_root=workspace_root,
    )
    if validation_issues.errors:
        raise ExportError(validation_failure(validation_issues))
    requests: list[SelectionInput | None] = (
        list(selections) if selections is not None else [None]
    )
    graphs: dict[str, ViewGraph] = {}
    prepared_by_roadmap: dict[str, PreparedSolutionSnapshots] = {}
    replay_by_roadmap: dict[str, RoadmapReplayTimeline] = {}
    request_map: list[dict[str, Any]] = []
    for index, value in enumerate(requests):
        try:
            normalized = normalize_selection(workspace=workspace, value=value)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        replay_timeline = None
        if normalized.roadmap is not None:
            replay_timeline = replay_by_roadmap.get(normalized.roadmap)
            if replay_timeline is None:
                replay_timeline = prepare_roadmap_timeline(
                    workspace=workspace,
                    roadmap_id=normalized.roadmap,
                )
                replay_by_roadmap[normalized.roadmap] = replay_timeline
        resolved = resolve_view_graph(
            workspace=workspace,
            value=value,
            replay_timeline=replay_timeline,
        )
        if resolved.issues.errors or resolved.graph is None:
            messages = "; ".join(issue.message for issue in resolved.issues.errors)
            raise ExportError(messages or f"Selection request {index} did not resolve")
        graph = resolved.graph
        if graph.selection.roadmap_id is not None:
            assert graph.selection.order is not None
            roadmap_id = graph.selection.roadmap_id
            prepared = prepared_by_roadmap.get(roadmap_id)
            if prepared is None:
                prepared = prepare_solution_snapshots(
                    workspace=workspace,
                    roadmap_id=roadmap_id,
                    replay_timeline=replay_timeline,
                )
                prepared_by_roadmap[roadmap_id] = prepared
            graph = project_solution(
                prepared=prepared,
                order=graph.selection.order,
                selector=graph.selection.selection.system_set,
                interface_depth=graph.selection.selection.interface_depth,
                level=graph.selection.selection.level,
                selection=graph.selection.selection,
            ).graph
        graph = resolve_graph_presentation(
            graph=graph,
            workspace=workspace,
            workspace_root=workspace_root,
        )
        graphs.setdefault(graph.selection.id, graph)
        request_map.append({"request": index, "selection_id": graph.selection.id})
    return workspace, workspace_root, list(graphs.values()), request_map


def _layout_batch(*, source: str, view_ids: list[str]) -> dict[str, Any]:
    request = json.dumps(
        {"source": source, "viewIds": view_ids},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    cache_key = LIKEC4_EXPORT_CACHE.key(b"likec4-export-1.58.0-v1", request)
    cached = LIKEC4_EXPORT_CACHE.get(cache_key)
    if cached is not None:
        cached_payload = json.loads(cached)
        if isinstance(cached_payload, dict):
            return cached_payload
        raise LikeC4BoundaryError("Cached LikeC4 exporter result is invalid")
    result = subprocess.run(
        ["node", "scripts/export-likec4.mjs"],
        cwd=_frontend_root(),
        input=request.decode(),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise LikeC4BoundaryError(result.stderr.strip() or result.stdout.strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LikeC4BoundaryError(
            "Pinned LikeC4 exporter returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise LikeC4BoundaryError("Pinned LikeC4 exporter returned an invalid payload")
    LIKEC4_EXPORT_CACHE.put(
        cache_key,
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
    )
    return payload


def _neutral_layout(
    *,
    graph: ViewGraph,
    layout: dict[str, Any],
    canonical_mapping: dict[str, str],
) -> SolutionLayoutResult:
    from .models import (
        LayoutBounds,
        LayoutPoint,
        SolutionLayoutEdge,
        SolutionLayoutNode,
        SolutionLayoutResult,
    )

    inverse = {
        renderer_id: canonical for canonical, renderer_id in canonical_mapping.items()
    }
    graph_edges = {edge.id: edge for edge in graph.edges}
    nodes = [
        SolutionLayoutNode(
            id=inverse[item["id"]],
            parent=inverse.get(item.get("parent")),
            bounds=LayoutBounds(
                x=float(item["x"]),
                y=float(item["y"]),
                width=float(item["width"]),
                height=float(item["height"]),
            ),
        )
        for item in layout["nodes"]
        if item["id"] in inverse
    ]
    edges = []
    for item in layout["edges"]:
        canonical_ids = [
            value
            for value in item.get("canonicalIds", [])
            if isinstance(value, str) and value in graph_edges
        ]
        edge_id = canonical_ids[0] if canonical_ids else str(item["id"])
        edge = graph_edges.get(edge_id)
        source = inverse.get(item["source"])
        target = inverse.get(item["target"])
        if source is None or target is None:
            continue
        edges.append(
            SolutionLayoutEdge(
                id=edge_id,
                source=source,
                target=target,
                route=[
                    LayoutPoint(x=float(point[0]), y=float(point[1]))
                    for point in item["points"]
                ],
                interface_ids=edge.interface_ids if edge is not None else [],
                label=str(item["label"]) if item.get("label") else None,
            )
        )
    bounds = layout["bounds"]
    return SolutionLayoutResult(
        request_id=graph.selection.id,
        graph_id=graph.id,
        selection_id=graph.selection.id,
        nodes=sorted(nodes, key=lambda item: item.id),
        edges=sorted(edges, key=lambda item: item.id),
        bounds=LayoutBounds(
            x=float(bounds.get("x", 0)),
            y=float(bounds.get("y", 0)),
            width=float(bounds["width"]),
            height=float(bounds["height"]),
        ),
    )


def _svg(
    *,
    graph: ViewGraph,
    layout: SolutionLayoutResult,
) -> bytes:
    """Render direct semantic SVG from the exact LikeC4 layout geometry."""
    node_by_id = {node.id: node for node in graph.nodes}
    edge_by_id = {edge.id: edge for edge in graph.edges}
    width = layout.bounds.width + 40
    height = layout.bounds.height + 40
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
            f'viewBox="-20 -20 {width:g} {height:g}" '
            f'data-selection-id="{html.escape(graph.selection.id)}" '
            f'data-viewgraph-id="{html.escape(graph.id)}">'
        ),
        f"<title>{html.escape(graph.resolved_state.name or graph.resolved_state.id)}</title>",
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="context-stroke"/></marker></defs>',
        '<g class="edges" fill="none">',
    ]
    for rendered in layout.edges:
        edge = edge_by_id.get(rendered.id)
        if edge is None:
            edge_id = rendered.id
            interface_ids = rendered.interface_ids
            context_status = "no_change"
            status = "No Change"
            edge_name = rendered.label
        else:
            edge_id = edge.id
            interface_ids = rendered.interface_ids
            context_status = edge.context_status
            status = edge.status
            edge_name = edge.name
        points = " ".join(f"{point.x:g},{point.y:g}" for point in rendered.route)
        lines.append(
            f'<polyline id="{html.escape(edge_id)}" data-interface-ids="{html.escape(" ".join(interface_ids))}" data-source="{html.escape(rendered.source)}" data-target="{html.escape(rendered.target)}" data-status="{status}" data-context-status="{context_status}" points="{points}" stroke="{_STATUS_COLORS[context_status][1]}" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        if edge_name and rendered.route:
            middle = rendered.route[len(rendered.route) // 2]
            lines.append(
                f'<text x="{middle.x:g}" y="{middle.y - 6:g}" text-anchor="middle" fill="#334155">{html.escape(edge_name)}</text>'
            )
    lines.append('</g><g class="nodes">')
    for rendered_node in layout.nodes:
        node = node_by_id[rendered_node.id]
        fill, stroke = _STATUS_COLORS[node.context_status]
        x, y = rendered_node.bounds.x, rendered_node.bounds.y
        width_value, height_value = (
            rendered_node.bounds.width,
            rendered_node.bounds.height,
        )
        attributes = (
            f'id="{html.escape(node.id)}" '
            f'data-kind="{node.entity_kind}" data-status="{node.status}" data-context-status="{node.context_status}" '
            f'data-parent="{html.escape(node.parent or "")}" data-icon="{html.escape(node.icon or "")}"'
        )
        dash = ' stroke-dasharray="8 5"' if node.context_status == "future" else ""
        lines.extend(
            [
                f"<g {attributes}>",
                f'<rect x="{x:g}" y="{y:g}" width="{width_value:g}" height="{height_value:g}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>',
                f'<text x="{x + width_value / 2:g}" y="{y + height_value / 2:g}" text-anchor="middle" dominant-baseline="middle" fill="#17212b">{html.escape(node.name)}</text>',
                "</g>",
            ]
        )
    lines.extend(["</g>", "</svg>"])
    return ("\n".join(lines) + "\n").encode()


def _state_bytes(*, graph: ViewGraph, suffix: Literal["yaml", "xlsx"]) -> bytes:
    with TemporaryDirectory(prefix="onetool-state-export-") as directory:
        path = Path(directory) / f"state.{suffix}"
        write_complete_state(path=path, state=graph.resolved_state)
        return path.read_bytes()


def _artifact_name(*, graph: ViewGraph, format_name: str) -> str:
    suffix = (
        "xlsx"
        if format_name == "excel"
        else "c4"
        if format_name == "likec4"
        else format_name
    )
    selection = graph.selection.selection
    selector = selection.system_set
    scope_values = [
        *selector.systems,
        *selector.system_groups,
        *selector.changes,
        *selector.change_groups,
        *selector.tags,
    ]
    source = graph.resolved_state.id.split("@", maxsplit=1)[0]
    scope = "-".join(scope_values) if scope_values else "all"
    snapshot = f"{graph.selection.roadmap_id or 'state'}-{graph.selection.order or 0}"
    return (
        f"{_slug(source)}-{_slug(scope)}-{_slug(snapshot)}-"
        f"n{selection.interface_depth}-{selection.level}.{suffix}"
    )


def _load_prior(*, output: Path, force: bool) -> tuple[dict[str, Any] | None, Path]:
    manifest = output / "manifest.json"
    if not output.exists():
        return None, manifest
    if not output.is_dir():
        raise ExportError(f"Export destination must be a directory: {output}")
    if not manifest.exists():
        if any(output.iterdir()) and not force:
            raise ExportError(f"Refusing to replace user-owned destination: {output}")
        return None, manifest
    try:
        prior = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"Refusing invalid export manifest: {manifest}") from exc
    if prior.get("owner") != _OWNER and not force:
        raise ExportError(f"Refusing user-owned export manifest: {manifest}")
    if prior.get("owner") != _OWNER:
        return None, manifest
    return prior, manifest


def export_architecture(
    *,
    input_path: Path,
    output_path: Path,
    formats: list[str],
    selections: list[SelectionInput] | None,
    drawio_mode: str,
    continue_on_error: bool,
    force: bool,
    presentation: Presentation | None = None,
) -> OperationResult:
    """Normalize once, layout once, and publish manifest-owned artifacts atomically."""
    if not formats:
        raise ExportError("At least one export format is required")
    if drawio_mode not in {"per-view", "multi-tab"}:
        raise ExportError("drawio_mode must be 'per-view' or 'multi-tab'")
    normalized_formats = list(dict.fromkeys(formats))
    unsupported = [
        item for item in normalized_formats if item not in _SUPPORTED_FORMATS
    ]
    output = output_path.resolve()
    prior, manifest_path = _load_prior(output=output, force=force)
    workspace, workspace_root, graphs, request_map = _prepare_graphs(
        input_path=input_path,
        selections=selections,
        presentation=presentation,
    )
    generated = generate_prepared_likec4(graphs)
    source, catalog_by_graph, _attachments = extend_with_diagram_catalog(
        generated=generated,
        graphs=graphs,
        workspace=workspace,
        workspace_root=workspace_root,
    )
    selected_by_graph: dict[str, dict[str, Any] | None] = {}
    renderable_graphs: list[ViewGraph] = []
    view_ids: list[str] = []
    for graph in graphs:
        selected_diagram = graph.selection.selection.diagram
        selected = next(
            (
                item
                for item in catalog_by_graph[graph.id]
                if item["id"] == selected_diagram
            ),
            None,
        )
        selected_by_graph[graph.id] = selected
        if selected is not None and selected["kind"] == "external":
            continue
        renderable_graphs.append(graph)
        view_ids.append(
            selected["likec4View"] if selected else generated.view_by_graph[graph.id]
        )
    layouts_by_graph: dict[str, SolutionLayoutResult] = {}
    if {"svg", "drawio"} & set(normalized_formats) and renderable_graphs:
        layout_payload = _layout_batch(source=source, view_ids=view_ids)
        layouts_by_graph = {
            graph.id: _neutral_layout(
                graph=graph,
                layout=layout,
                canonical_mapping=generated.canonical_to_likec4_by_graph[graph.id],
            )
            for graph, layout in zip(
                renderable_graphs, layout_payload["views"], strict=True
            )
        }

    pending: list[tuple[str, str, str | None, bytes, list[str]]] = []
    failures: list[ArtifactOutcome] = []
    errors: list[Issue] = []
    for format_name in unsupported:
        artifact_id = f"export-unsupported-{_slug(format_name)}"
        failures.append(
            ArtifactOutcome(
                id=artifact_id,
                path=str(output / f"unsupported.{_slug(format_name)}"),
                status="failed",
                format=format_name,
            )
        )
        errors.append(
            _issue(
                code="arch.unsupported_export_format",
                message=f"Unsupported architecture export format '{format_name}'",
                artifact=artifact_id,
            )
        )
    external_formats = {"svg", "drawio", "likec4"}
    for graph in graphs:
        selected = selected_by_graph[graph.id]
        for format_name in normalized_formats:
            if format_name in unsupported or (
                format_name == "drawio" and drawio_mode == "multi-tab"
            ):
                continue
            name = _artifact_name(graph=graph, format_name=format_name)
            if (
                selected is not None
                and selected["kind"] == "external"
                and format_name in external_formats
            ):
                artifact_id = f"export-{_slug(graph.selection.id)}-{format_name}"
                failures.append(
                    ArtifactOutcome(
                        id=artifact_id,
                        path=str(output / name),
                        status="failed",
                        format=format_name,
                        selection_id=graph.selection.id,
                    )
                )
                errors.append(
                    _issue(
                        code="arch.unsupported_external_diagram_export",
                        message=(
                            f"External diagram '{selected['id']}' cannot be exported "
                            f"as {format_name}"
                        ),
                        artifact=artifact_id,
                    )
                )
                continue
            fidelity: list[str] = []
            if format_name == "svg":
                layout = layouts_by_graph[graph.id]
                content = _svg(
                    graph=graph,
                    layout=layout,
                )
            elif format_name == "drawio":
                layout = layouts_by_graph[graph.id]
                content = drawio_document(
                    pages=[
                        (
                            graph,
                            layout,
                            selection_page_name(graph),
                        )
                    ]
                )
                fidelity = [
                    "React-only inspector fields and non-color status glyphs are not represented"
                ]
            elif format_name == "likec4":
                disclosure = json.dumps(
                    generated.canonical_to_likec4_by_graph[graph.id],
                    separators=(",", ":"),
                    sort_keys=True,
                )
                content = f"// canonical-id-map: {disclosure}\n{source}".encode()
            elif format_name == "yaml":
                content = _state_bytes(graph=graph, suffix="yaml")
            else:
                content = _state_bytes(graph=graph, suffix="xlsx")
            pending.append(
                (
                    f"export-{_slug(graph.selection.id)}-{format_name}",
                    name,
                    graph.selection.id,
                    content,
                    fidelity,
                )
            )
    if "drawio" in normalized_formats and drawio_mode == "multi-tab":
        artifact_id = "export-multi-tab-drawio"
        external = [
            selected
            for selected in selected_by_graph.values()
            if selected is not None and selected["kind"] == "external"
        ]
        if external:
            failures.append(
                ArtifactOutcome(
                    id=artifact_id,
                    path=str(output / "architecture-views.drawio"),
                    status="failed",
                    format="drawio",
                )
            )
            errors.append(
                _issue(
                    code="arch.unsupported_external_diagram_export",
                    message=(
                        "Multi-tab Draw.io cannot include external diagrams: "
                        + ", ".join(str(item["id"]) for item in external)
                    ),
                    artifact=artifact_id,
                )
            )
        else:
            pending.append(
                (
                    artifact_id,
                    "architecture-views.drawio",
                    None,
                    drawio_document(
                        pages=[
                            (
                                graph,
                                layouts_by_graph[graph.id],
                                selection_page_name(graph),
                            )
                            for graph in graphs
                        ]
                    ),
                    [
                        "React-only inspector fields and non-color status glyphs are not represented"
                    ],
                )
            )
    if errors and not continue_on_error:
        return OperationResult(
            ok=False,
            operation="export",
            issues=IssueCollection(errors=errors),
            summary=ResultSummary(
                errors=len(errors),
                requested=len(failures),
                failed=len(failures),
            ),
            selections=[graph.selection.id for graph in graphs],
            artifacts=failures,
            data={"published": False, "request_map": request_map},
        )

    output.mkdir(parents=True, exist_ok=True)
    outcomes: list[ArtifactOutcome] = [*failures]
    current_names: set[str] = set()
    manifest_artifacts: list[dict[str, Any]] = []
    for artifact_id, name, selection_id, content, fidelity in pending:
        path = output / name
        current_names.add(name)
        content_hash = _hash(content)
        status: Literal["generated", "reused"] = "generated"
        if path.is_file() and _hash(path.read_bytes()) == content_hash:
            status = "reused"
        else:
            _atomic(path, content)
        outcome = ArtifactOutcome(
            id=artifact_id,
            path=str(path),
            status=status,
            format=path.suffix.removeprefix("."),
            content_hash=content_hash,
            selection_id=selection_id,
            fidelity=fidelity,
        )
        outcomes.append(outcome)
        manifest_artifacts.append(outcome.model_dump(mode="json", exclude_none=True))
    if prior is not None:
        for artifact in prior.get("artifacts", []):
            name = artifact.get("path")
            if not isinstance(name, str) or name in current_names:
                continue
            stale = (output / name).resolve()
            try:
                stale.relative_to(output)
            except ValueError:
                continue
            if stale.is_file():
                stale.unlink()
                outcomes.append(
                    ArtifactOutcome(
                        id=f"removed-{_slug(name)}",
                        path=str(stale),
                        status="removed_stale",
                        format=stale.suffix.removeprefix("."),
                    )
                )
    manifest_payload = {
        "schema_version": 1,
        "owner": _OWNER,
        "exporter_version": _EXPORTER_VERSION,
        "requests": request_map,
        "artifacts": [
            {
                "path": Path(item["path"]).name,
                **{key: value for key, value in item.items() if key != "path"},
            }
            for item in manifest_artifacts
        ],
    }
    manifest_content = (
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"
    ).encode()
    manifest_hash = _hash(manifest_content)
    manifest_status: Literal["generated", "reused"] = "generated"
    if manifest_path.is_file() and _hash(manifest_path.read_bytes()) == manifest_hash:
        manifest_status = "reused"
    else:
        _atomic(manifest_path, manifest_content)
    outcomes.append(
        ArtifactOutcome(
            id="export-manifest",
            path=str(manifest_path),
            status=manifest_status,
            format="json",
            content_hash=manifest_hash,
        )
    )
    return OperationResult(
        ok=not errors,
        partial=bool(errors and pending),
        operation="export",
        issues=IssueCollection(errors=errors),
        summary=ResultSummary(
            errors=len(errors),
            requested=sum(item.status != "removed_stale" for item in outcomes),
            generated=sum(item.status == "generated" for item in outcomes),
            reused=sum(item.status == "reused" for item in outcomes),
            failed=sum(item.status == "failed" for item in outcomes),
            removed_stale=sum(item.status == "removed_stale" for item in outcomes),
        ),
        selections=[graph.selection.id for graph in graphs],
        artifacts=outcomes,
        data={"request_map": request_map, "drawio_mode": drawio_mode},
    )


def export_error_result(exc: Exception) -> OperationResult:
    """Convert pre-publication exporter failures into the common envelope."""
    issue = _issue(code="arch.export_failed", message=str(exc))
    return OperationResult(
        ok=False,
        operation="export",
        issues=IssueCollection(errors=[issue]),
        summary=ResultSummary(errors=1),
        data={"published": False},
    )


EXPORT_EXCEPTIONS = (
    OSError,
    ExportError,
    WorkspaceLoadError,
    WorkspaceWriteError,
    LikeC4BoundaryError,
    DiagramCatalogError,
    PresentationError,
)
