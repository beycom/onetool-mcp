"""Deterministic roadmap validation, replay, and order diagnostics."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

from .models import (
    ArchitectureWorkspace,
    CompleteState,
    ContributingHistory,
    EntityKind,
    NormalizedOperation,
    ResolvedState,
    Roadmap,
    Tombstone,
)
from .normalize import KIND_FIELDS, PARENT_FIELDS, normalize_change
from .result import Issue, IssueCollection, IssueIdentity


@dataclass(frozen=True)
class ReplayResult:
    """Roadmap replay outcome with warnings or blocking diagnostics."""

    issues: IssueCollection
    resolved: ResolvedState | None = None


@dataclass(frozen=True)
class RoadmapReplayTimeline:
    """One fully prepared roadmap replay shared by all endpoint resolutions."""

    roadmap_id: str
    ordered: tuple[Any, ...]
    results: dict[int, ReplayResult]
    initial_error: ReplayResult | None = None
    failure_order: int | None = None
    failure: ReplayResult | None = None

    def resolve(self, *, through: str | None = None, order: int | None = None) -> ReplayResult:
        """Resolve one endpoint without replaying or recomputing diagnostics."""
        if self.initial_error is not None:
            return self.initial_error
        if through is not None and order is not None:
            return ReplayResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.selection_conflict",
                            message="through and order are mutually exclusive",
                            roadmap=self.roadmap_id,
                        )
                    ]
                )
            )
        if through == "base" or order == 0:
            endpoint = 0
        elif through is not None:
            matching = next(
                (item for item in self.ordered if item.change == through), None
            )
            if matching is None:
                return ReplayResult(
                    issues=IssueCollection(
                        errors=[
                            _issue(
                                code="arch.unknown_roadmap_endpoint",
                                message=(
                                    f"Change '{through}' is not on roadmap "
                                    f"'{self.roadmap_id}'"
                                ),
                                roadmap=self.roadmap_id,
                            )
                        ]
                    )
                )
            endpoint = matching.order
        elif order is not None:
            endpoint = order
        else:
            endpoint = self.ordered[-1].order if self.ordered else 0
        if endpoint < 0 or endpoint > len(self.ordered):
            return ReplayResult(
                issues=IssueCollection(
                    errors=[
                        _issue(
                            code="arch.roadmap_order_out_of_bounds",
                            message=(
                                f"Order {endpoint} is outside roadmap "
                                f"'{self.roadmap_id}'"
                            ),
                            roadmap=self.roadmap_id,
                            order=endpoint,
                        )
                    ]
                )
            )
        if self.failure_order is not None and endpoint >= self.failure_order:
            assert self.failure is not None
            return self.failure
        return self.results[endpoint]


def _issue(
    *, code: str, message: str, roadmap: str | None = None, order: int | None = None
) -> Issue:
    return Issue(
        code=code,
        severity="error",
        message=message,
        identity=IssueIdentity(roadmap=roadmap, order=order),
    )


def validate_roadmap(*, workspace: ArchitectureWorkspace, roadmap: Roadmap) -> IssueCollection:
    """Validate known changes and contiguous positive orders without rewriting order."""
    errors: list[Issue] = []
    state_ids = {state.id for state in workspace.states}
    if roadmap.base not in state_ids:
        errors.append(
            _issue(
                code="arch.unknown_roadmap_base",
                message=f"Roadmap '{roadmap.id}' references unknown base '{roadmap.base}'",
                roadmap=roadmap.id,
            )
        )
    change_ids = {change.id for change in workspace.changes}
    orders = [item.order for item in roadmap.items]
    for item in roadmap.items:
        if item.change not in change_ids:
            errors.append(
                _issue(
                    code="arch.unknown_roadmap_change",
                    message=f"Roadmap '{roadmap.id}' references unknown change '{item.change}'",
                    roadmap=roadmap.id,
                    order=item.order,
                )
            )
    if len(set(orders)) != len(orders):
        errors.append(
            _issue(
                code="arch.duplicate_roadmap_order",
                message=f"Roadmap '{roadmap.id}' contains duplicate orders",
                roadmap=roadmap.id,
            )
        )
    expected = list(range(1, len(orders) + 1))
    if sorted(orders) != expected:
        errors.append(
            _issue(
                code="arch.non_contiguous_roadmap_orders",
                message=(
                    f"Roadmap '{roadmap.id}' orders must be contiguous from 1; "
                    f"received {sorted(orders)}"
                ),
                roadmap=roadmap.id,
            )
        )
    orders_by_change = {item.change: item.order for item in roadmap.items}
    changes = {change.id: change for change in workspace.changes}
    for item in roadmap.items:
        change = changes.get(item.change)
        if change is None:
            continue
        for dependency in change.depends_on:
            dependency_order = orders_by_change.get(dependency)
            if dependency_order is None:
                errors.append(
                    _issue(
                        code="arch.missing_dependency",
                        message=(
                            f"Change '{change.id}' requires '{dependency}', which is not on "
                            f"roadmap '{roadmap.id}'"
                        ),
                        roadmap=roadmap.id,
                        order=item.order,
                    )
                )
            elif dependency_order >= item.order:
                errors.append(
                    Issue(
                        code="arch.invalid_dependency_order",
                        severity="error",
                        message=(
                            f"Change '{change.id}' requires '{dependency}' at an earlier "
                            "roadmap order"
                        ),
                        identity=IssueIdentity(
                            roadmap=roadmap.id,
                            order=item.order,
                            change=change.id,
                        ),
                        details={
                            "dependency": dependency,
                            "dependency_order": dependency_order,
                            "suggested_order": f"apply {dependency} before {change.id}",
                        },
                    )
                )
    return IssueCollection(errors=errors)


def _entity_lists(state: CompleteState) -> dict[EntityKind, list[dict[str, Any]]]:
    return {
        kind: [
            item.model_dump(mode="json", exclude_none=True)
            for item in cast("list[Any]", getattr(state, field))
        ]
        for kind, field in KIND_FIELDS.items()
    }


def apply_operations(
    *, state: CompleteState, operations: list[NormalizedOperation], output_state_id: str
) -> tuple[CompleteState, list[Tombstone]]:
    """Apply validated normalized operations to a complete state."""
    lists = _entity_lists(state)
    tombstones: list[Tombstone] = []

    def locate(kind: EntityKind, entity_id: str) -> tuple[int, dict[str, Any]] | None:
        for index, entity in enumerate(lists[kind]):
            if entity["id"] == entity_id:
                return index, entity
        return None

    for operation in operations:
        located = locate(operation.entity_kind, operation.entity_id)
        if operation.kind == "add":
            if located is not None:
                raise ValueError(
                    f"Cannot add existing {operation.entity_kind} '{operation.entity_id}'"
                )
            added = {"id": operation.entity_id, **deepcopy(operation.values)}
            if operation.source is not None:
                added["source"] = operation.source.model_dump(mode="json", exclude_none=True)
            lists[operation.entity_kind].append(added)
            continue
        if located is None:
            raise ValueError(
                f"Cannot {operation.kind} missing {operation.entity_kind} '{operation.entity_id}'"
            )
        index, entity = located
        if operation.kind == "modify":
            entity.update(deepcopy(operation.values))
            for field in operation.unset:
                entity.pop(field, None)
        elif operation.kind == "move":
            parent_field = PARENT_FIELDS[operation.entity_kind]
            entity[parent_field] = operation.to_parent
        elif operation.kind == "remove":
            removed = lists[operation.entity_kind].pop(index)
            tombstones.append(
                Tombstone(
                    entity_kind=operation.entity_kind,
                    entity_id=operation.entity_id,
                    value=removed,
                    removed_by=operation.change_id,
                    operation_id=operation.id,
                    source=operation.source,
                )
            )

    payload = state.model_dump(mode="json", exclude_none=True)
    payload["id"] = output_state_id
    for kind, field in KIND_FIELDS.items():
        payload[field] = sorted(lists[kind], key=lambda entity: str(entity["id"]))
    return CompleteState.model_validate(payload), tombstones


def _state_fingerprint(state: CompleteState) -> str:
    payload = state.model_dump(mode="json", exclude={"id", "source"}, exclude_none=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _enrich_replay_issue(
    issue: Issue, *, roadmap: Roadmap, order: int, future_additions: dict[str, str]
) -> Issue:
    identity = issue.identity.model_copy(update={"roadmap": roadmap.id, "order": order})
    details = dict(issue.details)
    entity_id = issue.identity.entity or issue.identity.interface
    if issue.code in {"arch.modify_before_add", "arch.remove_before_add"} and entity_id:
        dependency = future_additions.get(entity_id)
        if dependency is not None:
            details["suggested_dependency"] = dependency
            details["suggested_order"] = f"apply {dependency} before {issue.identity.change}"
    return issue.model_copy(update={"identity": identity, "details": details})


def _future_additions(
    *, workspace: ArchitectureWorkspace, roadmap: Roadmap, after_order: int
) -> dict[str, str]:
    changes = {change.id: change for change in workspace.changes}
    additions: dict[str, str] = {}
    for item in roadmap.items:
        if item.order <= after_order:
            continue
        change = changes.get(item.change)
        if change is None:
            continue
        for patches in (
            change.patches.systems,
            change.patches.applications,
            change.patches.components,
            change.patches.interfaces,
            change.patches.users,
            change.patches.relationships,
        ):
            for patch in patches:
                if patch.change_type == "added":
                    additions[patch.id] = change.id
    return additions


def _order_sensitive_warnings(
    *, workspace: ArchitectureWorkspace, roadmap: Roadmap, base: CompleteState
) -> list[Issue]:
    changes = {change.id: change for change in workspace.changes}
    warnings: list[Issue] = []
    ordered = sorted(roadmap.items, key=lambda item: item.order)
    current = base
    for left, right in pairwise(ordered):
        left_change = changes[left.change]
        right_change = changes[right.change]

        first_left = normalize_change(state=current, change=left_change)
        if first_left.issues.errors:
            break
        left_state, _ = apply_operations(
            state=current,
            operations=first_left.change.operations,
            output_state_id=current.id,
        )
        then_right = normalize_change(state=left_state, change=right_change)
        if then_right.issues.errors:
            current = left_state
            continue
        authored_state, _ = apply_operations(
            state=left_state,
            operations=then_right.change.operations,
            output_state_id=current.id,
        )

        first_right = normalize_change(state=current, change=right_change)
        if not first_right.issues.errors:
            right_state, _ = apply_operations(
                state=current,
                operations=first_right.change.operations,
                output_state_id=current.id,
            )
            then_left = normalize_change(state=right_state, change=left_change)
            if not then_left.issues.errors:
                reversed_state, _ = apply_operations(
                    state=right_state,
                    operations=then_left.change.operations,
                    output_state_id=current.id,
                )
                if _state_fingerprint(authored_state) != _state_fingerprint(reversed_state):
                    affected_fields = sorted(
                        {
                            field
                            for operation in (
                                *first_left.change.operations,
                                *then_right.change.operations,
                                *first_right.change.operations,
                                *then_left.change.operations,
                            )
                            for field in (*operation.values, *operation.unset)
                        }
                    )
                    warnings.append(
                        Issue(
                            code="arch.order_sensitive",
                            severity="warning",
                            message=(
                                f"Changes '{left.change}' and '{right.change}' are valid in either "
                                "order but resolve to different states"
                            ),
                            identity=IssueIdentity(
                                roadmap=roadmap.id,
                                order=left.order,
                                change=left.change,
                            ),
                            details={
                                "changes": [left.change, right.change],
                                "fields": affected_fields,
                            },
                        )
                    )
        current = authored_state
    return warnings


def prepare_roadmap_timeline(
    *, workspace: ArchitectureWorkspace, roadmap_id: str
) -> RoadmapReplayTimeline:
    """Replay a roadmap once and retain every valid endpoint."""
    roadmaps = {roadmap.id: roadmap for roadmap in workspace.roadmaps}
    roadmap = roadmaps.get(roadmap_id)
    if roadmap is None:
        error = ReplayResult(
            issues=IssueCollection(
                errors=[
                    _issue(
                        code="arch.unknown_roadmap",
                        message=f"Unknown roadmap '{roadmap_id}'",
                        roadmap=roadmap_id,
                    )
                ]
            )
        )
        return RoadmapReplayTimeline(
            roadmap_id=roadmap_id,
            ordered=(),
            results={},
            initial_error=error,
        )
    validation = validate_roadmap(workspace=workspace, roadmap=roadmap)
    if validation.errors:
        error = ReplayResult(issues=validation)
        return RoadmapReplayTimeline(
            roadmap_id=roadmap_id,
            ordered=tuple(sorted(roadmap.items, key=lambda item: item.order)),
            results={},
            initial_error=error,
        )

    ordered = sorted(roadmap.items, key=lambda item: item.order)
    states = {state.id: state for state in workspace.states}
    current = states[roadmap.base]
    changes = {change.id: change for change in workspace.changes}
    history: list[ContributingHistory] = []
    tombstones: list[Tombstone] = []
    warnings = _order_sensitive_warnings(workspace=workspace, roadmap=roadmap, base=current)
    results = {
        0: ReplayResult(
            resolved=ResolvedState(
                state=current.model_copy(update={"id": f"{roadmap.base}@{roadmap.id}:0"}),
                roadmap_id=roadmap.id,
                order=0,
                through="base",
                history=[],
                tombstones=[],
            ),
            issues=IssueCollection(warnings=warnings),
        )
    }
    for item in ordered:
        change = changes[item.change]
        normalized = normalize_change(state=current, change=change)
        if normalized.issues.errors:
            additions = _future_additions(
                workspace=workspace,
                roadmap=roadmap,
                after_order=item.order,
            )
            enriched = [
                _enrich_replay_issue(
                    issue,
                    roadmap=roadmap,
                    order=item.order,
                    future_additions=additions,
                )
                for issue in normalized.issues.errors
            ]
            failure = ReplayResult(
                issues=IssueCollection(errors=enriched, warnings=warnings)
            )
            return RoadmapReplayTimeline(
                roadmap_id=roadmap.id,
                ordered=tuple(ordered),
                results=results,
                failure_order=item.order,
                failure=failure,
            )
        current, removed = apply_operations(
            state=current,
            operations=normalized.change.operations,
            output_state_id=f"{roadmap.base}@{roadmap.id}:{item.order}",
        )
        tombstones.extend(removed)
        history.append(
            ContributingHistory(
                roadmap_id=roadmap.id,
                order=item.order,
                change_id=change.id,
                operations=normalized.change.operations,
            )
        )
        results[item.order] = ReplayResult(
            resolved=ResolvedState(
                state=current,
                roadmap_id=roadmap.id,
                order=item.order,
                through=item.change,
                history=list(history),
                tombstones=list(tombstones),
            ),
            issues=IssueCollection(warnings=warnings),
        )
    return RoadmapReplayTimeline(
        roadmap_id=roadmap.id,
        ordered=tuple(ordered),
        results=results,
    )


def replay_roadmap(
    *,
    workspace: ArchitectureWorkspace,
    roadmap_id: str,
    through: str | None = None,
    order: int | None = None,
    timeline: RoadmapReplayTimeline | None = None,
) -> ReplayResult:
    """Resolve a named roadmap endpoint from a prepared or new timeline."""
    prepared = timeline or prepare_roadmap_timeline(
        workspace=workspace,
        roadmap_id=roadmap_id,
    )
    if prepared.roadmap_id != roadmap_id:
        raise ValueError(
            f"Prepared roadmap '{prepared.roadmap_id}' cannot resolve '{roadmap_id}'"
        )
    return prepared.resolve(through=through, order=order)
