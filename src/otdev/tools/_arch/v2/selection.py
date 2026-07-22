"""Shared schema-v2 selection normalization and identity."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from .models import SavedView, SelectionInput, ViewSelection


class SelectionError(ValueError):
    """Raised when a saved or ad hoc selection cannot be normalized."""


def merge_selection(
    *,
    defaults: ViewSelection | None,
    saved: SavedView | None,
    adhoc: Mapping[str, Any] | ViewSelection | None,
) -> ViewSelection:
    """Merge defaults, saved values, and explicit ad hoc values in precedence order."""
    merged: dict[str, Any] = {}
    for candidate in (defaults, saved, adhoc):
        if candidate is None:
            continue
        if isinstance(candidate, ViewSelection):
            values = candidate.model_dump(
                exclude={"description", "id", "name", "source"},
                exclude_none=True,
                exclude_unset=True,
            )
        else:
            values = {
                key: value for key, value in candidate.items() if value is not None
            }
        merged.update(values)
    return ViewSelection.model_validate(merged)


def resolve_selection_input(
    *,
    value: SelectionInput | None,
    saved_views: Mapping[str, SavedView],
    defaults: ViewSelection | None = None,
) -> ViewSelection:
    """Resolve a saved-view ID or ad hoc selection into the shared grammar."""
    if value is None:
        return merge_selection(defaults=defaults, saved=None, adhoc=None)
    if isinstance(value, str):
        saved = saved_views.get(value)
        if saved is None:
            raise SelectionError(f"Unknown saved view: {value}")
        return merge_selection(defaults=defaults, saved=saved, adhoc=None)
    if isinstance(value, ViewSelection):
        return merge_selection(defaults=defaults, saved=None, adhoc=value)

    saved_id = value.get("view")
    saved = None
    if saved_id is not None:
        if not isinstance(saved_id, str):
            raise SelectionError("view must be a saved-view ID")
        saved = saved_views.get(saved_id)
        if saved is None:
            raise SelectionError(f"Unknown saved view: {saved_id}")
    adhoc = {key: item for key, item in value.items() if key != "view"}
    return merge_selection(defaults=defaults, saved=saved, adhoc=adhoc)


def selection_identity(selection: ViewSelection) -> str:
    """Return a deterministic content identity for a normalized selection."""
    values = selection.model_dump(mode="json", exclude_none=True)
    values["focus"] = sorted(set(values.get("focus", [])))
    values["display_statuses"] = sorted(set(values.get("display_statuses", [])))
    selector = values.get("system_set")
    if isinstance(selector, dict):
        values["system_set"] = {
            key: sorted(set(items)) if isinstance(items, list) else items
            for key, items in selector.items()
        }
    payload = json.dumps(
        values,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"selection-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
