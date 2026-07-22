"""Roadmap-wide impacted-system derivation from normalized operations."""

from __future__ import annotations

from collections import defaultdict

from .models import (
    CompleteState,
    EntityKind,
    ImpactReasonCode,
    NormalizedOperation,
    SystemImpactReason,
)
from .normalize import state_index

type EntityIndex = dict[EntityKind, dict[str, dict[str, object]]]


def _owning_system(*, entity_id: str, index: EntityIndex) -> str | None:
    if entity_id in index["system"]:
        return entity_id
    application = index["application"].get(entity_id)
    if application is not None:
        system = application.get("system")
        return system if isinstance(system, str) else None
    component = index["component"].get(entity_id)
    if component is None:
        return None
    application_id = component.get("application")
    if not isinstance(application_id, str):
        return None
    application = index["application"].get(application_id)
    if application is None:
        return None
    system = application.get("system")
    return system if isinstance(system, str) else None


def _reason(
    *, operation: NormalizedOperation, code: ImpactReasonCode
) -> SystemImpactReason:
    return SystemImpactReason(
        code=code,
        change_id=operation.change_id,
        operation_id=operation.id,
        entity_kind=operation.entity_kind,
        entity_id=operation.entity_id,
    )


def derive_system_impacts(
    *,
    before: CompleteState,
    after: CompleteState,
    operations: list[NormalizedOperation],
) -> dict[str, list[SystemImpactReason]]:
    """Return stable system impacts for one normalized before/after transition."""
    before_index = state_index(before)
    after_index = state_index(after)
    impacts: dict[str, list[SystemImpactReason]] = defaultdict(list)

    def add(
        system_id: str | None,
        operation: NormalizedOperation,
        code: ImpactReasonCode,
    ) -> None:
        if system_id is None:
            return
        impacts[system_id].append(_reason(operation=operation, code=code))
        if operation.generated:
            impacts[system_id].append(
                _reason(operation=operation, code="cascade_removal")
            )

    def add_owned(
        *,
        operation: NormalizedOperation,
        index: EntityIndex,
        code: ImpactReasonCode,
    ) -> None:
        add(
            _owning_system(entity_id=operation.entity_id, index=index),
            operation,
            code,
        )

    def add_endpoint(
        *,
        operation: NormalizedOperation,
        index: EntityIndex,
        field: str,
        code: ImpactReasonCode,
    ) -> None:
        entity = index[operation.entity_kind].get(operation.entity_id)
        endpoint = entity.get(field) if entity is not None else None
        add(
            _owning_system(entity_id=endpoint, index=index)
            if isinstance(endpoint, str)
            else None,
            operation,
            code,
        )

    for operation in operations:
        if operation.entity_kind == "system":
            add(operation.entity_id, operation, "system_patch")
            continue
        if operation.entity_kind in {"application", "component"}:
            owner_code: ImpactReasonCode = (
                "application_owner"
                if operation.entity_kind == "application"
                else "component_owner"
            )
            if operation.kind == "move":
                add_owned(
                    operation=operation,
                    index=before_index,
                    code="moved_from",
                )
                add_owned(
                    operation=operation,
                    index=after_index,
                    code="moved_to",
                )
            elif operation.kind == "remove":
                add_owned(
                    operation=operation,
                    index=before_index,
                    code=owner_code,
                )
            else:
                add_owned(
                    operation=operation,
                    index=after_index,
                    code=owner_code,
                )
            continue
        if operation.entity_kind == "interface":
            indexes = (
                [before_index]
                if operation.kind == "remove"
                else [after_index]
                if operation.kind == "add"
                else [before_index, after_index]
            )
            for index in indexes:
                add_endpoint(
                    operation=operation,
                    index=index,
                    field="provider",
                    code="interface_provider",
                )
                add_endpoint(
                    operation=operation,
                    index=index,
                    field="consumer",
                    code="interface_consumer",
                )
            continue
        if operation.entity_kind == "relationship":
            indexes = (
                [before_index]
                if operation.kind == "remove"
                else [after_index]
                if operation.kind == "add"
                else [before_index, after_index]
            )
            for index in indexes:
                add_endpoint(
                    operation=operation,
                    index=index,
                    field="source_id",
                    code="relationship_source",
                )
                add_endpoint(
                    operation=operation,
                    index=index,
                    field="target_id",
                    code="relationship_target",
                )

    result: dict[str, list[SystemImpactReason]] = {}
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
        result[system_id] = [unique[key] for key in sorted(unique)]
    return result
