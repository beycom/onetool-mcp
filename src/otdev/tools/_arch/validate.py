"""Entity validation helpers for arch pack."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import CORE_SHEETS, Issue, first_value

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "sys": ("id", "name"),
    "app": ("id", "name"),
    "cmp": ("id", "name"),
    "int": ("id", "src", "dst"),
    "usr": ("id", "name"),
}

_APP_SYSTEM_KEYS = ("sys", "system", "system_id", "sys_id")
_CMP_APP_KEYS = ("app", "application", "app_id", "application_id")
_INT_SRC_KEYS = ("src", "source", "from", "from_id", "src_id")
_INT_DST_KEYS = ("dst", "target", "to", "to_id", "dst_id")
_USR_APP_KEYS = ("app", "application", "app_id", "application_id")


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
    counter = Counter()
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

    for row in entities["app"]:
        row_num = int(row.get("_sheet_row", 0))
        sys_id = first_value(row, _APP_SYSTEM_KEYS)
        if sys_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Application row must reference a system",
                    details={"sheet": "app", "row": row_num, "field": "sys"},
                )
            )
            continue
        if str(sys_id).strip() not in system_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Application references unknown system '{sys_id}'",
                    details={"sheet": "app", "row": row_num, "field": "sys", "value": str(sys_id)},
                )
            )

    for row in entities["cmp"]:
        row_num = int(row.get("_sheet_row", 0))
        app_id = first_value(row, _CMP_APP_KEYS)
        if app_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Component row must reference an application",
                    details={"sheet": "cmp", "row": row_num, "field": "app"},
                )
            )
            continue
        if str(app_id).strip() not in app_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Component references unknown application '{app_id}'",
                    details={"sheet": "cmp", "row": row_num, "field": "app", "value": str(app_id)},
                )
            )

    for row in entities["int"]:
        row_num = int(row.get("_sheet_row", 0))
        src_id = first_value(row, _INT_SRC_KEYS)
        dst_id = first_value(row, _INT_DST_KEYS)
        if src_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Integration row must reference src",
                    details={"sheet": "int", "row": row_num, "field": "src"},
                )
            )
        elif str(src_id).strip() not in node_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Integration source '{src_id}' not found",
                    details={"sheet": "int", "row": row_num, "field": "src", "value": str(src_id)},
                )
            )

        if dst_id is None:
            issues.append(
                Issue(
                    code="missing_reference",
                    message="Integration row must reference dst",
                    details={"sheet": "int", "row": row_num, "field": "dst"},
                )
            )
        elif str(dst_id).strip() not in node_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"Integration destination '{dst_id}' not found",
                    details={"sheet": "int", "row": row_num, "field": "dst", "value": str(dst_id)},
                )
            )

    for row in entities["usr"]:
        row_num = int(row.get("_sheet_row", 0))
        app_id = first_value(row, _USR_APP_KEYS)
        if app_id is not None and str(app_id).strip() not in app_ids:
            issues.append(
                Issue(
                    code="invalid_reference",
                    message=f"User references unknown application '{app_id}'",
                    details={"sheet": "usr", "row": row_num, "field": "app", "value": str(app_id)},
                )
            )

    return issues


def validate_entities(*, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Validate required fields, duplicates, and reference integrity."""
    errors: list[Issue] = []
    warnings: list[Issue] = []

    for sheet in CORE_SHEETS:
        rows = entities.get(sheet, [])
        for row in rows:
            row_num = int(row.get("_sheet_row", 0))
            errors.extend(_missing_required(sheet=sheet, row=row, row_index=row_num))
        errors.extend(_duplicate_ids(sheet=sheet, rows=rows))

    system_ids = {str(row["id"]).strip() for row in entities.get("sys", []) if row.get("id")}
    app_ids = {str(row["id"]).strip() for row in entities.get("app", []) if row.get("id")}
    component_ids = {str(row["id"]).strip() for row in entities.get("cmp", []) if row.get("id")}
    user_ids = {str(row["id"]).strip() for row in entities.get("usr", []) if row.get("id")}

    node_ids = system_ids | app_ids | component_ids | user_ids
    errors.extend(
        _check_refs(
            entities=entities,
            system_ids=system_ids,
            app_ids=app_ids,
            node_ids=node_ids,
        )
    )

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
