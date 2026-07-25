"""Entity validation helpers for arch pack."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import (
    APP_REF_KEYS,
    ARROW_DIRECTIONS,
    CORE_SHEETS,
    PROJECT_SCOPE_ITEM_TYPES,
    SHEET_APP,
    SHEET_CMP,
    SHEET_INTERFACE,
    SHEET_PROJECT,
    SHEET_PROJECT_SCOPE,
    SHEET_SYS,
    SHEET_USR,
    SYS_REF_KEYS,
    Issue,
    first_value,
)

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    SHEET_SYS: ("id", "name"),
    SHEET_APP: ("id", "name"),
    SHEET_CMP: ("id", "name"),
    SHEET_INTERFACE: ("id", "provider", "consumer"),
    SHEET_USR: ("id", "name"),
    SHEET_PROJECT: ("id", "name"),
    SHEET_PROJECT_SCOPE: ("project", "stage", "item_type", "item_id", "change_type"),
}

_DETAIL_LEVELS = {"sys", "app", "cmp"}
_CONNECT_LEVELS = {"sys", "app", "cmp", "lowest_visible"}
_PROJECT_SCOPE_CHANGE_TYPES = {
    "existing",
    "new",
    "changed",
    "removed",
    "impacted",
    "dependency",
}


def _missing_required(
    *, sheet: str, row: dict[str, Any], row_index: int
) -> list[Issue]:
    issues: list[Issue] = []
    for field in _REQUIRED_FIELDS[sheet]:
        value = row.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(
                Issue(
                    code="missing_required_field",
                    message=f"Missing required field '{field}' in {sheet} row",
                    details={"sheet": sheet, "row": row_index, "field": field},
                )
            )
    return issues


def _duplicate_ids(*, sheet: str, rows: list[dict[str, Any]]) -> list[Issue]:
    counter: Counter[str] = Counter()
    for row in rows:
        row_id = row.get("id")
        if row_id is None:
            continue
        counter[str(row_id).strip()] += 1

    issues: list[Issue] = []
    for row_id, count in counter.items():
        if row_id and count > 1:
            issues.append(
                Issue(
                    code="duplicate_id",
                    message=f"Duplicate id '{row_id}' in {sheet}",
                    details={"sheet": sheet, "id": row_id, "count": count},
                )
            )
    return issues


def _check_refs(
    *,
    entities: dict[str, list[dict[str, Any]]],
    system_ids: set[str],
    app_ids: set[str],
    node_ids: set[str],
) -> list[Issue]:
    issues: list[Issue] = []

    for row in entities[SHEET_APP]:
        row_num = int(row.get("_sheet_row", 0))
        sys_id = first_value(row, SYS_REF_KEYS)
        if sys_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Application row must reference a system",
                    details={"sheet": SHEET_APP, "row": row_num, "field": "sys"},
                )
            )
            continue
        if str(sys_id).strip() not in system_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Application references unknown system '{sys_id}'",
                    details={
                        "sheet": SHEET_APP,
                        "row": row_num,
                        "field": "sys",
                        "value": str(sys_id),
                    },
                )
            )

    for row in entities[SHEET_CMP]:
        row_num = int(row.get("_sheet_row", 0))
        app_id = first_value(row, APP_REF_KEYS)
        sys_id = first_value(row, SYS_REF_KEYS)
        if app_id is None and sys_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Component row must reference an application or a system",
                    details={"sheet": SHEET_CMP, "row": row_num, "field": "app"},
                )
            )
            continue
        if app_id is not None:
            if str(app_id).strip() not in app_ids:
                issues.append(
                    Issue(
                        code="invalid_reference",
                        message=f"Component references unknown application '{app_id}'",
                        details={
                            "sheet": SHEET_CMP,
                            "row": row_num,
                            "field": "app",
                            "value": str(app_id),
                        },
                    )
                )
        elif str(sys_id).strip() not in system_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Component references unknown system '{sys_id}'",
                    details={
                        "sheet": SHEET_CMP,
                        "row": row_num,
                        "field": "sys",
                        "value": str(sys_id),
                    },
                )
            )

    for row in entities[SHEET_INTERFACE]:
        row_num = int(row.get("_sheet_row", 0))
        provider_id = first_value(row, ("provider",))
        consumer_id = first_value(row, ("consumer",))
        if provider_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Interface row must reference provider",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": row_num,
                        "field": "provider",
                    },
                )
            )
        elif str(provider_id).strip() not in node_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Interface provider '{provider_id}' not found",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": row_num,
                        "field": "provider",
                        "value": str(provider_id),
                    },
                )
            )

        if consumer_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Interface row must reference consumer",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": row_num,
                        "field": "consumer",
                    },
                )
            )
        elif str(consumer_id).strip() not in node_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Interface consumer '{consumer_id}' not found",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": row_num,
                        "field": "consumer",
                        "value": str(consumer_id),
                    },
                )
            )

        interaction_type = row.get("interaction_type")
        if interaction_type is not None and not str(interaction_type).strip():
            issues.append(
                Issue(
                    code="invalid_value",
                    message="Interface interaction_type must be non-empty when provided",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": row_num,
                        "field": "interaction_type",
                    },
                )
            )

        arrow_direction = row.get("arrow_direction")
        if arrow_direction is not None:
            normalized_arrow = str(arrow_direction).strip().lower()
            if normalized_arrow not in ARROW_DIRECTIONS:
                issues.append(
                    Issue(
                        code="invalid_value",
                        message=(
                            "Interface arrow_direction must be one of "
                            f"{sorted(ARROW_DIRECTIONS)}"
                        ),
                        details={
                            "sheet": SHEET_INTERFACE,
                            "row": row_num,
                            "field": "arrow_direction",
                            "value": str(arrow_direction),
                        },
                    )
                )

    project_ids = {
        str(row.get("id", "")).strip()
        for row in entities.get(SHEET_PROJECT, [])
        if row.get("id")
    }
    item_ids_by_type = {
        "sys": system_ids,
        "app": app_ids,
        "cmp": {
            str(row["id"]).strip()
            for row in entities.get(SHEET_CMP, [])
            if row.get("id")
        },
        "interface": {
            str(row["id"]).strip()
            for row in entities.get(SHEET_INTERFACE, [])
            if row.get("id")
        },
    }

    for row in entities.get(SHEET_PROJECT, []):
        row_num = int(row.get("_sheet_row", 0))
        detail_level = row.get("detail_level")
        if (
            detail_level is not None
            and str(detail_level).strip().lower() not in _DETAIL_LEVELS
        ):
            issues.append(
                Issue(
                    code="invalid_value",
                    message=f"Project detail_level must be one of {sorted(_DETAIL_LEVELS)}",
                    details={
                        "sheet": SHEET_PROJECT,
                        "row": row_num,
                        "field": "detail_level",
                        "value": str(detail_level),
                    },
                )
            )
        connect_level = row.get("connect_level")
        if (
            connect_level is not None
            and str(connect_level).strip().lower() not in _CONNECT_LEVELS
        ):
            issues.append(
                Issue(
                    code="invalid_value",
                    message=f"Project connect_level must be one of {sorted(_CONNECT_LEVELS)}",
                    details={
                        "sheet": SHEET_PROJECT,
                        "row": row_num,
                        "field": "connect_level",
                        "value": str(connect_level),
                    },
                )
            )

    for row in entities.get(SHEET_PROJECT_SCOPE, []):
        row_num = int(row.get("_sheet_row", 0))
        project_id = first_value(row, ("project", "project_id"))
        if project_id is not None and str(project_id).strip() not in project_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Project scope references unknown project '{project_id}'",
                    details={
                        "sheet": SHEET_PROJECT_SCOPE,
                        "row": row_num,
                        "field": "project",
                        "value": str(project_id),
                    },
                )
            )

        raw_item_type = row.get("item_type")
        item_type = (
            PROJECT_SCOPE_ITEM_TYPES.get(str(raw_item_type).strip().lower())
            if raw_item_type is not None
            else None
        )
        if raw_item_type is not None and item_type is None:
            issues.append(
                Issue(
                    code="invalid_value",
                    message=f"Project scope item_type must be one of {sorted(PROJECT_SCOPE_ITEM_TYPES)}",
                    details={
                        "sheet": SHEET_PROJECT_SCOPE,
                        "row": row_num,
                        "field": "item_type",
                        "value": str(raw_item_type),
                    },
                )
            )
        item_id = row.get("item_id")
        if (
            item_type is not None
            and item_id is not None
            and str(item_id).strip() not in item_ids_by_type[item_type]
        ):
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Project scope references unknown {item_type} '{item_id}'",
                    details={
                        "sheet": SHEET_PROJECT_SCOPE,
                        "row": row_num,
                        "field": "item_id",
                        "value": str(item_id),
                        "item_type": item_type,
                    },
                )
            )

        change_type = row.get("change_type")
        if (
            change_type is not None
            and str(change_type).strip().lower() not in _PROJECT_SCOPE_CHANGE_TYPES
        ):
            issues.append(
                Issue(
                    code="invalid_value",
                    message=f"Project scope change_type must be one of {sorted(_PROJECT_SCOPE_CHANGE_TYPES)}",
                    details={
                        "sheet": SHEET_PROJECT_SCOPE,
                        "row": row_num,
                        "field": "change_type",
                        "value": str(change_type),
                    },
                )
            )

    for row in entities[SHEET_USR]:
        row_num = int(row.get("_sheet_row", 0))
        app_id = first_value(row, APP_REF_KEYS)
        if app_id is not None and str(app_id).strip() not in app_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"User references unknown application '{app_id}'",
                    details={
                        "sheet": SHEET_USR,
                        "row": row_num,
                        "field": "app",
                        "value": str(app_id),
                    },
                )
            )

    return issues


def _collect_warnings(
    *,
    entities: dict[str, list[dict[str, Any]]],
    system_ids: set[str],
) -> list[Issue]:
    """Non-blocking data-quality warnings (design D5): `orphan_system`,
    `duplicate_name`, and `self_interface`. Never affect validity."""
    warnings: list[Issue] = []

    app_to_sys: dict[str, str] = {}
    for row in entities.get(SHEET_APP, []):
        app_id = str(row.get("id") or "").strip()
        sys_id = str(first_value(row, SYS_REF_KEYS) or "").strip()
        if app_id and sys_id:
            app_to_sys[app_id] = sys_id

    cmp_to_sys: dict[str, str] = {}
    for row in entities.get(SHEET_CMP, []):
        cmp_id = str(row.get("id") or "").strip()
        if not cmp_id:
            continue
        app_ref = str(first_value(row, APP_REF_KEYS) or "").strip()
        owner = (
            app_to_sys.get(app_ref)
            if app_ref
            else str(first_value(row, SYS_REF_KEYS) or "").strip()
        )
        if owner:
            cmp_to_sys[cmp_id] = owner

    def _owning_system(endpoint_id: str) -> str | None:
        if endpoint_id in system_ids:
            return endpoint_id
        return app_to_sys.get(endpoint_id) or cmp_to_sys.get(endpoint_id)

    referenced_system_ids: set[str] = set()
    for row in entities.get(SHEET_INTERFACE, []):
        for field in ("provider", "consumer"):
            endpoint = str(first_value(row, (field,)) or "").strip()
            if endpoint:
                owner = _owning_system(endpoint)
                if owner:
                    referenced_system_ids.add(owner)
    for row in entities.get(SHEET_PROJECT_SCOPE, []):
        item_id = str(row.get("item_id") or "").strip()
        if item_id:
            owner = _owning_system(item_id)
            if owner:
                referenced_system_ids.add(owner)

    for row in entities.get(SHEET_SYS, []):
        sys_id = str(row.get("id") or "").strip()
        if not sys_id or sys_id in referenced_system_ids:
            continue
        warnings.append(
            Issue(
                code="orphan_system",
                message=(
                    f"System '{sys_id}' is not referenced by any interface endpoint "
                    "or project scope row"
                ),
                details={
                    "sheet": SHEET_SYS,
                    "row": int(row.get("_sheet_row", 0)),
                    "id": sys_id,
                },
            )
        )

    for sheet in (SHEET_SYS, SHEET_APP, SHEET_CMP, SHEET_USR):
        ids_by_name: dict[str, list[str]] = {}
        display_name: dict[str, str] = {}
        for row in entities.get(sheet, []):
            row_id = str(row.get("id") or "").strip()
            name = str(row.get("name") or "").strip()
            if not row_id or not name:
                continue
            key = name.lower()
            ids = ids_by_name.setdefault(key, [])
            if row_id not in ids:
                ids.append(row_id)
            display_name.setdefault(key, name)
        for key, ids in ids_by_name.items():
            if len(ids) > 1:
                warnings.append(
                    Issue(
                        code="duplicate_name",
                        message=f"Duplicate name '{display_name[key]}' in {sheet}: {ids}",
                        details={"sheet": sheet, "name": display_name[key], "ids": ids},
                    )
                )

    for row in entities.get(SHEET_INTERFACE, []):
        provider = str(first_value(row, ("provider",)) or "").strip()
        consumer = str(first_value(row, ("consumer",)) or "").strip()
        if provider and provider == consumer:
            warnings.append(
                Issue(
                    code="self_interface",
                    message=f"Interface provider and consumer are both '{provider}'",
                    details={
                        "sheet": SHEET_INTERFACE,
                        "row": int(row.get("_sheet_row", 0)),
                        "id": str(row.get("id") or ""),
                        "value": provider,
                    },
                )
            )

    return warnings


def validate_entities(*, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Validate required fields, duplicates, and reference integrity."""
    errors: list[Issue] = []

    for sheet in CORE_SHEETS:
        rows = entities.get(sheet, [])
        for row in rows:
            row_num = int(row.get("_sheet_row", 0))
            errors.extend(_missing_required(sheet=sheet, row=row, row_index=row_num))
        errors.extend(_duplicate_ids(sheet=sheet, rows=rows))

    system_ids = {
        str(row["id"]).strip() for row in entities.get(SHEET_SYS, []) if row.get("id")
    }
    app_ids = {
        str(row["id"]).strip() for row in entities.get(SHEET_APP, []) if row.get("id")
    }
    component_ids = {
        str(row["id"]).strip() for row in entities.get(SHEET_CMP, []) if row.get("id")
    }
    user_ids = {
        str(row["id"]).strip() for row in entities.get(SHEET_USR, []) if row.get("id")
    }

    # IDs shared across node sheets resolve ambiguously in diagrams; reject them.
    sheets_by_id: dict[str, list[str]] = {}
    for sheet, ids in (
        (SHEET_SYS, system_ids),
        (SHEET_APP, app_ids),
        (SHEET_CMP, component_ids),
        (SHEET_USR, user_ids),
    ):
        for row_id in ids:
            sheets_by_id.setdefault(row_id, []).append(sheet)
    for row_id, sheets in sorted(sheets_by_id.items()):
        if len(sheets) > 1:
            errors.append(
                Issue(
                    code="duplicate_id",
                    message=f"Duplicate id '{row_id}' across sheets: {sheets}",
                    details={"sheets": sheets, "id": row_id},
                )
            )

    node_ids = system_ids | app_ids | component_ids | user_ids
    errors.extend(
        _check_refs(
            entities=entities,
            system_ids=system_ids,
            app_ids=app_ids,
            node_ids=node_ids,
        )
    )

    warnings = _collect_warnings(entities=entities, system_ids=system_ids)

    summary = {
        "counts": {sheet: len(rows) for sheet, rows in entities.items()},
        "errors": len(errors),
        "warnings": len(warnings),
    }

    return {
        "valid": len(errors) == 0,
        "issues": {
            "errors": [item.to_dict() for item in errors],
            "warnings": [item.to_dict() for item in warnings],
        },
        "summary": summary,
    }


__all__ = ["validate_entities"]
