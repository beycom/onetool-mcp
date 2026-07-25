"""Pure layout computation for whiteboard.layout().

Everything here operates on plain dicts — no pydoll, no browser I/O — so the
ELK graph build, patch computation, and session write-back are unit-testable
without mocks. `excalidraw.py:layout()` orchestrates browser evals around
these helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

ELK_DIRECTIONS = {"RIGHT", "LEFT", "DOWN", "UP"}
ELK_ALGORITHMS = {"layered", "stress", "mrtree", "radial", "force"}
ELK_NODE_PLACEMENTS = {"BRANDES_KOEPF", "NETWORK_SIMPLEX", "LINEAR_SEGMENTS", "SIMPLE"}
ELK_CROSSING_MINS = {"LAYER_SWEEP", "MEDIAN_LAYER_SWEEP", "NONE"}
ELK_CYCLE_BREAKINGS = {"GREEDY", "DEPTH_FIRST", "MODEL_ORDER"}

_DEFAULT_DIMS = (160, 60)


@dataclass
class ElkBuild:
    """Everything the browser-side ELK run and the patch builders need."""

    graph: dict[str, Any]
    elem_to_elk: dict[str, str]
    elk_node_set: set[str]
    scene_edge_map: dict[str, dict[str, str]]
    boundary_edges: list[dict[str, Any]]
    offset_x: float
    offset_y: float
    node_dims: dict[str, tuple[int, int]] = field(default_factory=dict)
    all_node_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    use_selection: bool = False


def resolve_selection(scene: dict[str, Any]) -> tuple[set[str], bool]:
    """Resolve the layout scope from the live scene's selection."""
    selected_ids: list[str] = scene.get("selectedIds", [])
    return set(selected_ids), len(selected_ids) > 0


