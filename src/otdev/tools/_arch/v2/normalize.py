"""Format-independent sparse change normalization and precondition validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

if TYPE_CHECKING:
    from collections.abc import Iterable

from .models import (
    Change,
    CompleteState,
    EntityKind,
    NormalizedChange,
    NormalizedOperation,
    OperationPrecondition,
    PatchBase,
    SourceLocation,
    StrictModel,
)
from .result import Issue, IssueCollection, IssueIdentity

EntityData = dict[str, Any]
EntityIndex = dict[EntityKind, dict[str, EntityData]]
PlannedEntities = dict[EntityKind, set[str]]

KIND_FIELDS: dict[EntityKind, str] = {
    "system": "systems",
    "application": "applications",
    "component": "components",
    "interface": "interfaces",
    "user": "users",
    "relationship": "relationships",
}
PATCH_FIELDS: dict[EntityKind, str] = KIND_FIELDS
PARENT_FIELDS: dict[EntityKind, str] = {
    "application": "system",
    "component": "application",
}
REMOVAL_ORDER: dict[EntityKind, int] = {
    "interface": 0,
    "relationship": 1,
    "component": 2,
    "application": 3,
    "system": 4,
    "user": 5,
}
ENDPOINT_KINDS: tuple[EntityKind, ...] = ("system", "application", "component", "user")


class NormalizationResult(StrictModel):
    """Normalized operations plus source-complete issues."""

    change: NormalizedChange
    issues: IssueCollection = Field(default_factory=IssueCollection)


def state_index(state: CompleteState) -> EntityIndex:
    """Build a stable-ID index over every complete-state entity kind."""
    result: EntityIndex = {
        "system": {},
        "application": {},
        "component": {},
        "interface": {},
        "user": {},
        "relationship": {},
    }
    for kind, field in KIND_FIELDS.items():
        for entity in getattr(state, field):
            result[kind][entity.id] = entity.model_dump(
                mode="python", exclude_none=True
            )
    return result


def _patches(change: Change) -> Iterable[tuple[EntityKind, PatchBase]]:
    for kind, field in PATCH_FIELDS.items():
        for patch in getattr(change.patches, field):
            yield kind, patch


def _issue(
    *,
    code: str,
    message: str,
    change: Change,
    kind: EntityKind,
    entity_id: str,
    source: SourceLocation | None,
    details: dict[str, Any] | None = None,
) -> Issue:
    return Issue(
        code=code,
        severity="error",
        message=message,
        identity=IssueIdentity(
            change=change.id,
            entity=entity_id if kind != "interface" else None,
            interface=entity_id if kind == "interface" else None,
        ),
        locations=[source] if source is not None else [],
        details={"entity_kind": kind, **(details or {})},
    )


def _operation(
    *,
    change: Change,
    kind: EntityKind,
    entity_id: str,
    operation_kind: Literal["add", "modify", "move", "remove"],
    source: SourceLocation | None,
    **updates: Any,
) -> NormalizedOperation:
    return NormalizedOperation(
        id=f"{change.id}:{kind}:{entity_id}:{operation_kind}",
        kind=operation_kind,
        entity_kind=kind,
        entity_id=entity_id,
        change_id=change.id,
        source=source,
        **updates,
    )


def _mutation_values(*, patch: PatchBase, kind: EntityKind) -> dict[str, Any]:
    values = patch.model_dump(
        mode="python",
        exclude={"change_note", "change_type", "expected", "id", "source", "unset"},
        exclude_none=True,
        exclude_unset=True,
    )
    parent = values.pop("parent", None)
    parent_field = PARENT_FIELDS.get(kind)
    if parent is not None and parent_field is not None:
        values[parent_field] = parent
    return values


def _required_fields(kind: EntityKind) -> set[str]:
    return {
        "system": {"name"},
        "application": {"name", "system"},
        "component": {"name", "application"},
        "interface": {"name", "provider", "consumer"},
        "user": {"name"},
        "relationship": {"name", "source_id", "target_id"},
    }[kind]


def _all_endpoint_ids(
    index: EntityIndex,
    planned_adds: PlannedEntities,
    planned_removals: set[tuple[EntityKind, str]],
) -> set[str]:
    return {
        entity_id
        for kind in ENDPOINT_KINDS
        for entity_id in index[kind]
        if (kind, entity_id) not in planned_removals
    } | {entity_id for kind in ENDPOINT_KINDS for entity_id in planned_adds[kind]}


def _validate_expected(
    *,
    patch: PatchBase,
    existing: EntityData,
    change: Change,
    kind: EntityKind,
) -> list[Issue]:
    issues: list[Issue] = []
    for field, expected in patch.expected.items():
        actual = existing.get(field)
        if actual != expected:
            issues.append(
                _issue(
                    code="arch.stale_precondition",
                    message=(
                        f"{kind} '{patch.id}' expected {field}={expected!r}, "
                        f"received {actual!r}"
                    ),
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    source=patch.source,
                    details={"field": field, "expected": expected, "actual": actual},
                )
            )
    return issues


def _validate_add_references(
    *,
    kind: EntityKind,
    entity_id: str,
    values: EntityData,
    index: EntityIndex,
    planned_adds: PlannedEntities,
    planned_removals: set[tuple[EntityKind, str]],
    change: Change,
    source: SourceLocation | None,
) -> list[Issue]:
    issues: list[Issue] = []
    parent_field = PARENT_FIELDS.get(kind)
    if parent_field is not None:
        parent_id = values.get(parent_field)
        parent_kind: EntityKind = "system" if kind == "application" else "application"
        parent_available = (
            parent_id in index[parent_kind]
            and (parent_kind, parent_id) not in planned_removals
        ) or parent_id in planned_adds[parent_kind]
        if not parent_available:
            issues.append(
                _issue(
                    code="arch.missing_parent",
                    message=f"{kind} '{entity_id}' references missing {parent_field} '{parent_id}'",
                    change=change,
                    kind=kind,
                    entity_id=entity_id,
                    source=source,
                    details={"parent_field": parent_field, "parent_id": parent_id},
                )
            )

    endpoints = _all_endpoint_ids(index, planned_adds, planned_removals)
    endpoint_fields: tuple[str, str] | None = None
    if kind == "interface":
        endpoint_fields = ("provider", "consumer")
    elif kind == "relationship":
        endpoint_fields = ("source_id", "target_id")
    if endpoint_fields is not None:
        for field in endpoint_fields:
            endpoint = values.get(field)
            if endpoint not in endpoints:
                code = (
                    "arch.missing_interface_endpoint"
                    if kind == "interface"
                    else "arch.missing_relationship_endpoint"
                )
                issues.append(
                    _issue(
                        code=code,
                        message=f"{kind} '{entity_id}' references missing {field} '{endpoint}'",
                        change=change,
                        kind=kind,
                        entity_id=entity_id,
                        source=source,
                        details={"endpoint_field": field, "endpoint_id": endpoint},
                    )
                )
    return issues


def _references_available(
    *,
    kind: EntityKind,
    values: EntityData,
    index: EntityIndex,
    planned_adds: PlannedEntities,
    planned_removals: set[tuple[EntityKind, str]],
) -> bool:
    parent_field = PARENT_FIELDS.get(kind)
    if parent_field is not None:
        parent_kind: EntityKind = "system" if kind == "application" else "application"
        parent_id = values.get(parent_field)
        if not (
            (
                parent_id in index[parent_kind]
                and (parent_kind, parent_id) not in planned_removals
            )
            or parent_id in planned_adds[parent_kind]
        ):
            return False

    endpoint_fields: tuple[str, str] | None = None
    if kind == "interface":
        endpoint_fields = ("provider", "consumer")
    elif kind == "relationship":
        endpoint_fields = ("source_id", "target_id")
    if endpoint_fields is None:
        return True
    endpoints = _all_endpoint_ids(index, planned_adds, planned_removals)
    return all(values.get(field) in endpoints for field in endpoint_fields)


def _containment_descendants(
    index: EntityIndex, kind: EntityKind, entity_id: str
) -> set[tuple[EntityKind, str]]:
    descendants: set[tuple[EntityKind, str]] = set()
    if kind == "system":
        applications = {
            item_id
            for item_id, value in index["application"].items()
            if value.get("system") == entity_id
        }
        descendants.update(("application", item_id) for item_id in applications)
        descendants.update(
            ("component", item_id)
            for item_id, value in index["component"].items()
            if value.get("application") in applications
        )
    elif kind == "application":
        descendants.update(
            ("component", item_id)
            for item_id, value in index["component"].items()
            if value.get("application") == entity_id
        )
    return descendants


def _expand_removal(
    *, index: EntityIndex, root_kind: EntityKind, root_id: str
) -> set[tuple[EntityKind, str]]:
    removed = {(root_kind, root_id)} | _containment_descendants(
        index, root_kind, root_id
    )
    removed_ids = {entity_id for _, entity_id in removed}
    removed.update(
        ("interface", entity_id)
        for entity_id, value in index["interface"].items()
        if value.get("provider") in removed_ids or value.get("consumer") in removed_ids
    )
    removed.update(
        ("relationship", entity_id)
        for entity_id, value in index["relationship"].items()
        if value.get("source_id") in removed_ids
        or value.get("target_id") in removed_ids
    )
    return removed


def normalize_change(*, state: CompleteState, change: Change) -> NormalizationResult:
    """Normalize one sparse change against a complete state without applying it."""
    index = state_index(state)
    errors: list[Issue] = []
    operations: list[NormalizedOperation] = []
    seen: set[tuple[EntityKind, str]] = set()
    duplicates: set[tuple[EntityKind, str]] = set()
    explicit_removals: dict[tuple[EntityKind, str], PatchBase] = {}
    planned_adds: PlannedEntities = {kind: set() for kind in KIND_FIELDS}
    invalid_adds: set[tuple[EntityKind, str]] = set()

    all_patches = list(_patches(change))
    for kind, patch in all_patches:
        key = (kind, patch.id)
        if key in seen:
            duplicates.add(key)
            errors.append(
                _issue(
                    code="arch.duplicate_operation",
                    message=f"Change '{change.id}' patches {kind} '{patch.id}' more than once",
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    source=patch.source,
                )
            )
            continue
        seen.add(key)
        if patch.change_type == "removed":
            explicit_removals[key] = patch
        elif patch.id not in index[kind]:
            planned_adds[kind].add(patch.id)

    planned_by_id: dict[str, set[EntityKind]] = {}
    for kind, entity_ids in planned_adds.items():
        for entity_id in entity_ids:
            planned_by_id.setdefault(entity_id, set()).add(kind)
    existing_by_id: dict[str, set[EntityKind]] = {}
    for kind, entities in index.items():
        for entity_id in entities:
            existing_by_id.setdefault(entity_id, set()).add(kind)
    for entity_id, planned_kinds in sorted(planned_by_id.items()):
        colliding_kinds = planned_kinds | existing_by_id.get(entity_id, set())
        if len(colliding_kinds) < 2:
            continue
        invalid_adds.update((kind, entity_id) for kind in planned_kinds)
        locations = [
            patch.source
            for kind, patch in all_patches
            if patch.id == entity_id
            and kind in planned_kinds
            and patch.source is not None
        ]
        errors.append(
            Issue(
                code="arch.duplicate_id",
                severity="error",
                message=(
                    f"Entity ID '{entity_id}' is used by multiple kinds: "
                    f"{', '.join(sorted(colliding_kinds))}"
                ),
                identity=IssueIdentity(entity=entity_id),
                locations=locations,
                details={"entity_kinds": sorted(colliding_kinds)},
            )
        )

    planned_removals: set[tuple[EntityKind, str]] = set()
    for root_kind, root_id in explicit_removals:
        if root_id in index[root_kind]:
            planned_removals.update(
                _expand_removal(index=index, root_kind=root_kind, root_id=root_id)
            )

    locally_valid_adds: PlannedEntities = {kind: set() for kind in KIND_FIELDS}
    add_values: dict[tuple[EntityKind, str], EntityData] = {}
    for kind, patch in all_patches:
        key = (kind, patch.id)
        values = _mutation_values(patch=patch, kind=kind)
        if (
            patch.id in index[kind]
            or patch.change_type in {"changed", "removed"}
            or key in duplicates
            or key in invalid_adds
            or not _required_fields(kind) <= values.keys()
            or bool(set(patch.unset) & (_required_fields(kind) | {"id"}))
        ):
            continue
        locally_valid_adds[kind].add(patch.id)
        add_values[key] = values

    planned_adds = locally_valid_adds
    changed = True
    while changed:
        changed = False
        for kind, entity_ids in planned_adds.items():
            for entity_id in tuple(entity_ids):
                if _references_available(
                    kind=kind,
                    values=add_values[(kind, entity_id)],
                    index=index,
                    planned_adds=planned_adds,
                    planned_removals=planned_removals,
                ):
                    continue
                entity_ids.remove(entity_id)
                changed = True

    for kind, patch in all_patches:
        key = (kind, patch.id)
        if patch.change_type == "removed" or key in duplicates or key in invalid_adds:
            continue
        existing = index[kind].get(patch.id)
        values = _mutation_values(patch=patch, kind=kind)
        if existing is None and patch.change_type == "changed":
            errors.append(
                _issue(
                    code="arch.modify_before_add",
                    message=f"{kind} '{patch.id}' is asserted changed but does not exist",
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    source=patch.source,
                )
            )
            continue
        if existing is not None and patch.change_type == "added":
            errors.append(
                _issue(
                    code="arch.duplicate_add",
                    message=f"{kind} '{patch.id}' is asserted added but already exists",
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    source=patch.source,
                )
            )
            continue

        protected_unset = _required_fields(kind) | {"id"}
        invalid_unset = sorted(set(patch.unset) & protected_unset)
        if invalid_unset:
            errors.append(
                _issue(
                    code="arch.incompatible_field_change",
                    message=f"{kind} '{patch.id}' cannot unset required fields {invalid_unset}",
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    source=patch.source,
                    details={"fields": invalid_unset},
                )
            )
            continue

        if existing is None:
            missing = sorted(
                field for field in _required_fields(kind) if field not in values
            )
            if missing:
                errors.append(
                    _issue(
                        code="arch.incomplete_add",
                        message=f"Added {kind} '{patch.id}' is missing required fields {missing}",
                        change=change,
                        kind=kind,
                        entity_id=patch.id,
                        source=patch.source,
                        details={"missing_fields": missing},
                    )
                )
                continue
            reference_issues = _validate_add_references(
                kind=kind,
                entity_id=patch.id,
                values=values,
                index=index,
                planned_adds=planned_adds,
                planned_removals=planned_removals,
                change=change,
                source=patch.source,
            )
            if reference_issues:
                errors.extend(reference_issues)
                continue
            operations.append(
                _operation(
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    operation_kind="add",
                    source=patch.source,
                    values=values,
                    preconditions=[OperationPrecondition(kind="absent")],
                )
            )
            continue

        expected_issues = _validate_expected(
            patch=patch,
            existing=existing,
            change=change,
            kind=kind,
        )
        if expected_issues:
            errors.extend(expected_issues)
            continue

        if kind in {"interface", "relationship"} and any(
            field in values
            for field in (
                ("provider", "consumer")
                if kind == "interface"
                else ("source_id", "target_id")
            )
        ):
            reference_issues = _validate_add_references(
                kind=kind,
                entity_id=patch.id,
                values={**existing, **values},
                index=index,
                planned_adds=planned_adds,
                planned_removals=planned_removals,
                change=change,
                source=patch.source,
            )
            if reference_issues:
                errors.extend(reference_issues)
                continue

        parent_field = PARENT_FIELDS.get(kind)
        new_parent = (
            values.pop(parent_field, None) if parent_field is not None else None
        )
        if (
            parent_field is not None
            and new_parent is not None
            and new_parent != existing.get(parent_field)
        ):
            parent_kind: EntityKind = (
                "system" if kind == "application" else "application"
            )
            if new_parent == patch.id or (
                (
                    new_parent not in index[parent_kind]
                    or (parent_kind, new_parent) in planned_removals
                )
                and new_parent not in planned_adds[parent_kind]
            ):
                errors.append(
                    _issue(
                        code="arch.invalid_move",
                        message=f"{kind} '{patch.id}' cannot move to '{new_parent}'",
                        change=change,
                        kind=kind,
                        entity_id=patch.id,
                        source=patch.source,
                        details={"to_parent": new_parent},
                    )
                )
            else:
                operations.append(
                    _operation(
                        change=change,
                        kind=kind,
                        entity_id=patch.id,
                        operation_kind="move",
                        source=patch.source,
                        from_parent=existing.get(parent_field),
                        to_parent=new_parent,
                        preconditions=[
                            OperationPrecondition(kind="present"),
                            OperationPrecondition(
                                kind="parent_exists", expected=new_parent
                            ),
                        ],
                    )
                )

        changed_values = {
            key: value for key, value in values.items() if existing.get(key) != value
        }
        if changed_values or patch.unset:
            preconditions = [OperationPrecondition(kind="present")]
            preconditions.extend(
                OperationPrecondition(
                    kind="field_equals", field=field, expected=expected
                )
                for field, expected in patch.expected.items()
            )
            operations.append(
                _operation(
                    change=change,
                    kind=kind,
                    entity_id=patch.id,
                    operation_kind="modify",
                    source=patch.source,
                    values=changed_values,
                    unset=patch.unset,
                    preconditions=preconditions,
                )
            )

    emitted_removals: set[tuple[EntityKind, str]] = set()
    for root, root_patch in explicit_removals.items():
        root_kind, root_id = root
        if root_id not in index[root_kind]:
            errors.append(
                _issue(
                    code="arch.remove_before_add",
                    message=f"{root_kind} '{root_id}' cannot be removed because it does not exist",
                    change=change,
                    kind=root_kind,
                    entity_id=root_id,
                    source=root_patch.source,
                )
            )
            continue
        expanded = sorted(
            _expand_removal(index=index, root_kind=root_kind, root_id=root_id),
            key=lambda item: (REMOVAL_ORDER[item[0]], item[1]),
        )
        for target_kind, target_id in expanded:
            target = (target_kind, target_id)
            if target in emitted_removals:
                continue
            emitted_removals.add(target)
            explicit_patch = explicit_removals.get(target)
            generated = target != root and explicit_patch is None
            source = (
                explicit_patch.source
                if explicit_patch is not None
                else root_patch.source
            )
            operations.append(
                _operation(
                    change=change,
                    kind=target_kind,
                    entity_id=target_id,
                    operation_kind="remove",
                    source=source,
                    generated=generated,
                    initiating_ancestor=root_id if target != root else None,
                    cascade_path=[root_id, target_id] if target != root else [],
                    cause=f"cascade from {root_kind} '{root_id}'"
                    if target != root
                    else None,
                    preconditions=[OperationPrecondition(kind="present")],
                )
            )

    return NormalizationResult(
        change=NormalizedChange(change_id=change.id, operations=operations),
        issues=IssueCollection(errors=errors),
    )
