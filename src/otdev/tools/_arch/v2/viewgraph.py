"""Shared selection resolution and deterministic renderer-neutral ViewGraph construction."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, cast

from .compare import compare_states
from .impact import derive_system_impacts
from .models import (
    ArchitectureWorkspace,
    ChangeBrowseEntry,
    CompleteState,
    ContextStatus,
    EntityKind,
    NormalizedOperation,
    PreparedViewGraphs,
    ResolvedSelection,
    SelectionInput,
    SourceLocation,
    StateComparison,
    Tombstone,
    ViewGraph,
    ViewGraphEdge,
    ViewGraphNode,
    ViewSelection,
)
from .normalize import KIND_FIELDS, PARENT_FIELDS
from .replay import (
    ReplayResult,
    RoadmapReplayTimeline,
    apply_operations,
    prepare_roadmap_timeline,
    replay_roadmap,
)
from .result import Issue, IssueCollection, IssueIdentity
from .selection import SelectionError, resolve_selection_input, selection_identity
from .selectors import (
    SelectorError,
    canonicalize_selection_subject,
    roadmap_selection_indexes,
    state_selection_indexes,
    systems_for_selector,
)


@dataclass(frozen=True)
class ViewResolutionResult:
    """Resolved ViewGraph or blocking source-complete diagnostics."""

    issues: IssueCollection
    graph: ViewGraph | None = None


def _issue(
    *, code: str, message: str, selection: ViewSelection, details: dict[str, Any] | None = None
) -> Issue:
    return Issue(
        code=code,
        severity="error",
        message=message,
        identity=IssueIdentity(
            roadmap=selection.roadmap,
            order=selection.order,
            state=selection.state,
        ),
        details=details or {},
    )


def normalize_selection(
    *, workspace: ArchitectureWorkspace, value: SelectionInput | None
) -> ViewSelection:
    """Apply default/saved/ad hoc precedence and all derived selection defaults."""
    saved = {view.id: view for view in workspace.views}
    selection = resolve_selection_input(
        value=value,
        saved_views=saved,
        defaults=workspace.presentation.default_selection,
    )
    updates: dict[str, Any] = {}
    if selection.state is None and selection.roadmap is None:
        if workspace.presentation.default_roadmap is None:
            if len(workspace.states) != 1:
                raise SelectionError(
                    "A state or roadmap is required when no default roadmap is configured"
                )
            updates["state"] = workspace.states[0].id
        else:
            updates["roadmap"] = workspace.presentation.default_roadmap
    change_ids = {change.id for change in workspace.changes}
    if selection.browse_by is None:
        updates["browse_by"] = (
            "change" if selection.focus or selection.subject in change_ids else "system"
        )
    browse_by = cast("str", updates.get("browse_by", selection.browse_by))
    focus = list(selection.focus)
    if selection.visibility is None:
        updates["visibility"] = (
            "changes_with_context" if browse_by == "change" or focus else "all"
        )
    if selection.theme is None:
        updates["theme"] = workspace.presentation.default_theme
    return canonicalize_selection_subject(selection.model_copy(update=updates))


def _state_entities(state: CompleteState) -> dict[EntityKind, dict[str, dict[str, Any]]]:
    return {
        kind: {
            item.id: item.model_dump(mode="json", exclude_none=True)
            for item in cast("list[Any]", getattr(state, field))
        }
        for kind, field in KIND_FIELDS.items()
    }


def _endpoint_for_compare(
    *,
    workspace: ArchitectureWorkspace,
    selection: ViewSelection,
    resolved: ReplayResult,
    replay_timeline: RoadmapReplayTimeline,
) -> tuple[CompleteState | None, list[Any], list[Tombstone], Issue | None]:
    compare_from = selection.compare_from
    if compare_from is None:
        return None, [], [], None
    assert selection.roadmap is not None
    assert resolved.resolved is not None
    endpoint = resolved.resolved.order
    roadmap = next(item for item in workspace.roadmaps if item.id == selection.roadmap)
    orders = {item.change: item.order for item in roadmap.items}
    origin_order: int | None = None
    origin_state: CompleteState | None = None
    if compare_from == "base":
        origin_order = 0
    elif isinstance(compare_from, int):
        origin_order = compare_from
    elif compare_from in orders:
        origin_order = orders[compare_from]
    else:
        origin_state = next(
            (state for state in workspace.states if state.id == compare_from),
            None,
        )
        if origin_state is None:
            return (
                None,
                [],
                [],
                _issue(
                    code="arch.unknown_comparison_origin",
                    message=f"Unknown comparison origin '{compare_from}'",
                    selection=selection,
                ),
            )
    if origin_order is not None:
        if origin_order > endpoint:
            return (
                None,
                [],
                [],
                _issue(
                    code="arch.comparison_after_endpoint",
                    message=(
                        f"Comparison origin {compare_from!r} is after resolved order {endpoint}"
                    ),
                    selection=selection,
                    details={"compare_from": compare_from, "endpoint": endpoint},
                ),
            )
        origin = replay_roadmap(
            workspace=workspace,
            roadmap_id=selection.roadmap,
            order=origin_order,
            timeline=replay_timeline,
        )
        if origin.resolved is None:
            return None, [], [], origin.issues.errors[0]
        origin_state = origin.resolved.state
        history = [
            item for item in resolved.resolved.history if item.order > origin_order
        ]
    else:
        history = list(resolved.resolved.history)
    contributing_ids = {item.change_id for item in history}
    tombstones = [
        item for item in resolved.resolved.tombstones if item.removed_by in contributing_ids
    ]
    return origin_state, history, tombstones, None


def _status_operations(
    *, comparison: StateComparison | None, focus_operations: list[NormalizedOperation]
) -> tuple[dict[tuple[EntityKind, str], ContextStatus], dict[str, set[str]]]:
    statuses: dict[tuple[EntityKind, str], ContextStatus] = {}
    related: dict[str, set[str]] = defaultdict(set)
    operations = [
        *(comparison.change.operations if comparison is not None else []),
        *focus_operations,
    ]
    rank: dict[ContextStatus, int] = {
        "out_of_scope": 0,
        "no_change": 1,
        "change": 2,
        "new": 3,
        "future": 4,
        "decommission": 5,
    }
    for operation in operations:
        status = cast(
            "ContextStatus",
            {
                "add": "new",
                "modify": "change",
                "move": "change",
                "remove": "decommission",
            }[operation.kind],
        )
        key = (operation.entity_kind, operation.entity_id)
        if rank[status] >= rank[statuses.get(key, "no_change")]:
            statuses[key] = status
        related[operation.entity_id].add(operation.change_id)
    return statuses, related


def _future_context(
    *,
    workspace: ArchitectureWorkspace,
    selection: ViewSelection,
    endpoint: int,
    replay_timeline: RoadmapReplayTimeline | None,
) -> tuple[dict[EntityKind, dict[str, dict[str, Any]]], list[NormalizedOperation]]:
    empty: dict[EntityKind, dict[str, dict[str, Any]]] = {
        kind: {} for kind in KIND_FIELDS
    }
    if not selection.include_future or selection.roadmap is None:
        return empty, []
    final = replay_roadmap(
        workspace=workspace,
        roadmap_id=selection.roadmap,
        timeline=replay_timeline,
    )
    if final.resolved is None:
        return empty, []
    selected = replay_roadmap(
        workspace=workspace,
        roadmap_id=selection.roadmap,
        order=endpoint,
        timeline=replay_timeline,
    )
    if selected.resolved is None:
        return empty, []
    selected_entities = _state_entities(selected.resolved.state)
    final_entities = _state_entities(final.resolved.state)
    future = {
        kind: {
            entity_id: entity
            for entity_id, entity in final_entities[kind].items()
            if entity_id not in selected_entities[kind]
        }
        for kind in KIND_FIELDS
    }
    operations = [
        operation
        for item in final.resolved.history
        if item.order > endpoint
        for operation in item.operations
    ]
    return future, operations


def _source(value: dict[str, Any], fallback: SourceLocation | None = None) -> SourceLocation | None:
    if fallback is not None:
        return fallback
    raw = value.get("source")
    return SourceLocation.model_validate(raw) if isinstance(raw, dict) else None


def _transition_status(status: ContextStatus) -> str:
    return {
        "new": "Added",
        "change": "Changed",
        "decommission": "Removed",
    }.get(status, "No Change")


def _node_from_value(
    *,
    kind: EntityKind,
    value: dict[str, Any],
    status: ContextStatus,
    related: set[str],
    tombstone: bool = False,
    future: bool = False,
    source: SourceLocation | None = None,
) -> ViewGraphNode:
    parent_field = PARENT_FIELDS.get(kind)
    return ViewGraphNode(
        id=str(value["id"]),
        entity_kind=kind,
        name=str(value.get("name", value["id"])),
        parent=str(value[parent_field]) if parent_field and value.get(parent_field) else None,
        status=cast("Any", _transition_status(status)),
        context_status=status,
        tombstone=tombstone,
        future=future,
        tags=cast("list[str]", value.get("tags", [])),
        groups=cast("list[str]", value.get("group", [])),
        icon=cast("str | None", value.get("icon")),
        style=value.get("style"),
        related_changes=sorted(related),
        source=_source(value, source),
        properties=cast("dict[str, Any]", value.get("properties", {})),
    )


def _edge_from_value(
    *,
    kind: EntityKind,
    value: dict[str, Any],
    status: ContextStatus,
    related: set[str],
    tombstone: bool = False,
    future: bool = False,
    source: SourceLocation | None = None,
) -> ViewGraphEdge:
    if kind == "interface":
        source_id = str(value["provider"])
        target_id = str(value["consumer"])
    else:
        source_id = str(value["source_id"])
        target_id = str(value["target_id"])
    entity_id = str(value["id"])
    return ViewGraphEdge(
        id=entity_id,
        entity_kind=cast("Any", kind),
        name=str(value.get("name", entity_id)),
        description=cast("str | None", value.get("description")),
        source_id=source_id,
        target_id=target_id,
        direction=cast("Any", value.get("direction", "forward")),
        status=cast("Any", _transition_status(status)),
        context_status=status,
        tombstone=tombstone,
        future=future,
        tags=cast("list[str]", value.get("tags", [])),
        integration_type=cast("str | None", value.get("type")),
        interface_ids=[entity_id] if kind == "interface" else [],
        related_changes=sorted(related),
        source=_source(value, source),
        properties=cast("dict[str, Any]", value.get("properties", {})),
    )


def _ancestors(node_id: str, nodes: dict[str, ViewGraphNode]) -> set[str]:
    result: set[str] = set()
    current = nodes.get(node_id)
    while current is not None and current.parent is not None and current.parent not in result:
        result.add(current.parent)
        current = nodes.get(current.parent)
    return result


def _filter_graph(
    *,
    nodes: dict[str, ViewGraphNode],
    edges: dict[str, ViewGraphEdge],
    selection: ViewSelection,
) -> tuple[list[ViewGraphNode], list[ViewGraphEdge]]:
    statuses = set(selection.display_statuses)
    primary = {
        node_id
        for node_id, node in nodes.items()
        if (not statuses or node.context_status in statuses)
        and node.context_status not in {"no_change", "out_of_scope"}
    }
    visibility = selection.visibility or "all"
    if visibility == "all":
        included = {
            node_id
            for node_id, node in nodes.items()
            if (not statuses or node.context_status in statuses)
            and node.context_status != "out_of_scope"
        }
    elif visibility == "changes_only":
        included = set(primary)
    else:
        included = set(primary)
        for node_id in tuple(primary):
            included.update(_ancestors(node_id, nodes))
        for edge in edges.values():
            if edge.context_status not in {"no_change", "out_of_scope"} or (
                edge.source_id in included or edge.target_id in included
            ):
                included.update({edge.source_id, edge.target_id})
                included.update(_ancestors(edge.source_id, nodes))
                included.update(_ancestors(edge.target_id, nodes))

    included_edges = [
        edge
        for edge in edges.values()
        if edge.source_id in included
        and edge.target_id in included
        and (
            not statuses
            or edge.context_status in statuses
            or visibility == "changes_with_context"
        )
    ]
    output_nodes = []
    for node_id in sorted(included):
        node = nodes[node_id]
        children = sorted(
            child.id for child in nodes.values() if child.parent == node.id and child.id in included
        )
        parent = node.parent if node.parent in included else None
        output_nodes.append(node.model_copy(update={"children": children, "parent": parent}))
    return output_nodes, sorted(included_edges, key=lambda edge: edge.id)


def _change_entries(
    *, workspace: ArchitectureWorkspace, roadmap_id: str, final: ReplayResult
) -> list[ChangeBrowseEntry]:
    roadmap = next(item for item in workspace.roadmaps if item.id == roadmap_id)
    changes = {change.id: change for change in workspace.changes}
    history = final.resolved.history if final.resolved else []
    base = next(state for state in workspace.states if state.id == roadmap.base)
    current = base
    impacts_by_change = {}
    operations_by_change = {}
    for history_item in history:
        after, _tombstones = apply_operations(
            state=current,
            operations=history_item.operations,
            output_state_id=current.id,
        )
        impacts_by_change[history_item.change_id] = derive_system_impacts(
            before=current,
            after=after,
            operations=history_item.operations,
        )
        operations_by_change[history_item.change_id] = history_item.operations
        current = after
    entries: list[ChangeBrowseEntry] = []
    for item in sorted(roadmap.items, key=lambda candidate: candidate.order):
        change = changes[item.change]
        operations = operations_by_change.get(change.id, [])
        impact_reasons = impacts_by_change.get(change.id, {})
        metadata = change.model_dump(
            mode="json",
            exclude={"id", "name", "patches", "source"},
            exclude_none=True,
        )
        counts = Counter(operation.kind for operation in operations)
        entries.append(
            ChangeBrowseEntry(
                id=change.id,
                name=change.name,
                order=item.order,
                metadata=metadata,
                affected_systems=sorted(impact_reasons),
                impact_reasons=impact_reasons,
                operation_counts=dict(counts),
                source=change.source,
            )
        )
    return entries


def resolve_view_graph(
    *,
    workspace: ArchitectureWorkspace,
    value: SelectionInput | None = None,
    replay_timeline: RoadmapReplayTimeline | None = None,
) -> ViewResolutionResult:
    """Resolve one saved/ad hoc selection into deterministic production ViewGraph data."""
    try:
        selection = normalize_selection(workspace=workspace, value=value)
    except (SelectionError, ValueError) as exc:
        fallback = ViewSelection()
        return ViewResolutionResult(
            issues=IssueCollection(
                errors=[
                    _issue(
                        code="arch.invalid_selection",
                        message=str(exc),
                        selection=fallback,
                    )
                ]
            )
        )
    warnings: list[Issue] = []
    comparison: StateComparison | None = None
    comparison_tombstones: list[Tombstone] = []
    focus_operations: list[NormalizedOperation] = []
    focus_overrides: list[NormalizedOperation] = []
    selected_history_operations: list[NormalizedOperation] = []
    roadmap_final: ReplayResult | None = None
    if selection.state is not None:
        state = next((item for item in workspace.states if item.id == selection.state), None)
        if state is None:
            return ViewResolutionResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.unknown_state",
                            message=f"Unknown state '{selection.state}'",
                            selection=selection,
                        )
                    ]
                )
            )
        endpoint = None
        through = None
    else:
        assert selection.roadmap is not None
        if replay_timeline is None:
            replay_timeline = prepare_roadmap_timeline(
                workspace=workspace,
                roadmap_id=selection.roadmap,
            )
        resolved = replay_roadmap(
            workspace=workspace,
            roadmap_id=selection.roadmap,
            through=selection.through,
            order=selection.order,
            timeline=replay_timeline,
        )
        if resolved.resolved is None:
            return ViewResolutionResult(issues=resolved.issues)
        warnings.extend(resolved.issues.warnings)
        state = resolved.resolved.state
        selected_history_operations = [
            operation
            for item in resolved.resolved.history
            for operation in item.operations
        ]
        endpoint = resolved.resolved.order
        through = resolved.resolved.through
        roadmap_final = replay_roadmap(
            workspace=workspace,
            roadmap_id=selection.roadmap,
            timeline=replay_timeline,
        )
        if roadmap_final.resolved is None:
            return ViewResolutionResult(issues=roadmap_final.issues)
        orders = {
            item.change_id: item.order for item in roadmap_final.resolved.history
        }
        unknown_focus = [change for change in selection.focus if change not in orders]
        if unknown_focus:
            return ViewResolutionResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.unknown_focus_change",
                            message=f"Focus changes are not on the selected roadmap: {unknown_focus}",
                            selection=selection,
                            details={"focus": unknown_focus},
                        )
                    ]
                )
            )
        future_focus = [change for change in selection.focus if orders[change] > endpoint]
        if future_focus and not selection.include_future:
            return ViewResolutionResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.future_focus_requires_context",
                            message=f"Focus changes occur after the selected endpoint: {future_focus}",
                            selection=selection,
                            details={"focus": future_focus, "endpoint": endpoint},
                        )
                    ]
                )
            )
        for item in roadmap_final.resolved.history:
            if item.change_id in selection.focus:
                focus_operations.extend(item.operations)
        focus_tombstones = [
            item
            for item in resolved.resolved.tombstones
            if item.removed_by in set(selection.focus)
        ]
        focused_keys = {
            (operation.entity_kind, operation.entity_id) for operation in focus_operations
        }
        focused_orders = {orders[change] for change in selection.focus}
        for item in roadmap_final.resolved.history:
            if focused_orders and item.order > min(focused_orders):
                focus_overrides.extend(
                    operation
                    for operation in item.operations
                    if (operation.entity_kind, operation.entity_id) in focused_keys
                    and operation.change_id not in selection.focus
                )
        origin, history, comparison_tombstones, error = _endpoint_for_compare(
            workspace=workspace,
            selection=selection,
            resolved=resolved,
            replay_timeline=replay_timeline,
        )
        if error is not None:
            return ViewResolutionResult(issues=IssueCollection(errors=[error]))
        if origin is not None:
            comparison = compare_states(
                base=origin,
                target=state,
                contributing_history=history,
            )
        tombstone_keys = {
            (item.entity_kind, item.entity_id) for item in comparison_tombstones
        }
        comparison_tombstones.extend(
            item
            for item in focus_tombstones
            if (item.entity_kind, item.entity_id) not in tombstone_keys
        )

    entities = _state_entities(state)
    future_entities, future_operations = _future_context(
        workspace=workspace,
        selection=selection,
        endpoint=endpoint or 0,
        replay_timeline=replay_timeline,
    )
    statuses, related = _status_operations(
        comparison=comparison,
        focus_operations=focus_operations,
    )
    for operation in future_operations:
        related[operation.entity_id].add(operation.change_id)
    for operation in selected_history_operations:
        related[operation.entity_id].add(operation.change_id)
    nodes: dict[str, ViewGraphNode] = {}
    edges: dict[str, ViewGraphEdge] = {}
    for kind, values in entities.items():
        for entity_id, entity in values.items():
            status = statuses.get((kind, entity_id), "no_change")
            if kind in {"interface", "relationship"}:
                edges[entity_id] = _edge_from_value(
                    kind=kind,
                    value=entity,
                    status=status,
                    related=related[entity_id],
                )
            else:
                nodes[entity_id] = _node_from_value(
                    kind=kind,
                    value=entity,
                    status=status,
                    related=related[entity_id],
                )
    for kind, values in future_entities.items():
        for entity_id, entity in values.items():
            if kind in {"interface", "relationship"}:
                edges[entity_id] = _edge_from_value(
                    kind=kind,
                    value=entity,
                    status="future",
                    related=related[entity_id],
                    future=True,
                )
            else:
                nodes[entity_id] = _node_from_value(
                    kind=kind,
                    value=entity,
                    status="future",
                    related=related[entity_id],
                    future=True,
                )
    for tombstone in comparison_tombstones:
        if tombstone.entity_kind in {"interface", "relationship"}:
            edges[tombstone.entity_id] = _edge_from_value(
                kind=tombstone.entity_kind,
                value=tombstone.value,
                status="decommission",
                related={tombstone.removed_by},
                tombstone=True,
                source=tombstone.source,
            )
        else:
            nodes[tombstone.entity_id] = _node_from_value(
                kind=tombstone.entity_kind,
                value=tombstone.value,
                status="decommission",
                related={tombstone.removed_by},
                tombstone=True,
                source=tombstone.source,
            )
    indexes = (
        roadmap_selection_indexes(
            workspace=workspace,
            roadmap_id=selection.roadmap,
            timeline=replay_timeline,
        )
        if selection.roadmap is not None and replay_timeline is not None
        else state_selection_indexes(state=state)
    )
    try:
        systems_for_selector(selector=selection.system_set, indexes=indexes)
    except SelectorError as exc:
        return ViewResolutionResult(
            issues=IssueCollection(
                errors=[
                    _issue(
                        code=(
                            "arch.inapplicable_subject"
                            if selection.subject is not None
                            else "arch.invalid_selection"
                        ),
                        message=str(exc),
                        selection=selection,
                    )
                ]
            )
        )

    filtered_nodes, filtered_edges = _filter_graph(
        nodes=nodes,
        edges=edges,
        selection=selection,
    )
    canonical_selection = (
        selection.model_copy(update={"through": None, "order": endpoint})
        if selection.roadmap is not None
        else selection
    )
    resolved_selection = ResolvedSelection(
        id=selection_identity(canonical_selection),
        selection=canonical_selection,
        state_id=state.id,
        roadmap_id=selection.roadmap,
        order=endpoint,
        through=through,
    )
    applicable_change_ids = set(selection.focus) | {
        operation.change_id for operation in selected_history_operations
    }
    applicable_diagrams = [
        diagram.id
        for diagram in workspace.diagrams
        if (not diagram.systems or set(diagram.systems) <= set(nodes))
        and (not diagram.changes or set(diagram.changes) <= applicable_change_ids)
    ]
    if selection.diagram is not None:
        known_diagrams = {diagram.id for diagram in workspace.diagrams}
        if selection.diagram not in known_diagrams:
            return ViewResolutionResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.unknown_diagram",
                            message=f"Unknown diagram '{selection.diagram}'",
                            selection=selection,
                        )
                    ]
                )
            )
        if selection.diagram not in applicable_diagrams:
            return ViewResolutionResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.inapplicable_diagram",
                            message=(
                                f"Diagram '{selection.diagram}' is unavailable for the "
                                "selected system/change context"
                            ),
                            selection=selection,
                        )
                    ]
                )
            )
    changes = (
        _change_entries(
            workspace=workspace,
            roadmap_id=selection.roadmap,
            final=roadmap_final,
        )
        if selection.roadmap is not None and roadmap_final is not None
        else []
    )
    graph = ViewGraph(
        id=f"viewgraph-{resolved_selection.id.removeprefix('selection-')}",
        selection=resolved_selection,
        resolved_state=state,
        nodes=filtered_nodes,
        containers=sorted(
            node.id
            for node in filtered_nodes
            if node.entity_kind in {"system", "application"}
        ),
        edges=filtered_edges,
        changes=changes,
        comparison=comparison,
        tombstones=comparison_tombstones,
        focus=selection.focus,
        focus_overrides=focus_overrides,
        diagram_ids=applicable_diagrams,
        hints={
            "projection": selection.projection,
            "level": selection.level,
            "diagram": selection.diagram,
            "theme": selection.theme,
            "visibility": selection.visibility,
        },
    )
    return ViewResolutionResult(
        graph=graph,
        issues=IssueCollection(warnings=warnings),
    )


def prepare_roadmap_viewgraphs(
    *,
    workspace: ArchitectureWorkspace,
    roadmap_id: str,
    orders: list[int] | None = None,
) -> tuple[PreparedViewGraphs, IssueCollection]:
    """Prepare base and included valid orders without any browser replay."""
    roadmap = next((item for item in workspace.roadmaps if item.id == roadmap_id), None)
    if roadmap is None:
        issue = Issue(
            code="arch.unknown_roadmap",
            severity="error",
            message=f"Unknown roadmap '{roadmap_id}'",
            identity=IssueIdentity(roadmap=roadmap_id),
        )
        return (
            PreparedViewGraphs(roadmap_id=roadmap_id, graphs={}),
            IssueCollection(errors=[issue]),
        )
    available = list(range(0, len(roadmap.items) + 1))
    included = available if orders is None else sorted(set(orders) & set(available))
    unavailable = sorted(set(available) - set(included))
    graphs: dict[str, ViewGraph] = {}
    errors: list[Issue] = []
    warnings: list[Issue] = []
    replay_timeline = prepare_roadmap_timeline(
        workspace=workspace,
        roadmap_id=roadmap_id,
    )
    for order in included:
        result = resolve_view_graph(
            workspace=workspace,
            value={"roadmap": roadmap_id, "order": order},
            replay_timeline=replay_timeline,
        )
        errors.extend(result.issues.errors)
        warnings.extend(result.issues.warnings)
        if result.graph is not None:
            graphs[str(order)] = result.graph
    return (
        PreparedViewGraphs(
            roadmap_id=roadmap_id,
            graphs=graphs,
            unavailable_orders=unavailable,
        ),
        IssueCollection(errors=errors, warnings=warnings),
    )
