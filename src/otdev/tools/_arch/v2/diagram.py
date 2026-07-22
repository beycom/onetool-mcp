"""Safe diagram catalog and authored view-only LikeC4 boundary."""

from __future__ import annotations

import base64
import hashlib
import html
import mimetypes
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .likec4 import generated_identifier

if TYPE_CHECKING:
    from .likec4 import GeneratedLikeC4Prepared
    from .models import ArchitectureWorkspace, DiagramCatalogEntry, ViewGraph

VIEW_ONLY_VERSION = "likec4-1.58.0-subset-1"
VIEW_ONLY_ALLOWLIST = frozenset(
    {
        "views",
        "view",
        "dynamic view",
        "include",
        "exclude",
        "group",
        "title",
        "description",
        "notes",
        "navigateTo",
        "style",
        "autoLayout",
        "parallel",
        "it",
    }
)
ATTACHMENT_SUFFIXES = frozenset({".puml", ".plantuml", ".mmd", ".mermaid", ".svg", ".pdf", ".html"})
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_BYTES = 25 * 1024 * 1024

_LOGICAL_DECLARATION = re.compile(
    r"(?m)^\s*(?P<statement>model|specification|deployment)\b"
)
_CANONICAL_REFERENCE = re.compile(r"@\{(?P<identifier>[^}]+)\}")
_VIEW_DECLARATION = re.compile(r"(?m)^(?P<indent>\s*)(?P<dynamic>dynamic\s+)?view\s+(?P<id>[A-Za-z_][\w]*)\b")
_REMOTE = re.compile(r"(?:https?:)?//", re.IGNORECASE)
_UNSAFE_MARKUP = re.compile(
    r"<\s*(?:script|iframe|object|embed|foreignObject)\b|\bon\w+\s*=|\b(?:href|src)\s*=\s*['\"]\s*(?:https?:|//|javascript:|data:text/html)",
    re.IGNORECASE,
)


