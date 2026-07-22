"""Complete-state comparison and derived sparse change materialization."""

from __future__ import annotations

from typing import Any

from .models import (
    Change,
    ChangePatches,
    CompleteState,
    ContributingHistory,
    ElementPatch,
    EntityKind,
    InterfacePatch,
    NormalizedChange,
    NormalizedOperation,
    OperationPrecondition,
    RelationshipPatch,
    SourceLocation,
    StateComparison,
)
from .normalize import KIND_FIELDS, PARENT_FIELDS, state_index


def _source(value: dict[str, Any]) -> SourceLocation | None:
    raw = value.get("source")
    return SourceLocation.model_validate(raw) if raw is not None else None


def compare_states(
    *,
    base: CompleteState,
    target: CompleteState,
    change_id: str | None = None,
    contributing_history: list[ContributingHistory] | None = None,
) -> StateComparison:
    """Compare complete states by stable IDs and derive net normalized operations."""
    derived_id = change_id or f"diff-{base.id}-to-{target.id}"
    base_index = state_index(base)
    target_index = state_index(target)
    operations: list[NormalizedOperation] = []

    for kind in KIND_FIELDS:
        base_entities = base_index[kind]
        target_entities = target_index[kind]
        for entity_id in sorted(target_entities.keys() - base_entities.keys()):
            values = {
                key: value
                for key, value in target_entities[entity_id].items()
                if key not in {"id", "source"} and value not in ([], {})
            }
            operations.append(
                NormalizedOperation(
                    id=f"{derived_id}:{kind}:{entity_id}:add",
                    kind="add",
                    entity_kind=kind,
                    entity_id=entity_id,
                    change_id=derived_id,
                    values=values,
                    preconditions=[OperationPrecondition(kind="absent")],
                    source=_source(target_entities[entity_id]),
                )
            )
        for entity_id in sorted(base_entities.keys() - target_entities.keys()):
            operations.append(
                NormalizedOperation(
                    id=f"{derived_id}:{kind}:{entity_id}:remove",
                    kind="remove",
                    entity_kind=kind,
                    entity_id=entity_id,
                    change_id=derived_id,
                    preconditions=[OperationPrecondition(kind="present")],
                    source=_source(base_entities[entity_id]),
                )
            )
        for entity_id in sorted(base_entities.keys() & target_entities.keys()):
            before = base_entities[entity_id]
            after = target_entities[entity_id]
            parent_field = PARENT_FIELDS.get(kind)
            if parent_field is not None and before.get(parent_field) != after.get(parent_field):
                operations.append(
                    NormalizedOperation(
                        id=f"{derived_id}:{kind}:{entity_id}:move",
                        kind="move",
                        entity_kind=kind,
                        entity_id=entity_id,
                        change_id=derived_id,
                        from_parent=before.get(parent_field),
                        to_parent=after.get(parent_field),
                        preconditions=[
                            OperationPrecondition(kind="present"),
                            OperationPrecondition(
                                kind="field_equals",
                                field=parent_field,
                                expected=before.get(parent_field),
                            ),
                        ],
                        source=_source(after),
                    )
                )
            ignored = {"id", "source"}
            if parent_field is not None:
                ignored.add(parent_field)
            changed = {
                key: value
                for key, value in after.items()
                if key not in ignored and before.get(key) != value
            }
            unset = sorted(
                key for key in before.keys() - after.keys() if key not in ignored
            )
            if changed or unset:
                expected_fields = sorted(set(changed) | set(unset))
                operations.append(
                    NormalizedOperation(
                        id=f"{derived_id}:{kind}:{entity_id}:modify",
                        kind="modify",
                        entity_kind=kind,
                        entity_id=entity_id,
                        change_id=derived_id,
                        values=changed,
                        unset=unset,
                        preconditions=[
                            OperationPrecondition(kind="present"),
                            *[
                                OperationPrecondition(
                                    kind="field_equals",
                                    field=field,
                                    expected=before.get(field),
                                )
                                for field in expected_fields
                            ],
                        ],
                        source=_source(after),
                    )
                )

    history = contributing_history or []
    net_keys = {(item.entity_kind, item.entity_id) for item in operations}
    canceled = [
        operation
        for item in history
        for operation in item.operations
        if (operation.entity_kind, operation.entity_id) not in net_keys
    ]
    return StateComparison(
        base_state_id=base.id,
        target_state_id=target.id,
        change=NormalizedChange(change_id=derived_id, operations=operations),
        contributing_history=history,
        canceled_history=canceled,
    )


def _expected_values(operation: NormalizedOperation) -> dict[str, Any]:
    return {
        item.field: item.expected
        for item in operation.preconditions
        if item.kind == "field_equals" and item.field is not None
    }


def materialize_change(*, comparison: StateComparison, change_id: str, name: str | None = None) -> Change:
    """Convert normalized net operations into one sparse change with preconditions."""
    grouped: dict[EntityKind, list[Any]] = {
        "system": [],
        "application": [],
        "component": [],
        "interface": [],
        "user": [],
        "relationship": [],
    }
    merged: dict[tuple[EntityKind, str], dict[str, Any]] = {}
    for operation in comparison.change.operations:
        key = (operation.entity_kind, operation.entity_id)
        patch = merged.setdefault(key, {"id": operation.entity_id})
        if operation.kind == "add":
            patch["change_type"] = "added"
            patch.update(operation.values)
        elif operation.kind == "remove":
            patch["change_type"] = "removed"
        elif operation.kind == "move":
            patch["parent"] = operation.to_parent
            patch["expected"] = {
                **patch.get("expected", {}),
                **_expected_values(operation),
            }
        elif operation.kind == "modify":
            patch["change_type"] = "changed"
            patch.update(operation.values)
            if operation.unset:
                patch["unset"] = operation.unset
            patch["expected"] = {
                **patch.get("expected", {}),
                **_expected_values(operation),
            }

    for (kind, _), payload in merged.items():
        if kind == "interface":
            grouped[kind].append(InterfacePatch.model_validate(payload))
        elif kind == "relationship":
            grouped[kind].append(RelationshipPatch.model_validate(payload))
        else:
            grouped[kind].append(ElementPatch.model_validate(payload))

    return Change.model_validate(
        {
            "id": change_id,
            "name": name or change_id,
            "description": (
                f"Derived from complete state {comparison.base_state_id} "
                f"to {comparison.target_state_id}"
            ),
            "base_state_id": comparison.base_state_id,
            "target_state_id": comparison.target_state_id,
            "patches": ChangePatches(
                systems=grouped["system"],
                applications=grouped["application"],
                components=grouped["component"],
                interfaces=grouped["interface"],
                users=grouped["user"],
                relationships=grouped["relationship"],
            ),
        }
    )
