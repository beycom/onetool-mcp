"""Structural and advisory validation for architecture schema v3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from .model import Architecture, Interface, Relationship
from .resolver import (
    ENDPOINT_KINDS,
    KINDS,
    EntityRow,
    ResolverError,
    StateSelector,
    governing_row,
    group_revisions,
    resolve,
    timeline_view,
)
from .yamlio import DataPath, format_data_path, source_location

Severity = Literal["error", "warning"]
THEME_KINDS = {"system", "subsystem", "container", "component", "code", "user"}
COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?\Z")
LAYOUT_METHODS = {"layered", "radial", "grid"}
LAYOUT_DIRECTIONS = {"right", "down"}
LAYOUT_KEYS = {"method", "direction", "spacing", "ranking", "user_choice"}
LAYOUT_SPACING_KEYS = {"node", "layer", "boundary"}


@dataclass(frozen=True)
class Finding:
    """One validation result with a stable code and source location."""

    severity: Severity
    code: str
    message: str
    file: str
    line: int
    column: int
    path: str


def _finding(
    architecture: Architecture,
    severity: Severity,
    code: str,
    message: str,
    path: DataPath,
) -> Finding:
    file, mark = source_location(architecture, path)
    return Finding(
        severity=severity,
        code=code,
        message=message,
        file=str(file) if file is not None else "<memory>",
        line=mark[0] if mark is not None else 1,
        column=mark[1] if mark is not None else 1,
        path=format_data_path(path),
    )


def _required_findings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    for kind in ("milestones", "timelines", *KINDS):
        for index, row in enumerate(getattr(architecture, kind, None) or []):
            for field_name, field in type(row).model_fields.items():
                value = getattr(row, field_name, None)
                if field.is_required() and (value is None or value == ""):
                    alias = field.alias or field_name
                    findings.append(
                        _finding(
                            architecture,
                            "error",
                            "missing_required",
                            f"required field {alias!r} is missing",
                            (kind, index, alias),
                        )
                    )
    return findings


def _theme_findings(architecture: Architecture) -> list[Finding]:
    if architecture.theme is None:
        return []
    findings: list[Finding] = []
    for key, value in architecture.theme.kinds.items():
        path = ("theme", "kinds", key)
        if key not in THEME_KINDS:
            findings.append(
                _finding(
                    architecture,
                    "error",
                    "unknown_theme_key",
                    f"theme kind {key!r} is not supported",
                    path,
                )
            )
        if not isinstance(value, str) or COLOR_PATTERN.fullmatch(value) is None:
            findings.append(
                _finding(
                    architecture,
                    "error",
                    "invalid_color",
                    f"theme color for {key!r} must be #RGB or #RRGGBB",
                    path,
                )
            )
    return findings


def _layout_findings(architecture: Architecture) -> list[Finding]:
    if architecture.layout is None:
        return []
    values = architecture.layout.model_dump(mode="python", exclude_none=True)
    findings: list[Finding] = []

    def warn(code: str, message: str, path: DataPath) -> None:
        findings.append(_finding(architecture, "warning", code, message, path))

    for key in values.keys() - LAYOUT_KEYS:
        warn(
            "unknown_layout_key",
            f"layout key {key!r} is not supported",
            ("layout", key),
        )
    method = values.get("method")
    if method is not None and (
        not isinstance(method, str) or method not in LAYOUT_METHODS
    ):
        warn(
            "invalid_layout_value",
            "layout method must be layered, radial, or grid",
            ("layout", "method"),
        )
    direction = values.get("direction")
    if direction is not None and (
        not isinstance(direction, str) or direction not in LAYOUT_DIRECTIONS
    ):
        warn(
            "invalid_layout_value",
            "layout direction must be right or down",
            ("layout", "direction"),
        )
    ranking = values.get("ranking")
    if ranking is not None and not (
        ranking == "auto"
        or (
            isinstance(ranking, str)
            and ranking.startswith("property:")
            and bool(ranking.removeprefix("property:"))
        )
    ):
        warn(
            "invalid_layout_value",
            "layout ranking must be auto or property:<name>",
            ("layout", "ranking"),
        )
    user_choice = values.get("user_choice")
    if user_choice is not None and not isinstance(user_choice, bool):
        warn(
            "invalid_layout_value",
            "layout user_choice must be a boolean",
            ("layout", "user_choice"),
        )
    spacing = values.get("spacing")
    if spacing is not None and not isinstance(spacing, dict):
        warn(
            "invalid_layout_value",
            "layout spacing must be a mapping",
            ("layout", "spacing"),
        )
    elif isinstance(spacing, dict):
        for key in spacing.keys() - LAYOUT_SPACING_KEYS:
            warn(
                "unknown_layout_key",
                f"layout spacing key {key!r} is not supported",
                ("layout", "spacing", key),
            )
        for key in LAYOUT_SPACING_KEYS & spacing.keys():
            value = spacing[key]
            if type(value) is not int or value <= 0:
                warn(
                    "invalid_layout_value",
                    f"layout spacing {key!r} must be a positive integer",
                    ("layout", "spacing", key),
                )
    return findings


def _duplicate_findings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    for kind in ("milestones", "timelines"):
        seen: set[str] = set()
        for index, row in enumerate(getattr(architecture, kind) or []):
            if row.id in seen:
                findings.append(
                    _finding(
                        architecture,
                        "error",
                        "duplicate_id",
                        f"{kind} repeats id {row.id!r}",
                        (kind, index, "id"),
                    )
                )
            seen.add(row.id)
    for kind in KINDS:
        grouped: dict[str, list[tuple[int, EntityRow]]] = {}
        for index, row in enumerate(getattr(architecture, kind)):
            grouped.setdefault(row.id, []).append((index, row))
        for entity_id, indexed_rows in grouped.items():
            if len(indexed_rows) < 2:
                continue
            start_values = [
                None if row.start_in in (None, "base") else row.start_in
                for _, row in indexed_rows
            ]
            valid = start_values.count(None) <= 1 and len(start_values) == len(
                set(start_values)
            )
            if not valid:
                index = indexed_rows[1][0]
                findings.append(
                    _finding(
                        architecture,
                        "error",
                        "duplicate_id",
                        f"{kind} id {entity_id!r} is not a valid revision group",
                        (kind, index, "id"),
                    )
                )
    return findings


def _reference_findings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    identity = {kind: {row.id for row in getattr(architecture, kind)} for kind in KINDS}
    endpoints = set().union(*(identity[kind] for kind in ENDPOINT_KINDS))
    milestone_ids = {milestone.id for milestone in architecture.milestones}
    for kind in KINDS:
        for index, row in enumerate(getattr(architecture, kind)):
            references: list[tuple[str, str, set[str], str]] = []
            if kind == "subsystems":
                references.append(
                    ("parent", row.parent, identity["systems"], "unresolved_parent")
                )
            elif kind == "containers":
                parent_kinds = [
                    parent_kind
                    for parent_kind in ("systems", "subsystems")
                    if row.parent in identity[parent_kind]
                ]
                if len(parent_kinds) > 1:
                    findings.append(
                        _finding(
                            architecture,
                            "error",
                            "ambiguous_parent",
                            f"parent {row.parent!r} matches a system and subsystem",
                            (kind, index, "parent"),
                        )
                    )
                elif not parent_kinds:
                    references.append(
                        ("parent", row.parent, set(), "unresolved_parent")
                    )
            elif kind == "components":
                references.append(
                    (
                        "container",
                        row.container,
                        identity["containers"],
                        "unresolved_parent",
                    )
                )
            elif kind == "code":
                references.append(
                    (
                        "component",
                        row.component,
                        identity["components"],
                        "unresolved_parent",
                    )
                )
            elif isinstance(row, Interface):
                references.extend(
                    [
                        ("provider", row.provider, endpoints, "unresolved_endpoint"),
                        ("consumer", row.consumer, endpoints, "unresolved_endpoint"),
                    ]
                )
            elif isinstance(row, Relationship):
                references.extend(
                    [
                        ("source", row.source, endpoints, "unresolved_endpoint"),
                        ("target", row.target, endpoints, "unresolved_endpoint"),
                    ]
                )
            for field, value, valid_ids, code in references:
                if value not in valid_ids:
                    findings.append(
                        _finding(
                            architecture,
                            "error",
                            code,
                            f"{field} references unknown identity {value!r}",
                            (kind, index, field),
                        )
                    )
            for field, value in (("start_in", row.start_in), ("end_in", row.end_in)):
                if value is not None and value != "base" and value not in milestone_ids:
                    findings.append(
                        _finding(
                            architecture,
                            "error",
                            "unresolved_milestone",
                            f"{field} references unknown milestone {value!r}",
                            (kind, index, field),
                        )
                    )
    return findings


def _temporal_findings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    timeline_orders = (
        [timeline.milestones for timeline in architecture.timelines]
        if architecture.timelines
        else [[milestone.id for milestone in architecture.milestones]]
    )
    milestone_ids = {milestone.id for milestone in architecture.milestones}
    for index, timeline in enumerate(architecture.timelines or []):
        invalid = (
            not timeline.milestones
            or len(timeline.milestones) != len(set(timeline.milestones))
            or any(item not in milestone_ids for item in timeline.milestones)
        )
        if invalid:
            findings.append(
                _finding(
                    architecture,
                    "error",
                    "invalid_timeline",
                    f"timeline {timeline.id!r} must contain unique, resolvable milestones",
                    ("timelines", index, "milestones"),
                )
            )
    for kind in KINDS:
        for index, row in enumerate(getattr(architecture, kind)):
            if row.start_in is None or row.end_in is None:
                continue
            invalid = any(
                row.start_in in ["base", *order]
                and row.end_in in ["base", *order]
                and ["base", *order].index(row.start_in)
                > ["base", *order].index(row.end_in)
                for order in timeline_orders
            )
            if invalid:
                findings.append(
                    _finding(
                        architecture,
                        "error",
                        "invalid_interval",
                        f"interval [{row.start_in}, {row.end_in}] is not ordered",
                        (kind, index, "start_in"),
                    )
                )
    return findings


def _revision_warnings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    for kind in KINDS:
        groups: dict[str, list[tuple[int, EntityRow]]] = {}
        for index, row in enumerate(getattr(architecture, kind)):
            groups.setdefault(row.id, []).append((index, row))
        for entity_id, rows in groups.items():
            for (previous_index, previous), (index, row) in pairwise(rows):
                old = previous.model_dump(exclude={"start_in", "end_in"})
                new = row.model_dump(exclude={"start_in", "end_in"})
                if old == new:
                    findings.append(
                        _finding(
                            architecture,
                            "warning",
                            "identical_revision",
                            f"revision {entity_id!r} repeats row {previous_index}",
                            (kind, index, "id"),
                        )
                    )
    return findings


def _resolution_warnings(architecture: Architecture) -> list[Finding]:
    findings: list[Finding] = []
    live: dict[str, set[str]] = {kind: set() for kind in KINDS}
    clipped_rows: set[tuple[str, int]] = set()
    timeline_ids: list[str | None] = [
        timeline.id for timeline in architecture.timelines or []
    ] or [None]
    try:
        groups = {
            kind: group_revisions(list(getattr(architecture, kind))) for kind in KINDS
        }
        for timeline_id in timeline_ids:
            view = timeline_view(architecture, timeline_id)
            selectors = [StateSelector("base", timeline_id)] + [
                StateSelector(milestone, timeline_id) for milestone in view.milestones
            ]
            for selector in selectors:
                state = resolve(architecture, selector)
                for kind in KINDS:
                    live[kind].update(row.id for row in state.entities[kind])
                for clip in state.clips:
                    row = governing_row(
                        groups[clip.kind][clip.id], state.timeline, state.position
                    )
                    if row is not None:
                        index = next(
                            i
                            for i, candidate in enumerate(
                                getattr(architecture, clip.kind)
                            )
                            if candidate is row
                        )
                        clipped_rows.add((clip.kind, index))
    except ResolverError:
        return findings
    for kind, index in sorted(
        clipped_rows, key=lambda item: (KINDS.index(item[0]), item[1])
    ):
        row = getattr(architecture, kind)[index]
        findings.append(
            _finding(
                architecture,
                "warning",
                "interval_clipped",
                f"authored interval for {row.id!r} exceeds effective liveness",
                (kind, index, "id"),
            )
        )
    for kind in KINDS:
        seen: set[str] = set()
        for index, row in enumerate(getattr(architecture, kind)):
            if row.id not in seen and row.id not in live[kind]:
                findings.append(
                    _finding(
                        architecture,
                        "warning",
                        "never_live",
                        f"{kind} identity {row.id!r} is live on no timeline",
                        (kind, index, "id"),
                    )
                )
            seen.add(row.id)
    return findings


def validate(architecture: Architecture) -> list[Finding]:
    """Return all structural errors and advisory warnings."""
    findings = _required_findings(architecture)
    findings.extend(_theme_findings(architecture))
    findings.extend(_layout_findings(architecture))
    findings.extend(_duplicate_findings(architecture))
    findings.extend(_reference_findings(architecture))
    findings.extend(_temporal_findings(architecture))
    findings.extend(_revision_warnings(architecture))
    findings.extend(_resolution_warnings(architecture))
    referenced = {
        value
        for kind in KINDS
        for row in getattr(architecture, kind)
        for value in (row.start_in, row.end_in)
        if value not in (None, "base")
    }
    for index, milestone in enumerate(architecture.milestones):
        if milestone.id == "base":
            findings.append(
                _finding(
                    architecture,
                    "error",
                    "reserved_milestone",
                    "milestone id 'base' is reserved",
                    ("milestones", index, "id"),
                )
            )
        if milestone.id not in referenced:
            findings.append(
                _finding(
                    architecture,
                    "warning",
                    "unused_milestone",
                    f"milestone {milestone.id!r} is referenced by no row",
                    ("milestones", index, "id"),
                )
            )
    return findings
