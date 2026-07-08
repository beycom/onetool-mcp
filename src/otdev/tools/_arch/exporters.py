"""Entity filtering and serialization helpers for arch pack."""

from __future__ import annotations

from typing import Any

from .models import (
    APP_REF_KEYS,
    PROJECT_SCOPE_ITEM_TYPES,
    SHEET_APP,
    SHEET_CMP,
    SHEET_INTERFACE,
    SHEET_PROJECT,
    SHEET_PROJECT_SCOPE,
    SHEET_SYS,
    SHEET_USR,
    SYS_REF_KEYS,
    first_value,
    tags_for_row,
)


def apply_tag_filters(
    *,
    entities: dict[str, list[dict[str, Any]]],
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Filter entities by include/exclude tag lists."""
    include = {item.strip().lower() for item in include_tags or [] if item and item.strip()}
    exclude = {item.strip().lower() for item in exclude_tags or [] if item and item.strip()}

    if not include and not exclude:
        return {sheet: [dict(row) for row in rows] for sheet, rows in entities.items()}

    filtered: dict[str, list[dict[str, Any]]] = {sheet: [] for sheet in entities}
    for sheet, rows in entities.items():
        for row in rows:
            row_tags = tags_for_row(row)
            if include and not (row_tags & include):
                continue
            if exclude and (row_tags & exclude):
                continue
            filtered[sheet].append(dict(row))

    system_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_SYS] if row.get("id")}
    app_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_APP] if row.get("id")}
    cmp_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_CMP] if row.get("id")}
    usr_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_USR] if row.get("id")}

    filtered[SHEET_APP] = [
        row
        for row in filtered[SHEET_APP]
        if str(first_value(row, SYS_REF_KEYS) or "").strip() in system_ids
    ]
    app_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_APP] if row.get("id")}

    filtered[SHEET_CMP] = [
        row
        for row in filtered[SHEET_CMP]
        if str(first_value(row, APP_REF_KEYS) or "").strip() in app_ids
        or (
            not first_value(row, APP_REF_KEYS)
            and str(first_value(row, SYS_REF_KEYS) or "").strip() in system_ids
        )
    ]
    cmp_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_CMP] if row.get("id")}

    filtered[SHEET_USR] = [
        row
        for row in filtered[SHEET_USR]
        if not first_value(row, APP_REF_KEYS)
        or str(first_value(row, APP_REF_KEYS)).strip() in app_ids
    ]
    usr_ids = {str(row.get("id", "")).strip() for row in filtered[SHEET_USR] if row.get("id")}
    node_ids = system_ids | app_ids | cmp_ids | usr_ids

    filtered[SHEET_INTERFACE] = [
        row
        for row in filtered[SHEET_INTERFACE]
        if str(row.get("provider") or "").strip() in node_ids
        and str(row.get("consumer") or "").strip() in node_ids
    ]
    interface_ids = {
        str(row.get("id", "")).strip()
        for row in filtered[SHEET_INTERFACE]
        if row.get("id")
    }
    item_ids_by_type = {
        "sys": system_ids,
        "app": app_ids,
        "cmp": cmp_ids,
        "interface": interface_ids,
    }
    project_ids = {
        str(row.get("id", "")).strip()
        for row in filtered.get(SHEET_PROJECT, [])
        if row.get("id")
    }
    filtered[SHEET_PROJECT_SCOPE] = [
        row
        for row in filtered.get(SHEET_PROJECT_SCOPE, [])
        if str(first_value(row, ("project", "project_id")) or "").strip() in project_ids
        and str(row.get("item_id") or "").strip()
        in item_ids_by_type.get(
            PROJECT_SCOPE_ITEM_TYPES.get(str(row.get("item_type") or "").strip().lower(), ""),
            set(),
        )
    ]

    return filtered


def serializable_entities(*, entities: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Return entities without internal bookkeeping keys."""
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for sheet, rows in entities.items():
        cleaned[sheet] = []
        for row in rows:
            cleaned_row = {key: value for key, value in row.items() if not key.startswith("_")}
            cleaned[sheet].append(cleaned_row)
    return cleaned


__all__ = [
    "apply_tag_filters",
    "serializable_entities",
]
