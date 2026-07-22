"""Production ViewGraph preparation and self-contained explorer build."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TYPE_CHECKING, Any, Literal

from .diagram import extend_with_diagram_catalog
from .likec4 import compile_likec4, generate_prepared_likec4
from .load import EXCEL_SUFFIXES, YAML_SUFFIXES, load_workspace
from .presentation import resolve_graph_presentation, resolve_theme
from .projection import prepare_solution_snapshots, project_solution
from .replay import RoadmapReplayTimeline, prepare_roadmap_timeline
from .validation import validate_workspace, validation_failure
from .viewgraph import normalize_selection, resolve_view_graph

if TYPE_CHECKING:
    from .models import (
        ArchitectureWorkspace,
        PreparedSolutionSnapshots,
        Presentation,
        SelectionInput,
        ViewGraph,
    )

_OWNER = "onetool-arch-v2"
_MARKER = '<meta content="onetool-arch-v2" name="generator">'


class ExplorerBuildError(ValueError):
    """Raised when explorer preparation, ownership, or frontend build fails."""


def _frontend_root() -> Path:
    return Path(__file__).parents[1] / "frontend"


def resolve_workspace_source(input_path: Path) -> tuple[Path, Path]:
    resolved = input_path.resolve()
    if resolved.is_file():
        return resolved, resolved.parent
    if not resolved.is_dir():
        raise ExplorerBuildError(f"Architecture input does not exist: {resolved}")
    preferred = [resolved / "architecture.yaml", resolved / "architecture.xlsx"]
    candidates = [path for path in preferred if path.is_file()]
    if not candidates:
        candidates = sorted(
            path
            for path in resolved.iterdir()
            if path.is_file() and path.suffix.lower() in YAML_SUFFIXES | EXCEL_SUFFIXES
        )
    if len(candidates) != 1 and preferred[0] not in candidates:
        raise ExplorerBuildError(
            f"Workspace directory must contain architecture.yaml or one schema-v2 source: {resolved}"
        )
    return (preferred[0] if preferred[0] in candidates else candidates[0]), resolved


def prepare_explorer_data(
    *,
    workspace: ArchitectureWorkspace,
    workspace_root: Path,
    selections: list[SelectionInput] | None,
) -> tuple[dict[str, Any], str]:
    """Resolve, deduplicate, present, compile, and serialize browser-ready graphs."""
    requested: list[SelectionInput | None] = (
        list(selections) if selections is not None else [None]
    )
    graphs: dict[str, ViewGraph] = {}
    prepared_by_roadmap: dict[str, PreparedSolutionSnapshots] = {}
    replay_by_roadmap: dict[str, RoadmapReplayTimeline] = {}
    warnings: list[str] = []
    initial_id: str | None = None
    for value in requested:
        try:
            normalized = normalize_selection(workspace=workspace, value=value)
        except ValueError as exc:
            raise ExplorerBuildError(str(exc)) from exc
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
        if resolved.issues.errors:
            raise ExplorerBuildError(
                "; ".join(issue.message for issue in resolved.issues.errors)
            )
        warnings.extend(issue.message for issue in resolved.issues.warnings)
        assert resolved.graph is not None
        graph = resolved.graph
        if graph.selection.roadmap_id is not None:
            roadmap_id = graph.selection.roadmap_id
            prepared = prepared_by_roadmap.get(roadmap_id)
            if prepared is None:
                prepared = prepare_solution_snapshots(
                    workspace=workspace,
                    roadmap_id=roadmap_id,
                    replay_timeline=replay_timeline,
                )
                prepared_by_roadmap[roadmap_id] = prepared
            assert graph.selection.order is not None
            projected = project_solution(
                prepared=prepared,
                order=graph.selection.order,
                selector=graph.selection.selection.system_set,
                interface_depth=graph.selection.selection.interface_depth,
                level=graph.selection.selection.level,
                selection=graph.selection.selection,
            )
            graph = projected.graph
        if initial_id is None:
            initial_id = graph.id
        graphs[graph.selection.id] = graph
    assert initial_id is not None
    presented = [
        resolve_graph_presentation(
            graph=graph,
            workspace=workspace,
            workspace_root=workspace_root,
        )
        for graph in graphs.values()
    ]
    generated = generate_prepared_likec4(presented)
    source, diagram_catalog, attachments = extend_with_diagram_catalog(
        generated=generated,
        graphs=presented,
        workspace=workspace,
        workspace_root=workspace_root,
    )
    compiled = compile_likec4(source)
    compiled_by_id = {view["id"]: view for view in compiled.get("views", [])}
    edge_mappings = {
        graph.id: compiled_by_id.get(generated.view_by_graph[graph.id], {}).get(
            "edgeMappings", {}
        )
        for graph in presented
    }
    presentation = workspace.presentation.model_dump(mode="json", exclude_none=True)
    theme_ids = {
        "clean",
        workspace.presentation.default_theme,
        *(theme.id for theme in workspace.presentation.themes),
    }
    presentation["resolved_themes"] = {
        theme_id: resolve_theme(workspace=workspace, theme_id=theme_id).model_dump(
            mode="json", exclude_none=True
        )
        for theme_id in sorted(theme_ids)
    }
    payload = {
        "schemaVersion": 1,
        "title": workspace.presentation.title,
        "initialGraphId": initial_id,
        "graphs": [
            graph.model_dump(mode="json", exclude_none=True) for graph in presented
        ],
        "likec4ViewByGraph": generated.view_by_graph,
        "canonicalToLikec4ByGraph": generated.canonical_to_likec4_by_graph,
        "likec4EdgeToCanonicalByGraph": edge_mappings,
        "diagramCatalogByGraph": diagram_catalog,
        "attachments": attachments,
        "tableConfigs": [
            table.model_dump(mode="json", exclude_none=True)
            for table in workspace.presentation.tables
        ],
        "solutionSnapshots": {
            roadmap_id: prepared.model_dump(mode="json", exclude_none=True)
            for roadmap_id, prepared in prepared_by_roadmap.items()
        },
        "presentation": presentation,
        "unavailableOrders": sorted(
            {
                order
                for prepared in prepared_by_roadmap.values()
                for order in prepared.unavailable_orders
            }
        ),
        "diagnostics": list(dict.fromkeys(warnings)),
    }
    return payload, source


def _build_html(*, data: dict[str, Any], source: str, directory: Path) -> Path:
    frontend = _frontend_root()
    vite = frontend / "node_modules" / ".bin" / "vite"
    if not vite.is_file():
        raise ExplorerBuildError(
            "Pinned frontend dependencies are unavailable; run npm ci in the arch frontend"
        )
    data_path = directory / "architecture-data.json"
    data_path.write_text(
        json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    likec4_workspace = directory / "likec4"
    likec4_workspace.mkdir()
    (likec4_workspace / "model.c4").write_text(source, encoding="utf-8")
    output = directory / "dist"
    environment = {
        **os.environ,
        "ONETOOL_ARCH_DATA": str(data_path),
        "ONETOOL_LIKEC4_WORKSPACE": str(likec4_workspace),
    }
    result = subprocess.run(
        [str(vite), "build", "--outDir", str(output), "--emptyOutDir"],
        cwd=frontend,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ExplorerBuildError(result.stderr.strip() or result.stdout.strip())
    html = output / "index.html"
    if not html.is_file():
        raise ExplorerBuildError("Frontend build did not produce index.html")
    content = html.read_text(encoding="utf-8")
    if "</head>" not in content:
        raise ExplorerBuildError("Frontend output has no document head")
    html.write_text(
        content.replace("</head>", f"{_MARKER}</head>", 1), encoding="utf-8"
    )
    return html


def _destination(output_path: Path) -> tuple[Path, Path]:
    if output_path.suffix.lower() == ".html":
        report = output_path
        manifest = output_path.with_suffix(".manifest.json")
    else:
        report = output_path / "architecture-explorer.html"
        manifest = output_path / "manifest.json"
    return report, manifest


def _owned_report(path: Path) -> bool:
    try:
        return _MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent, delete=False, prefix=f".{path.name}."
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    temporary.replace(path)


def generate_explorer(
    *,
    input_path: Path,
    output_path: Path,
    selections: list[SelectionInput] | None,
    force: bool,
    presentation: Presentation | None = None,
) -> tuple[
    str,
    Literal["generated", "reused"],
    Path,
    Path,
    dict[str, Any],
]:
    """Build and atomically replace or reuse one manifest-owned explorer."""
    source_path, workspace_root = resolve_workspace_source(input_path)
    workspace = load_workspace(source_path, presentation=presentation).workspace
    validation_issues, _counts = validate_workspace(
        workspace=workspace,
        workspace_root=workspace_root,
    )
    if validation_issues.errors:
        raise ExplorerBuildError(validation_failure(validation_issues))
    data, likec4_source = prepare_explorer_data(
        workspace=workspace,
        workspace_root=workspace_root,
        selections=selections,
    )
    report, manifest = _destination(output_path.resolve())
    if report.exists() and not force and not _owned_report(report):
        raise ExplorerBuildError(
            f"Refusing to replace user-owned destination: {report}"
        )
    if manifest.exists() and not force:
        try:
            prior = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExplorerBuildError(
                f"Refusing to replace invalid user manifest: {manifest}"
            ) from exc
        if prior.get("owner") != _OWNER:
            raise ExplorerBuildError(
                f"Refusing to replace user-owned manifest: {manifest}"
            )

    with TemporaryDirectory(prefix="onetool-arch-") as temporary:
        html = _build_html(data=data, source=likec4_source, directory=Path(temporary))
        content = html.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    status: Literal["generated", "reused"] = "generated"
    if (
        report.is_file()
        and hashlib.sha256(report.read_bytes()).hexdigest() == content_hash
    ):
        status = "reused"
    else:
        _atomic_bytes(report, content)
    manifest_payload = {
        "schema_version": 1,
        "owner": _OWNER,
        "artifacts": [
            {
                "path": report.name,
                "format": "html",
                "content_hash": content_hash,
                "selection_ids": [graph["selection"]["id"] for graph in data["graphs"]],
            }
        ],
    }
    _atomic_bytes(
        manifest,
        (json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n").encode(),
    )
    return content_hash, status, report, manifest, data
