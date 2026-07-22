"""Deterministic LikeC4 source generation and pinned compile/layout boundary."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .cache import LIKEC4_COMPILE_CACHE

if TYPE_CHECKING:
    from .models import ViewGraph, ViewGraphNode

_IDENTIFIER = re.compile(r"[^a-z0-9_]+")


class LikeC4BoundaryError(ValueError):
    """Raised when generated source cannot pass the pinned LikeC4 boundary."""


@dataclass(frozen=True)
class GeneratedLikeC4:
    """Generated source plus disclosed stable canonical mappings."""

    source: str
    canonical_to_likec4: dict[str, str]
    view_ids: list[str]


@dataclass(frozen=True)
class GeneratedLikeC4Prepared:
    """Multi-order generated model with one pre-layout view per ViewGraph."""

    source: str
    canonical_to_likec4_by_graph: dict[str, dict[str, str]]
    view_by_graph: dict[str, str]


def generated_identifier(*, kind: str, canonical_id: str) -> str:
    """Return a readable collision-resistant LikeC4 local identifier."""
    slug = _IDENTIFIER.sub("_", canonical_id.lower()).strip("_") or "item"
    digest = hashlib.sha256(f"{kind}:{canonical_id}".encode()).hexdigest()[:8]
    return f"{kind[:3]}_{slug[:32]}_{digest}"


def _quote(value: str) -> str:
    return (
        "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'"
    )


def _element_kind(node: ViewGraphNode) -> str:
    return "actor" if node.entity_kind == "user" else node.entity_kind


def selection_page_name(graph: ViewGraph) -> str:
    """Return a deterministic human-readable page name for one selection."""
    selection = graph.selection.selection
    order = graph.selection.order
    snapshot_change = next(
        (change for change in graph.changes if change.order == order),
        None,
    )
    if order == 0:
        snapshot = "Base"
    elif snapshot_change is not None:
        snapshot = snapshot_change.name
    elif order is not None:
        snapshot = f"Order {order}"
    else:
        snapshot = selection.state or graph.selection.state_id

    scope: str | None = None
    if selection.subject is not None:
        subject = selection.subject
        if selection.browse_by == "system":
            node = next(
                (
                    item
                    for item in graph.nodes
                    if item.id == subject and item.entity_kind == "system"
                ),
                None,
            )
            subject = node.name if node is not None else subject
        elif selection.browse_by == "change":
            change = next(
                (item for item in graph.changes if item.id == subject),
                None,
            )
            subject = change.name if change is not None else subject
        if not (selection.browse_by == "change" and subject == snapshot):
            browse_label = (selection.browse_by or "scope").replace("_", " ").title()
            scope = f"{browse_label}: {subject}"
    else:
        selector_fields = (
            ("System", selection.system_set.systems),
            ("System group", selection.system_set.system_groups),
            ("Change", selection.system_set.changes),
            ("Change group", selection.system_set.change_groups),
            ("Tag", selection.system_set.tags),
        )
        selected = [
            f"{label}: {value}"
            for label, values in selector_fields
            for value in values
        ]
        scope = " + ".join(selected) if selected else "All systems"

    parts = [snapshot]
    if scope is not None:
        parts.append(scope)
    parts.extend(
        [selection.level.title(), f"depth {selection.interface_depth}"]
    )
    return " · ".join(parts)


def generate_likec4(graph: ViewGraph) -> GeneratedLikeC4:
    """Generate the logical hierarchy, relationships, metadata, and standard views."""
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise LikeC4BoundaryError("ViewGraph contains duplicate canonical node IDs")
    local = {
        node.id: generated_identifier(kind=node.entity_kind, canonical_id=node.id)
        for node in graph.nodes
    }
    children: dict[str | None, list[ViewGraphNode]] = {}
    for node in graph.nodes:
        children.setdefault(node.parent, []).append(node)
    for values in children.values():
        values.sort(key=lambda item: item.id)
    mapping: dict[str, str] = {}

    def emit_node(node: ViewGraphNode, *, depth: int, prefix: str | None) -> list[str]:
        identifier = local[node.id]
        qualified = identifier if prefix is None else f"{prefix}.{identifier}"
        mapping[node.id] = qualified
        indent = "  " * depth
        nested = children.get(node.id, [])
        opening = f"{indent}{identifier} = {_element_kind(node)} {_quote(node.name)}"
        lines = [opening + " {"]
        lines.extend(
            [
                f"{indent}  metadata {{",
                f"{indent}    canonicalId {_quote(node.id)}",
                f"{indent}    status {_quote(node.status)}",
                f"{indent}    contextStatus {_quote(node.context_status)}",
                f"{indent}  }}",
            ]
        )
        for child in nested:
            lines.extend(emit_node(child, depth=depth + 1, prefix=qualified))
        lines.append(f"{indent}}}")
        return lines

    source = [
        "specification {",
        "  element actor {",
        "    style { shape person }",
        "  }",
        "  element system",
        "  element application",
        "  element component",
        "}",
        "",
        "model {",
    ]
    for root in children.get(None, []):
        source.extend(emit_node(root, depth=1, prefix=None))
    for edge in sorted(graph.edges, key=lambda item: item.id):
        source_id = mapping.get(edge.source_id)
        target_id = mapping.get(edge.target_id)
        if source_id is None or target_id is None:
            raise LikeC4BoundaryError(
                f"Edge '{edge.id}' references an unavailable generated endpoint"
            )
        source.extend(
            [
                f"  {source_id} -> {target_id} {_quote(edge.name)} {{",
                "    metadata {",
                f"      canonicalId {_quote(edge.id)}",
                f"      status {_quote(edge.status)}",
                f"      contextStatus {_quote(edge.context_status)}",
                "    }",
                "  }",
            ]
        )
    source.extend(["}", "", "views {"])
    view_ids = ["index", "landscape"]
    source.extend(
        [
            "  view index {",
            "    title 'Architecture'",
            "    include *",
            "  }",
            "  view landscape {",
            "    title 'Landscape'",
            "    include *",
            "  }",
        ]
    )
    for node in sorted(graph.nodes, key=lambda item: item.id):
        if node.entity_kind not in {"system", "application", "component"}:
            continue
        view_id = generated_identifier(
            kind=f"view_{node.entity_kind}", canonical_id=node.id
        )
        view_ids.append(view_id)
        source.extend(
            [
                f"  view {view_id} {{",
                f"    title {_quote(node.name)}",
                f"    include {mapping[node.id]}",
            ]
        )
        if node.entity_kind != "component":
            source.append(f"    include {mapping[node.id]}.**")
        source.append("  }")
    for change in graph.changes:
        view_id = generated_identifier(kind="view_change", canonical_id=change.id)
        view_ids.append(view_id)
        source.extend(
            [
                f"  view {view_id} {{",
                f"    title {_quote(change.name)}",
                "    include *",
                "  }",
            ]
        )
    if graph.comparison is not None:
        view_id = generated_identifier(kind="view_comparison", canonical_id=graph.id)
        view_ids.append(view_id)
        source.extend(
            [
                f"  view {view_id} {{",
                "    title 'Comparison'",
                "    include *",
                "  }",
            ]
        )
    source.append("}")
    return GeneratedLikeC4(
        source="\n".join(source) + "\n",
        canonical_to_likec4=mapping,
        view_ids=view_ids,
    )


def generate_prepared_likec4(graphs: list[ViewGraph]) -> GeneratedLikeC4Prepared:
    """Generate isolated logical subtrees and one view for every prepared graph."""
    if not graphs:
        raise LikeC4BoundaryError("At least one prepared ViewGraph is required")
    source = [
        "specification {",
        "  element state",
        "  element actor { style { shape person } }",
        "  element system",
        "  element application",
        "  element component",
        "}",
        "",
        "model {",
    ]
    mappings: dict[str, dict[str, str]] = {}
    roots: dict[str, str] = {}
    pending_edges: list[tuple[str, str, str, str, str]] = []
    for graph in graphs:
        root = generated_identifier(kind="state", canonical_id=graph.id)
        roots[graph.id] = root
        mapping: dict[str, str] = {}
        mappings[graph.id] = mapping
        children: dict[str | None, list[ViewGraphNode]] = {}
        for node in graph.nodes:
            children.setdefault(node.parent, []).append(node)
        for values in children.values():
            values.sort(key=lambda item: item.id)

        def emit(
            node: ViewGraphNode,
            *,
            depth: int,
            prefix: str,
            graph_mapping: dict[str, str] = mapping,
            graph_children: dict[str | None, list[ViewGraphNode]] = children,
        ) -> list[str]:
            identifier = generated_identifier(
                kind=node.entity_kind,
                canonical_id=node.id,
            )
            qualified = f"{prefix}.{identifier}"
            graph_mapping[node.id] = qualified
            indent = "  " * depth
            lines = [
                f"{indent}{identifier} = {_element_kind(node)} {_quote(node.name)} {{"
            ]
            lines.extend(
                [
                    f"{indent}  metadata {{",
                    f"{indent}    canonicalId {_quote(node.id)}",
                    f"{indent}    status {_quote(node.status)}",
                    f"{indent}    contextStatus {_quote(node.context_status)}",
                    f"{indent}  }}",
                ]
            )
            for child in graph_children.get(node.id, []):
                lines.extend(emit(child, depth=depth + 1, prefix=qualified))
            lines.append(f"{indent}}}")
            return lines

        source.extend(
            [
                f"  {root} = state {_quote('Order ' + str(graph.selection.order or 0))} {{",
                "    metadata {",
                f"      selectionId {_quote(graph.selection.id)}",
                "    }",
            ]
        )
        for node in children.get(None, []):
            source.extend(emit(node, depth=2, prefix=root))
        source.append("  }")
        for edge in graph.edges:
            pending_edges.append(
                (graph.id, edge.id, edge.name, edge.source_id, edge.target_id)
            )
    for graph_id, edge_id, name, source_id, target_id in pending_edges:
        mapping = mappings[graph_id]
        if source_id not in mapping or target_id not in mapping:
            raise LikeC4BoundaryError(
                f"Edge '{edge_id}' references an unavailable generated endpoint"
            )
        source.extend(
            [
                f"  {mapping[source_id]} -> {mapping[target_id]} {_quote(name)} {{",
                "    metadata {",
                f"      canonicalId {_quote(edge_id)}",
                "    }",
                "  }",
            ]
        )
    source.extend(["}", "", "views {"])
    views: dict[str, str] = {}
    for graph in graphs:
        view_id = generated_identifier(kind="prepared_view", canonical_id=graph.id)
        views[graph.id] = view_id
        source.extend(
            [
                f"  view {view_id} {{",
                f"    title {_quote(selection_page_name(graph))}",
                "    autoLayout LeftRight",
                f"    include {roots[graph.id]}.**",
                "  }",
            ]
        )
    source.append("}")
    return GeneratedLikeC4Prepared(
        source="\n".join(source) + "\n",
        canonical_to_likec4_by_graph=mappings,
        view_by_graph=views,
    )


def _frontend_root() -> Path:
    return Path(__file__).parents[1] / "frontend"


def compile_likec4(source: str) -> dict[str, Any]:
    """Compile and layout generated source using the pinned local LikeC4 install."""
    source_bytes = source.encode()
    cache_key = LIKEC4_COMPILE_CACHE.key(b"likec4-1.58.0", source_bytes)
    cached = LIKEC4_COMPILE_CACHE.get(cache_key)
    if cached is not None:
        cached_payload = json.loads(cached)
        if isinstance(cached_payload, dict):
            return cached_payload
        raise LikeC4BoundaryError("Cached LikeC4 compiler result is invalid")
    command = ["node", "scripts/compile-likec4.mjs"]
    result = subprocess.run(
        command,
        cwd=_frontend_root(),
        input=source,
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
            "Pinned LikeC4 compiler returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise LikeC4BoundaryError("Pinned LikeC4 compiler returned an invalid result")
    LIKEC4_COMPILE_CACHE.put(
        cache_key,
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
    )
    return payload
