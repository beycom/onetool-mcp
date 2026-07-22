"""Snapshot preparation and deterministic local solution projections."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Literal, cast

from .models import (
    AbsentSelectedSystem,
    ArchitectureLevel,
    ArchitectureWorkspace,
    BoundaryInterface,
    CollapsedInterface,
    PreparedSolutionSnapshots,
    ProjectionDiagnostic,
    SolutionProjection,
    SystemSetSelector,
    ViewGraph,
    ViewGraphEdge,
    ViewGraphNode,
    ViewSelection,
)
from .replay import RoadmapReplayTimeline, prepare_roadmap_timeline
from .selection import selection_identity
from .selectors import SelectorError, roadmap_selection_indexes, systems_for_selector
from .viewgraph import resolve_view_graph

_PROJECTION_SCHEMA_VERSION = "solution-projection-2"
_RENDERER_ADAPTER_VERSION = "likec4-adapter-1"
_LAYOUT_SCHEMA_VERSION = "solution-layout-1"


class SolutionProjectionError(ValueError):
    """Raised when a snapshot or selector cannot be resolved."""


def _stable_hash(value: str) -> str:
    result = 2_166_136_261
    for character in value:
        result ^= ord(character)
        result = (result * 16_777_619) & 0xFFFFFFFF
    return f"{result:08x}"


def prepare_solution_snapshots(
    *,
    workspace: ArchitectureWorkspace,
    roadmap_id: str,
    replay_timeline: RoadmapReplayTimeline | None = None,
) -> PreparedSolutionSnapshots:
    """Precompute validated full graphs and indexes, but no projection layouts."""
    roadmap = next((item for item in workspace.roadmaps if item.id == roadmap_id), None)
    if roadmap is None:
        raise SolutionProjectionError(f"Unknown roadmap '{roadmap_id}'")
    orders = [
        0,
        *(item.order for item in sorted(roadmap.items, key=lambda item: item.order)),
    ]
    snapshots: dict[str, ViewGraph] = {}
    unavailable: list[int] = []
    timeline = replay_timeline or prepare_roadmap_timeline(
        workspace=workspace,
        roadmap_id=roadmap_id,
    )
    for order in orders:
        selection: dict[str, object] = {"roadmap": roadmap_id, "order": order}
        if order > 0:
            selection["compare_from"] = order - 1
        resolved = resolve_view_graph(
            workspace=workspace,
            value=selection,
            replay_timeline=timeline,
        )
        if resolved.graph is None or resolved.issues.errors:
            unavailable.append(order)
            continue
        key = str(order)
        snapshots[key] = resolved.graph
    roadmap_indexes = roadmap_selection_indexes(
        workspace=workspace,
        roadmap_id=roadmap_id,
        timeline=timeline,
    )
    presence: dict[str, list[int]] = defaultdict(list)
    for key, graph in snapshots.items():
        for node in graph.nodes:
            if node.entity_kind == "system" and not node.tombstone and not node.future:
                presence[node.id].append(int(key))
    return PreparedSolutionSnapshots(
        roadmap_id=roadmap_id,
        snapshots=snapshots,
        indexes={key: roadmap_indexes.model_copy(deep=True) for key in snapshots},
        system_presence={key: sorted(value) for key, value in sorted(presence.items())},
        unavailable_orders=unavailable,
    )


def _normalized_selector(selector: SystemSetSelector) -> SystemSetSelector:
    return selector.model_copy(
        update={
            key: sorted(set(values))
            for key, values in selector.model_dump(mode="python").items()
        }
    )


def _system_map(nodes: list[ViewGraphNode]) -> dict[str, str | None]:
    by_id = {node.id: node for node in nodes}
    result: dict[str, str | None] = {}
    for node in nodes:
        current: ViewGraphNode | None = node
        seen: set[str] = set()
        while current is not None and current.entity_kind != "system":
            if current.id in seen or current.parent is None:
                current = None
                break
            seen.add(current.id)
            current = by_id.get(current.parent)
        result[node.id] = current.id if current is not None else None
    return result


def _system_distances(
    *, graph: ViewGraph, selected: set[str], depth: int, systems: dict[str, str | None]
) -> dict[str, int]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.entity_kind != "interface":
            continue
        source = systems.get(edge.source_id)
        target = systems.get(edge.target_id)
        if source is None or target is None or source == target:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
    distances = dict.fromkeys(selected, 0)
    included = set(distances)
    frontier = set(selected)
    for hop in range(1, depth + 1):
        frontier = {
            neighbor for item in frontier for neighbor in adjacency[item]
        } - included
        included.update(frontier)
        distances.update(dict.fromkeys(frontier, hop))
    return distances


def _level_endpoint(
    *, endpoint: str, level: ArchitectureLevel, nodes: dict[str, ViewGraphNode]
) -> str | None:
    current = nodes.get(endpoint)
    while current is not None:
        if level == "component" or current.entity_kind == "system":
            return current.id
        if level == "application" and current.entity_kind == "application":
            return current.id
        current = nodes.get(current.parent) if current.parent else None
    return None


def solution_projection_cache_key(
    *,
    snapshot_id: str,
    model_id: str,
    selector: SystemSetSelector,
    depth: int,
    level: ArchitectureLevel,
    theme: str,
) -> str:
    """Return the stable cache identity; coloring is deliberately excluded."""
    payload = {
        "snapshot": snapshot_id,
        "model": model_id,
        "selector": {
            key: sorted(set(values))
            for key, values in selector.model_dump(mode="json").items()
        },
        "depth": depth,
        "level": level,
        "theme": theme,
        "versions": {
            "projection": _PROJECTION_SCHEMA_VERSION,
            "renderer": _RENDERER_ADAPTER_VERSION,
            "layout": _LAYOUT_SCHEMA_VERSION,
        },
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def project_solution(
    *,
    prepared: PreparedSolutionSnapshots,
    order: int,
    selector: SystemSetSelector | dict[str, object] | None = None,
    interface_depth: int = 0,
    level: ArchitectureLevel = "system",
    selection: ViewSelection | None = None,
) -> SolutionProjection:
    """Derive one projection from a prepared snapshot without resolving the roadmap again."""
    key = str(order)
    graph = prepared.snapshots.get(key)
    indexes = prepared.indexes.get(key)
    if graph is None or indexes is None:
        raise SolutionProjectionError(
            f"Roadmap '{prepared.roadmap_id}' order {order} is unavailable"
        )
    if interface_depth < 0:
        raise SolutionProjectionError("interface_depth must be at least zero")
    resolved_selector = _normalized_selector(
        selector
        if isinstance(selector, SystemSetSelector)
        else SystemSetSelector.model_validate(selector or {})
    )
    try:
        selected = systems_for_selector(selector=resolved_selector, indexes=indexes)
    except SelectorError as exc:
        raise SolutionProjectionError(str(exc)) from exc
    system_by_node = _system_map(graph.nodes)
    distances = _system_distances(
        graph=graph,
        selected=selected,
        depth=interface_depth,
        systems=system_by_node,
    )
    included = set(distances)
    present_systems = {
        node.id
        for node in graph.nodes
        if node.entity_kind == "system" and not node.tombstone and not node.future
    }
    absent_systems: list[AbsentSelectedSystem] = []
    for system_id in sorted(selected - present_systems):
        presence = prepared.system_presence.get(system_id, [])
        if presence and order < min(presence):
            state = "not_yet_present"
        elif presence and order > max(presence):
            state = "no_longer_present"
        else:
            state = "not_present"
        absent_systems.append(
            AbsentSelectedSystem(
                system_id=system_id,
                state=cast(
                    "Literal['not_yet_present', 'no_longer_present', 'not_present']",
                    state,
                ),
            )
        )

    internal_edges: list[ViewGraphEdge] = []
    boundary: list[BoundaryInterface] = []
    diagnostics: list[ProjectionDiagnostic] = []
    graph_nodes = {node.id: node for node in graph.nodes}
    for edge in graph.edges:
        source_system = system_by_node.get(edge.source_id)
        target_system = system_by_node.get(edge.target_id)
        for endpoint_id, endpoint_system in (
            (edge.source_id, source_system),
            (edge.target_id, target_system),
        ):
            endpoint = graph_nodes.get(endpoint_id)
            if endpoint_system is None and (
                endpoint is None or endpoint.entity_kind != "user"
            ):
                diagnostics.append(
                    ProjectionDiagnostic(
                        code=(
                            "unresolved_interface_endpoint"
                            if edge.entity_kind == "interface"
                            else "unresolved_relationship_endpoint"
                        ),
                        message=(
                            f"{edge.entity_kind.title()} '{edge.id}' endpoint "
                            f"'{endpoint_id}' has no owning system"
                        ),
                        entity_id=edge.id,
                        endpoint_id=endpoint_id,
                    )
                )
        source_inside = source_system in included
        target_inside = target_system in included
        if source_inside and target_inside:
            internal_edges.append(edge)
        elif edge.entity_kind == "interface" and source_inside != target_inside:
            boundary.append(
                BoundaryInterface(
                    interface=edge,
                    inside_system=cast(
                        "str", source_system if source_inside else target_system
                    ),
                    inside_endpoint=edge.source_id if source_inside else edge.target_id,
                    outside_system=target_system if source_inside else source_system,
                    outside_endpoint=edge.target_id
                    if source_inside
                    else edge.source_id,
                )
            )

    allowed_kinds = {
        "system": {"system"},
        "application": {"system", "application"},
        "component": {"system", "application", "component"},
    }[level]
    projected_nodes = [
        node
        for node in graph.nodes
        if node.entity_kind in allowed_kinds and system_by_node.get(node.id) in included
    ]
    projected_by_id = {node.id: node for node in projected_nodes}
    children: dict[str, list[str]] = defaultdict(list)
    for node in projected_nodes:
        if node.parent is not None and node.parent in projected_by_id:
            children[node.parent].append(node.id)
    projected_nodes = [
        node.model_copy(update={"children": sorted(children[node.id])})
        for node in projected_nodes
    ]
    original_nodes = {node.id: node for node in graph.nodes}
    projected_relationships: list[ViewGraphEdge] = []
    projected_interfaces: dict[
        tuple[str, str, str, str | None, str, str], list[ViewGraphEdge]
    ] = defaultdict(list)
    collapsed: list[CollapsedInterface] = []
    for edge in internal_edges:
        source = _level_endpoint(
            endpoint=edge.source_id, level=level, nodes=original_nodes
        )
        target = _level_endpoint(
            endpoint=edge.target_id, level=level, nodes=original_nodes
        )
        if (
            source is None
            or target is None
            or source not in projected_by_id
            or target not in projected_by_id
        ):
            continue
        projected = edge.model_copy(update={"source_id": source, "target_id": target})
        if edge.entity_kind == "interface" and source == target:
            collapsed.append(CollapsedInterface(interface=edge, visible_node=source))
            continue
        if edge.entity_kind == "relationship":
            projected_relationships.append(projected)
            continue
        projected_interfaces[
            (
                source,
                target,
                edge.direction,
                edge.integration_type,
                edge.status,
                edge.context_status,
            )
        ].append(projected)

    projected_edges: list[ViewGraphEdge] = list(projected_relationships)
    for aggregate_key, members in sorted(projected_interfaces.items()):
        ordered = sorted(members, key=lambda item: item.id)
        if len(ordered) == 1:
            projected_edges.append(ordered[0])
            continue
        member_ids = [item.id for item in ordered]
        aggregate_identity = "|".join(
            [
                aggregate_key[0],
                aggregate_key[1],
                aggregate_key[2],
                aggregate_key[3] or "",
                aggregate_key[4],
                aggregate_key[5],
                *member_ids,
            ]
        )
        first = ordered[0]
        projected_edges.append(
            first.model_copy(
                update={
                    "id": f"aggregate-{_stable_hash(aggregate_identity)}",
                    "name": f"{len(ordered)} interfaces",
                    "description": None,
                    "interface_ids": member_ids,
                    "tags": sorted({tag for item in ordered for tag in item.tags}),
                    "related_changes": sorted(
                        {
                            change_id
                            for item in ordered
                            for change_id in item.related_changes
                        }
                    ),
                    "properties": {"aggregate_members": member_ids},
                }
            )
        )
    projected_edges.sort(key=lambda item: item.id)

    snapshot_id = f"{prepared.roadmap_id}@{order}"
    requested_selection = selection or graph.selection.selection
    projected_selection = requested_selection.model_copy(
        update={
            "system_set": resolved_selector,
            "interface_depth": interface_depth,
            "level": level,
        }
    )
    projected_selection_id = selection_identity(projected_selection)
    projected_graph = graph.model_copy(
        update={
            "id": f"solution-{projected_selection_id.removeprefix('selection-')}",
            "selection": graph.selection.model_copy(
                update={
                    "id": projected_selection_id,
                    "selection": projected_selection,
                }
            ),
            "nodes": projected_nodes,
            "containers": sorted(children),
            "edges": projected_edges,
        }
    )
    return SolutionProjection(
        cache_key=solution_projection_cache_key(
            snapshot_id=snapshot_id,
            model_id=graph.id,
            selector=resolved_selector,
            depth=interface_depth,
            level=level,
            theme=projected_selection.theme or "clean",
        ),
        snapshot_id=snapshot_id,
        selector=resolved_selector,
        selected_systems=sorted(selected),
        included_systems=sorted(included),
        system_distances={key: distances[key] for key in sorted(distances)},
        absent_systems=absent_systems,
        interface_depth=interface_depth,
        level=level,
        graph=projected_graph,
        internal_interfaces=[
            edge for edge in internal_edges if edge.entity_kind == "interface"
        ],
        boundary_interfaces=boundary,
        collapsed_interfaces=sorted(collapsed, key=lambda item: item.interface.id),
        diagnostics=sorted(
            diagnostics,
            key=lambda item: (item.entity_id, item.endpoint_id, item.code),
        ),
    )
