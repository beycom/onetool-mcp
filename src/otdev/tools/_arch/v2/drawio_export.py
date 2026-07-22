"""Deterministic editable Draw.io export from canonical graph geometry."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .models import SolutionLayoutResult, ViewGraph, ViewGraphEdge, ViewGraphNode

_MODIFIED = "2026-01-01T00:00:00.000Z"


def _number(value: float) -> str:
    return f"{value:g}"


def _color(value: str | None, fallback: str) -> str:
    return value if value and value.startswith("#") else fallback


def _border(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    candidate = value.split(maxsplit=1)[0]
    return candidate if candidate.startswith("#") else fallback


def _node_style(node: ViewGraphNode) -> str:
    fill = _color(node.style.color if node.style else None, "#f8fafc")
    stroke = _border(node.style.border if node.style else None, "#64748b")
    parts = [
        "rounded=1",
        "whiteSpace=wrap",
        "html=1",
        f"fillColor={fill}",
        f"strokeColor={stroke}",
    ]
    if node.status == "Removed":
        parts.extend(["dashed=1", "strokeWidth=2"])
    return ";".join(parts) + ";"


def _edge_style(edge: ViewGraphEdge | None) -> str:
    color = _color(edge.style.color if edge and edge.style else None, "#64748b")
    stroke = _border(edge.style.border if edge and edge.style else None, color)
    parts = [
        "edgeStyle=orthogonalEdgeStyle",
        "rounded=1",
        "html=1",
        f"strokeColor={stroke}",
    ]
    if edge and edge.direction in {"consumer_to_provider", "reverse"}:
        parts.extend(["startArrow=block", "endArrow=none"])
    elif edge and edge.direction == "bidirectional":
        parts.extend(["startArrow=block", "endArrow=block"])
    else:
        parts.extend(["startArrow=none", "endArrow=block"])
    if edge and edge.status == "Removed":
        parts.extend(["dashed=1", "strokeWidth=2"])
    return ";".join(parts) + ";"


def _diagram(
    *, graph: ViewGraph, layout: SolutionLayoutResult, name: str
) -> ET.Element:
    selection = graph.selection.selection.model_dump(mode="json", exclude_none=True)
    diagram = ET.Element(
        "diagram",
        {
            "id": hashlib.sha256(graph.selection.id.encode()).hexdigest()[:16],
            "name": name,
            "selectionId": graph.selection.id,
            "viewGraphId": graph.id,
            "snapshotId": graph.selection.state_id,
            "selection": json.dumps(selection, separators=(",", ":"), sort_keys=True),
        },
    )
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "0",
            "dy": "0",
            "grid": "1",
            "gridSize": "10",
            "page": "1",
            "pageScale": "1",
            "pageWidth": _number(layout.bounds.width),
            "pageHeight": _number(layout.bounds.height),
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    graph_nodes = {node.id: node for node in graph.nodes}
    layout_nodes = {node.id: node for node in layout.nodes}
    for item in sorted(layout.nodes, key=lambda candidate: candidate.id):
        node = graph_nodes[item.id]
        parent = item.parent if item.parent in layout_nodes else "1"
        parent_bounds = layout_nodes[parent].bounds if parent != "1" else None
        x = item.bounds.x - (parent_bounds.x if parent_bounds else 0)
        y = item.bounds.y - (parent_bounds.y if parent_bounds else 0)
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": node.id,
                "value": node.name,
                "style": _node_style(node),
                "vertex": "1",
                "parent": parent,
                "canonicalId": node.id,
                "kind": node.entity_kind,
                "status": node.status,
                "selectionId": graph.selection.id,
            },
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": _number(x),
                "y": _number(y),
                "width": _number(item.bounds.width),
                "height": _number(item.bounds.height),
                "as": "geometry",
            },
        )
    graph_edges = {edge.id: edge for edge in graph.edges}
    for layout_edge in sorted(layout.edges, key=lambda candidate: candidate.id):
        edge = graph_edges.get(layout_edge.id)
        edge_id = edge.id if edge else layout_edge.id
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": edge_id,
                "value": edge.name if edge else layout_edge.label or "",
                "style": _edge_style(edge),
                "edge": "1",
                "parent": "1",
                "source": layout_edge.source,
                "target": layout_edge.target,
                "canonicalId": edge.id if edge else "",
                "interfaceIds": ",".join(layout_edge.interface_ids),
                "kind": edge.entity_kind if edge else "relationship",
                "status": edge.status if edge else "No Change",
                "selectionId": graph.selection.id,
            },
        )
        geometry = ET.SubElement(
            cell, "mxGeometry", {"relative": "1", "as": "geometry"}
        )
        points = ET.SubElement(geometry, "Array", {"as": "points"})
        for point in layout_edge.route:
            ET.SubElement(
                points,
                "mxPoint",
                {"x": _number(point.x), "y": _number(point.y)},
            )
    return diagram


def drawio_document(
    *, pages: list[tuple[ViewGraph, SolutionLayoutResult, str]]
) -> bytes:
    """Return one deterministic uncompressed Draw.io document."""
    root = ET.Element(
        "mxfile",
        {
            "host": "OneTool",
            "modified": _MODIFIED,
            "agent": "OneTool architecture exporter",
            "version": "1",
            "type": "device",
            "compressed": "false",
        },
    )
    for graph, layout, name in pages:
        root.append(_diagram(graph=graph, layout=layout, name=name))
    ET.indent(root, space="  ")
    return cast("bytes", ET.tostring(root, encoding="utf-8", xml_declaration=True))