def build_elk_graph(
    scene: dict[str, Any],
    *,
    direction: str,
    gap_layer: int,
    gap_node: int,
    algorithm: str,
    node_placement: str,
    crossing_min: str,
    cycle_breaking: str,
    elk_options: dict[str, str] | None = None,
) -> ElkBuild | None:
    """Build the ELK JSON graph and all bookkeeping maps from the live scene.

    Groups collapse into atomic ELK nodes (bounding box of members). Edges
    with both endpoints in the layout scope become ELK edges; edges with
    exactly one endpoint in scope are captured as boundary edges for the
    post-layout fixup. Returns None when there is nothing to lay out.
    """
    scene_nodes: list[dict[str, Any]] = scene.get("nodes", [])
    scene_edges: list[dict[str, Any]] = scene.get("edges", [])
    selected_set, use_selection = resolve_selection(scene)

    # Save full node map before selection filter (needed to look up positions
    # of non-selected nodes when fixing boundary arrows later).
    all_node_map: dict[str, dict[str, Any]] = {n["id"]: n for n in scene_nodes}
    if use_selection:
        scene_nodes = [n for n in scene_nodes if n["id"] in selected_set]

    if not scene_nodes:
        return None

    # ELK layout offset: for a selection layout anchor to the selection's
    # top-left so nodes stay roughly in place; for a full layout use the
    # standard canvas padding.
    if use_selection:
        offset_x = float(min(n.get("x", 0) for n in scene_nodes))
        offset_y = float(min(n.get("y", 0) for n in scene_nodes))
    else:
        offset_x = 60.0
        offset_y = 60.0

    # Collapse Excalidraw groups into atomic ELK nodes: elements sharing a
    # groupId are treated as a single node (bounding box of members).
    group_to_members: dict[str, list[dict[str, Any]]] = {}
    ungrouped: list[dict[str, Any]] = []
    for n in scene_nodes:
        gids = n.get("groupIds") or []
        if gids:
            gid = gids[0]  # primary group
            group_to_members.setdefault(gid, []).append(n)
        else:
            ungrouped.append(n)

    elem_to_elk: dict[str, str] = {}
    elk_nodes = []
    node_dims: dict[str, tuple[int, int]] = {}

    for n in ungrouped:
        eid = n["id"]
        w, h = int(n["w"]), int(n["h"])
        elk_nodes.append({"id": eid, "width": w, "height": h})
        node_dims[eid] = (w, h)
        elem_to_elk[eid] = eid

    for gid, members in group_to_members.items():
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for m in members:
            mx, my = float(m.get("x", 0)), float(m.get("y", 0))
            min_x = min(min_x, mx)
            max_x = max(max_x, mx + float(m["w"]))
            min_y = min(min_y, my)
            max_y = max(max_y, my + float(m["h"]))
            elem_to_elk[m["id"]] = gid
        w, h = int(max_x - min_x) or 160, int(max_y - min_y) or 60
        elk_nodes.append({"id": gid, "width": w, "height": h})
        node_dims[gid] = (w, h)

    # Build ELK edge list from live scene arrows (both endpoints in node set)
    elk_node_set = {n["id"] for n in elk_nodes}
    elk_edges = []
    seen_edge_ids: set[str] = set()
    scene_edge_map: dict[
        str, dict[str, str]
    ] = {}  # eid → {src, dst} for STRAIGHT recompute
    # Boundary edges: exactly one endpoint is in the selection / elk_node_set.
    # After layout we update the selected-side endpoint to its new position.
    boundary_edges: list[dict[str, Any]] = []
    for edge in scene_edges:
        eid = edge["id"]
        if eid in seen_edge_ids:
            continue
        src_elk = elem_to_elk.get(edge["src"])
        dst_elk = elem_to_elk.get(edge["dst"])
        src_in = src_elk is not None and src_elk in elk_node_set
        dst_in = dst_elk is not None and dst_elk in elk_node_set
        if src_in and dst_in:
            assert src_elk is not None
            assert dst_elk is not None
            seen_edge_ids.add(eid)
            elk_edges.append({"id": eid, "sources": [src_elk], "targets": [dst_elk]})
            scene_edge_map[eid] = {"src": src_elk, "dst": dst_elk}
        elif src_in != dst_in:
            # One endpoint is in the layout scope; track for post-layout fixup
            boundary_edges.append(
                {
                    "id": eid,
                    "src": edge["src"],
                    "dst": edge["dst"],
                    "src_elk": src_elk,
                    "dst_elk": dst_elk,
                    "src_in": src_in,
                }
            )

    layered_only = algorithm == "layered"
    layout_opts: dict[str, str] = {
        "elk.algorithm": algorithm,
        "elk.direction": direction,
        "elk.spacing.nodeNode": str(gap_node),
        "elk.padding": "[top=60,left=60,bottom=60,right=60]",
    }
    if layered_only:
        layout_opts.update(
            {
                "elk.layered.spacing.nodeNodeBetweenLayers": str(gap_layer),
                "elk.layered.spacing.edgeNodeBetweenLayers": str(gap_layer // 2),
                "elk.layered.spacing.edgeEdgeBetweenLayers": "10",
                "elk.layered.nodePlacement.strategy": node_placement,
                "elk.layered.crossingMinimization.strategy": crossing_min,
                "elk.layered.cycleBreaking.strategy": cycle_breaking,
            }
        )
    if algorithm == "stress":
        layout_opts["elk.stress.desiredEdgeLength"] = str(gap_node * 3)
    if elk_options:
        layout_opts.update(elk_options)

    graph = {
        "id": "root",
        "layoutOptions": layout_opts,
        "children": elk_nodes,
        "edges": elk_edges,
    }
    return ElkBuild(
        graph=graph,
        elem_to_elk=elem_to_elk,
        elk_node_set=elk_node_set,
        scene_edge_map=scene_edge_map,
        boundary_edges=boundary_edges,
        offset_x=offset_x,
        offset_y=offset_y,
        node_dims=node_dims,
        all_node_map=all_node_map,
        use_selection=use_selection,
    )


def build_node_patches(
    positions_list: list[dict[str, Any]],
    build: ElkBuild,
    layout_state: dict[str, Any],
    *,
    font_size: int,
) -> list[dict[str, Any]]:
    """Node position patches plus DSL bound-text repositioning."""
    patches: list[dict[str, Any]] = []
    for pos in positions_list:
        id_ = pos["id"]
        x, y = float(pos["x"]), float(pos["y"])
        _w, h = build.node_dims.get(id_, _DEFAULT_DIMS)
        patches.append({"id": id_, "x": x, "y": y})
        # Also reposition the DSL-drawn text element if present
        dsl_shape = layout_state["shapes"].get(id_)
        if dsl_shape is not None:
            line_count = len((dsl_shape.get("label") or "").split("\n"))
            text_h = line_count * font_size * 1.25
            patches.append({"id": id_ + "-text", "x": x + 8, "y": y + (h - text_h) / 2})
    return patches


def position_map(
    positions_list: list[dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    """Map ELK node id → (x, y) from the ELK result."""
    return {pos["id"]: (float(pos["x"]), float(pos["y"])) for pos in positions_list}


def build_edge_patches(
    build: ElkBuild,
    positions: dict[str, tuple[float, float]],
    direction: str,
) -> list[dict[str, Any]]:
    """Recompute in-scope arrow endpoints from the new node positions.

    ELK does not return waypoints; arrows stay bound via startBinding.
    """
    patches: list[dict[str, Any]] = []
    for eid, einfo in build.scene_edge_map.items():
        src_id, dst_id = einfo["src"], einfo["dst"]
        if src_id not in positions or dst_id not in positions:
            continue
        sx, sy = positions[src_id]
        ex, ey = positions[dst_id]
        sw, sh = (float(d) for d in build.node_dims.get(src_id, _DEFAULT_DIMS))
        dw, dh = (float(d) for d in build.node_dims.get(dst_id, _DEFAULT_DIMS))
        if direction == "RIGHT":
            start: list[float] = [sx + sw, sy + sh / 2]
            end: list[float] = [ex, ey + dh / 2]
        elif direction == "LEFT":
            start = [sx, sy + sh / 2]
            end = [ex + dw, ey + dh / 2]
        elif direction == "DOWN":
            start = [sx + sw / 2, sy + sh]
            end = [ex + dw / 2, ey]
        else:  # UP
            start = [sx + sw / 2, sy]
            end = [ex + dw / 2, ey + dh]
        patches.append({"id": eid, "points": [start, end]})
    return patches


def build_boundary_arrow_patches(
    build: ElkBuild,
    positions: dict[str, tuple[float, float]],
    direction: str,
) -> list[dict[str, Any]]:
    """Fix boundary arrows: one endpoint inside the layout scope, one outside.

    Moves the inside endpoint to track its node's new position; the outside
    endpoint stays put. The connection side depends on whether the anchored
    node is the arrow's source (arrow leaves → exit side) or destination
    (arrow arrives → entry side), which is the *opposite* side from the
    layout direction. Each edge uses its own containment (``src_in``) — never
    a value carried over from another edge.
    """
    patches: list[dict[str, Any]] = []
    for bedge in build.boundary_edges:
        eid = bedge["id"]
        src_inside: bool = bedge["src_in"]
        anchored_elk = bedge["src_elk"] if src_inside else bedge["dst_elk"]
        free_id = bedge["dst"] if src_inside else bedge["src"]
        if anchored_elk not in positions:
            continue
        anc_x, anc_y = positions[anchored_elk]
        anc_w, anc_h = (
            float(d) for d in build.node_dims.get(anchored_elk, _DEFAULT_DIMS)
        )
        free_node = build.all_node_map.get(free_id) or {}
        free_x = float(free_node.get("x", 0))
        free_y = float(free_node.get("y", 0))
        free_w = float(free_node.get("w", 160))
        free_h = float(free_node.get("h", 60))

        # Determine connection points: the anchored node uses the side
        # appropriate for its role (source=exit side, dest=entry side).
        # For RIGHT layout: source exits right, dest enters left.
        if direction == "RIGHT":
            if src_inside:
                anc_pt: list[float] = [anc_x + anc_w, anc_y + anc_h / 2]
                free_pt: list[float] = [free_x, free_y + free_h / 2]
            else:
                anc_pt = [anc_x, anc_y + anc_h / 2]
                free_pt = [free_x + free_w, free_y + free_h / 2]
        elif direction == "LEFT":
            if src_inside:
                anc_pt = [anc_x, anc_y + anc_h / 2]
                free_pt = [free_x + free_w, free_y + free_h / 2]
            else:
                anc_pt = [anc_x + anc_w, anc_y + anc_h / 2]
                free_pt = [free_x, free_y + free_h / 2]
        elif direction == "DOWN":
            if src_inside:
                anc_pt = [anc_x + anc_w / 2, anc_y + anc_h]
                free_pt = [free_x + free_w / 2, free_y]
            else:
                anc_pt = [anc_x + anc_w / 2, anc_y]
                free_pt = [free_x + free_w / 2, free_y + free_h]
        else:  # UP
            if src_inside:
                anc_pt = [anc_x + anc_w / 2, anc_y]
                free_pt = [free_x + free_w / 2, free_y + free_h]
            else:
                anc_pt = [anc_x + anc_w / 2, anc_y + anc_h]
                free_pt = [free_x + free_w / 2, free_y]
        start_pt, end_pt = (anc_pt, free_pt) if src_inside else (free_pt, anc_pt)
        patches.append({"id": eid, "points": [start_pt, end_pt]})
    return patches


def build_subgraph_updates(layout_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Subgraph payloads for the browser-side bbox recompute."""
    return [
        {
            "id": gid,
            "label": group["label"],
            "memberIds": group["members"],
            "savedBounds": None,
        }
        for gid, group in layout_state["groups"].items()
    ]


def writeback_positions(
    layout_state: dict[str, Any],
    positions_list: list[dict[str, Any]],
    build: ElkBuild,
) -> int:
    """Persist computed positions into the session state dict (mutates it).

    Subsequent rerenders (screenshot/share/reload) keep this layout instead
    of re-gridding. Returns the number of shapes moved; when non-zero,
    ``canvas_max_y`` is recomputed (never shrinking it for selection layouts).
    """
    moved = 0
    for pos in positions_list:
        shape = layout_state["shapes"].get(pos["id"])
        if shape is None:
            continue
        shape["x"] = float(pos["x"])
        shape["y"] = float(pos["y"])
        moved += 1
    if moved:
        new_max = max(
            float(pos["y"]) + float(build.node_dims.get(pos["id"], _DEFAULT_DIMS)[1])
            for pos in positions_list
        )
        if build.use_selection:
            new_max = max(new_max, float(layout_state.get("canvas_max_y", 60.0)))
        layout_state["canvas_max_y"] = new_max
    return moved


def elk_run_js(build: ElkBuild) -> str:
    """The browser-side ELK invocation (assumes window.ELK is already loaded)."""
    graph_json = json.dumps(build.graph)
    return f"""
async () => {{
  const elk = new ELK();
  const graph = {graph_json};
  const result = await elk.layout(graph);
  const offsetX = {build.offset_x}, offsetY = {build.offset_y};
  const nodes = result.children.map(n => ({{id: n.id, x: n.x + offsetX, y: n.y + offsetY}}));
  return {{nodes, edges: []}};
}}
"""


__all__ = [
    "ELK_ALGORITHMS",
    "ELK_CROSSING_MINS",
    "ELK_CYCLE_BREAKINGS",
    "ELK_DIRECTIONS",
    "ELK_NODE_PLACEMENTS",
    "ElkBuild",
    "build_boundary_arrow_patches",
    "build_edge_patches",
    "build_elk_graph",
    "build_node_patches",
    "build_subgraph_updates",
    "elk_run_js",
    "position_map",
    "resolve_selection",
    "writeback_positions",
]
