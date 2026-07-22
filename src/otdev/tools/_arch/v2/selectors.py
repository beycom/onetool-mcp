"""Canonical roadmap-wide browse and system-set selector resolution."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .impact import derive_system_impacts
from .models import SolutionSelectionIndexes, SystemSetSelector

if TYPE_CHECKING:
    from .models import (
        ArchitectureWorkspace,
        BrowseKind,
        CompleteState,
        SystemImpactReason,
        ViewSelection,
    )
    from .replay import RoadmapReplayTimeline


class SelectorError(ValueError):
    """Raised when a canonical system-set selector cannot be resolved."""


_BROWSE_SELECTOR_FIELD: dict[BrowseKind, str] = {
    "system": "systems",
    "system_group": "system_groups",
    "change": "changes",
    "change_group": "change_groups",
    "tag": "tags",
}


def canonicalize_selection_subject(selection: ViewSelection) -> ViewSelection:
    """Union a browse subject into the canonical system-set selector."""
    values = {
        key: sorted(set(items))
        for key, items in selection.system_set.model_dump(mode="python").items()
    }
    if selection.subject is not None:
        assert selection.browse_by is not None
        field = _BROWSE_SELECTOR_FIELD[selection.browse_by]
        values[field] = sorted({*values[field], selection.subject})
    return selection.model_copy(
        update={"system_set": SystemSetSelector.model_validate(values)}
    )


def _sorted_index(values: dict[str, set[str]]) -> dict[str, list[str]]:
    return {key: sorted(items) for key, items in sorted(values.items())}


def _state_selector_values(
    states: list[CompleteState],
) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    systems: set[str] = set()
    system_groups: dict[str, set[str]] = defaultdict(set)
    tags: dict[str, set[str]] = defaultdict(set)
    for state in states:
        for system in state.systems:
            systems.add(system.id)
            for group in system.group:
                system_groups[group].add(system.id)
            for tag in system.tags:
                tags[tag].add(system.id)
    return systems, system_groups, tags


def state_selection_indexes(*, state: CompleteState) -> SolutionSelectionIndexes:
    """Build selector indexes for one authored state."""
    systems, system_groups, tags = _state_selector_values([state])
    return SolutionSelectionIndexes(
        systems=sorted(systems),
        system_groups=_sorted_index(system_groups),
        tags=_sorted_index(tags),
    )


def roadmap_selection_indexes(
    *,
    workspace: ArchitectureWorkspace,
    roadmap_id: str,
    timeline: RoadmapReplayTimeline,
) -> SolutionSelectionIndexes:
    """Build one roadmap-wide selector index from every prepared replay state."""
    if timeline.roadmap_id != roadmap_id:
        raise ValueError(
            f"Prepared roadmap '{timeline.roadmap_id}' cannot index '{roadmap_id}'"
        )
    roadmap = next((item for item in workspace.roadmaps if item.id == roadmap_id), None)
    if roadmap is None:
        raise SelectorError(f"Unknown roadmap '{roadmap_id}'")

    resolved_by_order = {
        order: result.resolved
        for order, result in timeline.results.items()
        if result.resolved is not None
    }
    states = [resolved.state for _, resolved in sorted(resolved_by_order.items())]
    systems, system_groups, tags = _state_selector_values(states)
    changes: dict[str, list[str]] = {}
    change_impacts: dict[str, dict[str, list[SystemImpactReason]]] = {}
    change_groups: dict[str, set[str]] = defaultdict(set)
    change_group_impacts: dict[str, dict[str, list[SystemImpactReason]]] = defaultdict(
        lambda: defaultdict(list)
    )
    change_by_id = {change.id: change for change in workspace.changes}
    previous_order = 0
    for item in sorted(roadmap.items, key=lambda value: value.order):
        before = resolved_by_order.get(previous_order)
        after = resolved_by_order.get(item.order)
        if before is None or after is None:
            previous_order = item.order
            continue
        history = next(
            (entry for entry in after.history if entry.change_id == item.change),
            None,
        )
        if history is None:
            previous_order = item.order
            continue
        impacts = derive_system_impacts(
            before=before.state,
            after=after.state,
            operations=history.operations,
        )
        changes[item.change] = sorted(impacts)
        change_impacts[item.change] = impacts
        systems.update(impacts)
        change = change_by_id[item.change]
        for group in change.group:
            change_groups[group].update(impacts)
            for system_id, reasons in impacts.items():
                change_group_impacts[group][system_id].extend(reasons)
        previous_order = item.order

    normalized_group_impacts: dict[str, dict[str, list[SystemImpactReason]]] = {}
    for group, impacts in sorted(change_group_impacts.items()):
        normalized_group_impacts[group] = {}
        for system_id, reasons in sorted(impacts.items()):
            unique = {
                (
                    reason.code,
                    reason.change_id,
                    reason.operation_id,
                    reason.entity_kind,
                    reason.entity_id,
                ): reason
                for reason in reasons
            }
            normalized_group_impacts[group][system_id] = [
                unique[key] for key in sorted(unique)
            ]

    return SolutionSelectionIndexes(
        systems=sorted(systems),
        system_groups=_sorted_index(system_groups),
        changes={key: changes[key] for key in sorted(changes)},
        change_groups=_sorted_index(change_groups),
        change_impacts={key: change_impacts[key] for key in sorted(change_impacts)},
        change_group_impacts=normalized_group_impacts,
        tags=_sorted_index(tags),
    )


def systems_for_selector(
    *, selector: SystemSetSelector, indexes: SolutionSelectionIndexes
) -> set[str]:
    """Validate and union every canonical selector axis into system identities."""
    requested = any(selector.model_dump(mode="python").values())
    lookups = (
        ("systems", selector.systems, set(indexes.systems)),
        ("system groups", selector.system_groups, set(indexes.system_groups)),
        ("changes", selector.changes, set(indexes.changes)),
        ("change groups", selector.change_groups, set(indexes.change_groups)),
        ("tags", selector.tags, set(indexes.tags)),
    )
    for label, values, known in lookups:
        unknown = sorted(set(values) - known)
        if unknown:
            raise SelectorError(f"Unknown {label}: {unknown}")
    selected = set(selector.systems)
    for value in selector.system_groups:
        selected.update(indexes.system_groups[value])
    for value in selector.changes:
        selected.update(indexes.changes[value])
    for value in selector.change_groups:
        selected.update(indexes.change_groups[value])
    for value in selector.tags:
        selected.update(indexes.tags[value])
    return selected if requested else set(indexes.systems)
