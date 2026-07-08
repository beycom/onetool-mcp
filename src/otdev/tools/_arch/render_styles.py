"""Shared style vocabularies for arch diagram rendering.

Single source of truth for change-type and interaction-type styling so that
D2 diagram context, HTML badges, the legend, and tests all read identical
data. `styles.d2` remains a static file; a unit test asserts every class
name and hex color defined here appears verbatim in `styles.d2` to keep the
two in sync.
"""

from __future__ import annotations

import re

CHANGE_TYPE_STYLES: dict[str, dict[str, str]] = {
    # change_type -> {"d2_class": ..., "color": ..., "label": ...}
    "new": {"d2_class": "ChangeNew", "color": "#2E7D32", "label": "New"},
    "changed": {"d2_class": "ChangeChanged", "color": "#F9A825", "label": "Changed"},
    "removed": {"d2_class": "ChangeRemoved", "color": "#C62828", "label": "Removed"},
    "impacted": {"d2_class": "ChangeImpacted", "color": "#6A1B9A", "label": "Impacted"},
    "dependency": {"d2_class": "ChangeDependency", "color": "#546E7A", "label": "Dependency"},
    # "existing" intentionally absent: renders with pre-existing neutral styling
}

DIRECTION_STYLES: dict[str, dict[str, str]] = {
    # d2 direction class -> {"color": ..., "label": ...}; mirrors the three
    # existing Interface/InterfaceFromFocus/InterfaceToFocus hexes in
    # styles.d2 (D6 legend group "edge direction colors").
    "Interface": {"color": "#000000", "label": "Neutral"},
    "InterfaceFromFocus": {"color": "#84A1EB", "label": "From Focus"},
    "InterfaceToFocus": {"color": "#C1A2F3", "label": "To Focus"},
}

INTERACTION_TYPE_STYLES: dict[str, dict[str, str]] = {
    # normalized interaction_type -> {"d2_class": ..., "stroke_dash": ..., "stroke_width": ..., "label": ...}
    "api": {"d2_class": "IntApi", "stroke_dash": "0", "stroke_width": "3", "label": "API"},
    "event": {"d2_class": "IntEvent", "stroke_dash": "3", "stroke_width": "2", "label": "Event"},
    "queue": {"d2_class": "IntQueue", "stroke_dash": "5", "stroke_width": "2", "label": "Queue"},
    "batch": {"d2_class": "IntBatch", "stroke_dash": "8", "stroke_width": "2", "label": "Batch"},
    "file": {"d2_class": "IntFile", "stroke_dash": "1", "stroke_width": "2", "label": "File"},
    "pubsub": {"d2_class": "IntPubsub", "stroke_dash": "4", "stroke_width": "3", "label": "Pub/Sub"},
}

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_interaction_type(value: str | None) -> str | None:
    """Lowercase and strip non-alphanumerics: 'Pub/Sub' -> 'pubsub'. Return the
    key if it is in INTERACTION_TYPE_STYLES, else None (neutral fallback)."""
    if not value:
        return None
    normalized = _NON_ALPHANUMERIC.sub("", value.lower())
    if normalized in INTERACTION_TYPE_STYLES:
        return normalized
    return None