class DiagramCatalogError(ValueError):
    """Raised for a source-located diagram catalog or safety failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        diagram_id: str,
        path: Path | None = None,
        line: int | None = None,
        identifier: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.diagram_id = diagram_id
        self.path = path
        self.line = line
        self.identifier = identifier


def _contained_file(*, root: Path, source: str, diagram_id: str) -> Path:
    if _REMOTE.search(source) or Path(source).is_absolute():
        raise DiagramCatalogError(
            code="arch.unsafe_diagram_source",
            message=f"Diagram '{diagram_id}' source must be a local workspace-relative path",
            diagram_id=diagram_id,
        )
    path = (root / source).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise DiagramCatalogError(
            code="arch.diagram_path_escape",
            message=f"Diagram '{diagram_id}' source escapes the workspace: {source}",
            diagram_id=diagram_id,
            path=path,
        ) from exc
    if not path.is_file():
        raise DiagramCatalogError(
            code="arch.missing_diagram_source",
            message=f"Diagram '{diagram_id}' source does not exist: {source}",
            diagram_id=diagram_id,
            path=path,
        )
    return path


def validate_view_only_source(
    *,
    source: str,
    path: Path,
    diagram_id: str,
    canonical_mapping: dict[str, str],
    graph: ViewGraph,
) -> tuple[str, dict[str, str]]:
    """Validate, map canonical references, and isolate authored view identifiers."""
    declaration = _LOGICAL_DECLARATION.search(source)
    if declaration:
        line = source.count("\n", 0, declaration.start()) + 1
        statement = declaration.group("statement")
        raise DiagramCatalogError(
            code="arch.likec4_logical_declaration",
            message=f"View-only diagram '{diagram_id}' declares disallowed '{statement}' at {path}:{line}",
            diagram_id=diagram_id,
            path=path,
            line=line,
            identifier=statement,
        )
    if not re.search(r"(?m)^\s*views\s*\{", source):
        raise DiagramCatalogError(
            code="arch.likec4_views_required",
            message=f"View-only diagram '{diagram_id}' must contain a views block",
            diagram_id=diagram_id,
            path=path,
        )

    node_by_id = {node.id: node for node in graph.nodes}

    def replace_reference(match: re.Match[str]) -> str:
        identifier = match.group("identifier")
        mapped = canonical_mapping.get(identifier)
        if mapped is None:
            line = source.count("\n", 0, match.start()) + 1
            raise DiagramCatalogError(
                code="arch.likec4_unknown_generated_id",
                message=f"Diagram '{diagram_id}' references unknown canonical ID '{identifier}' at {path}:{line}",
                diagram_id=diagram_id,
                path=path,
                line=line,
                identifier=identifier,
            )
        return mapped

    for interaction in re.finditer(r"@\{([^}]+)\}\s*->\s*@\{([^}]+)\}", source):
        for identifier in interaction.groups():
            node = node_by_id.get(identifier)
            if node is None:
                continue
            if node.children:
                line = source.count("\n", 0, interaction.start()) + 1
                raise DiagramCatalogError(
                    code="arch.invalid_sequence_participant",
                    message=f"Dynamic step uses non-leaf participant '{identifier}' at {path}:{line}",
                    diagram_id=diagram_id,
                    path=path,
                    line=line,
                    identifier=identifier,
                )

    mapped_source = _CANONICAL_REFERENCE.sub(replace_reference, source)
    view_ids: dict[str, str] = {}

    def replace_view(match: re.Match[str]) -> str:
        authored_id = match.group("id")
        isolated = generated_identifier(
            kind="catalog_view",
            canonical_id=f"{graph.id}:{diagram_id}:{authored_id}",
        )
        view_ids[authored_id] = isolated
        dynamic = match.group("dynamic") or ""
        return f"{match.group('indent')}{dynamic}view {isolated}"

    mapped_source = _VIEW_DECLARATION.sub(replace_view, mapped_source)
    if not view_ids:
        raise DiagramCatalogError(
            code="arch.likec4_view_required",
            message=f"View-only diagram '{diagram_id}' declares no static or dynamic view",
            diagram_id=diagram_id,
            path=path,
        )
    for authored_id, isolated in view_ids.items():
        mapped_source = re.sub(
            rf"(?<=\bnavigateTo\s){re.escape(authored_id)}\b",
            isolated,
            mapped_source,
        )
    return mapped_source, view_ids


def _safe_attachment(*, path: Path, diagram_id: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix not in ATTACHMENT_SUFFIXES:
        raise DiagramCatalogError(
            code="arch.unsupported_attachment",
            message=f"Diagram '{diagram_id}' has unsupported attachment type '{suffix}'",
            diagram_id=diagram_id,
            path=path,
        )
    size = path.stat().st_size
    if size > MAX_ATTACHMENT_BYTES:
        raise DiagramCatalogError(
            code="arch.attachment_too_large",
            message=(
                f"Diagram '{diagram_id}' attachment is {size} bytes; "
                f"the limit is {MAX_ATTACHMENT_BYTES} bytes"
            ),
            diagram_id=diagram_id,
            path=path,
        )
    content = path.read_bytes()
    if suffix in {".svg", ".html"}:
        try:
            markup = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DiagramCatalogError(
                code="arch.invalid_attachment_encoding",
                message=f"Diagram '{diagram_id}' attachment must be UTF-8: {path}",
                diagram_id=diagram_id,
                path=path,
            ) from exc
        if _UNSAFE_MARKUP.search(markup):
            raise DiagramCatalogError(
                code="arch.unsafe_attachment_markup",
                message=f"Diagram '{diagram_id}' attachment contains unsafe markup: {path}",
                diagram_id=diagram_id,
                path=path,
            )
    mime = (
        "text/plain"
        if suffix in {".puml", ".plantuml", ".mmd", ".mermaid"}
        else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    )
    content_hash = hashlib.sha256(content).hexdigest()
    return {
        "id": f"attachment-{content_hash}",
        "mediaType": mime,
        "dataUrl": f"data:{mime};base64,{base64.b64encode(content).decode()}",
        "size": len(content),
    }


def _applicable(entry: DiagramCatalogEntry, graph: ViewGraph) -> bool:
    nodes = {node.id for node in graph.nodes}
    changes = set(graph.focus) | {change.id for change in graph.changes}
    return (not entry.systems or set(entry.systems) <= nodes) and (
        not entry.changes or set(entry.changes) <= changes
    )


def extend_with_diagram_catalog(
    *,
    generated: GeneratedLikeC4Prepared,
    graphs: list[ViewGraph],
    workspace: ArchitectureWorkspace,
    workspace_root: Path,
) -> tuple[str, dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Append isolated view-only sources and embed safe external catalog entries."""
    additions: list[str] = []
    by_graph: dict[str, list[dict[str, Any]]] = {}
    attachments: dict[str, dict[str, Any]] = {}
    attachments_by_path: dict[Path, dict[str, Any]] = {}
    total_attachment_bytes = 0
    for graph in graphs:
        catalog: list[dict[str, Any]] = [
            {
                "id": f"generated:{graph.id}",
                "name": "Architecture",
                "kind": "generated",
                "likec4View": generated.view_by_graph[graph.id],
                "variants": [],
                "systems": [],
                "changes": [],
            }
        ]
        mapping = generated.canonical_to_likec4_by_graph[graph.id]
        for entry in workspace.diagrams:
            if not _applicable(entry, graph):
                continue
            item: dict[str, Any] = {
                "id": entry.id,
                "name": entry.name,
                "kind": entry.kind,
                "source": entry.source,
                "folder": entry.folder,
                "systems": entry.systems,
                "changes": entry.changes,
                "variants": [variant.model_dump(mode="json") for variant in entry.variants],
            }
            if entry.source is not None:
                path = _contained_file(
                    root=workspace_root,
                    source=entry.source,
                    diagram_id=entry.id,
                )
                if entry.kind in {"static", "dynamic"}:
                    if path.suffix.lower() != ".c4":
                        raise DiagramCatalogError(
                            code="arch.invalid_view_source_type",
                            message=f"View-only diagram '{entry.id}' source must use .c4",
                            diagram_id=entry.id,
                            path=path,
                        )
                    authored, views = validate_view_only_source(
                        source=path.read_text(encoding="utf-8"),
                        path=path,
                        diagram_id=entry.id,
                        canonical_mapping=mapping,
                        graph=graph,
                    )
                    additions.append(authored)
                    requested = entry.likec4_view or next(iter(views))
                    if requested not in views:
                        raise DiagramCatalogError(
                            code="arch.unknown_catalog_view",
                            message=f"Diagram '{entry.id}' selects unknown authored view '{requested}'",
                            diagram_id=entry.id,
                            path=path,
                            identifier=requested,
                        )
                    item["likec4View"] = views[requested]
                elif entry.kind == "external":
                    attachment = attachments_by_path.get(path)
                    if attachment is None:
                        attachment = _safe_attachment(path=path, diagram_id=entry.id)
                        attachments_by_path[path] = attachment
                        if attachment["id"] not in attachments:
                            if total_attachment_bytes + attachment["size"] > MAX_TOTAL_ATTACHMENT_BYTES:
                                raise DiagramCatalogError(
                                    code="arch.attachments_too_large",
                                    message=(
                                        "Distinct architecture attachments exceed the "
                                        f"{MAX_TOTAL_ATTACHMENT_BYTES}-byte aggregate limit"
                                    ),
                                    diagram_id=entry.id,
                                    path=path,
                                )
                            attachments[attachment["id"]] = {
                                key: value
                                for key, value in attachment.items()
                                if key != "id"
                            }
                            total_attachment_bytes += attachment["size"]
                    item["attachmentId"] = attachment["id"]
            catalog.append({key: value for key, value in item.items() if value is not None})
        by_graph[graph.id] = catalog
    return generated.source + "\n" + "\n".join(additions), by_graph, attachments


def attachment_placeholder(entry_id: str) -> str:
    """Return escaped fallback text for non-embeddable attachment consumers."""
    return html.escape(f"Attachment: {entry_id}")
