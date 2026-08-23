"""Deterministic report payload compilation for architecture schema v3."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .resolver import (
    KINDS,
    StateSelector,
    governing_row,
    group_revisions,
    resolve,
    timeline_view,
)

if TYPE_CHECKING:
    from .model import Architecture, StrictModel


def _serialize(item: StrictModel) -> dict[str, Any]:
    value = item.model_dump(by_alias=True, exclude_none=True, mode="json")
    for field in ("tags", "properties"):
        if not value.get(field):
            value.pop(field, None)
    for field in ("call_direction", "data_flow"):
        if value.get(field) == "unspecified":
            value.pop(field)
    return value


def _live_segments(positions: list[int], last: int) -> list[list[int | None]]:
    if not positions:
        return []
    segments: list[list[int | None]] = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position != previous + 1:
            segments.append([start, previous + 1])
            start = position
        previous = position
    segments.append([start, None if previous == last else previous + 1])
    return segments


def _clip_segments(
    positions: list[tuple[int, str]], last: int
) -> list[dict[str, int | str | None]]:
    if not positions:
        return []
    segments: list[dict[str, int | str | None]] = []
    start = previous = positions[0][0]
    cause = positions[0][1]
    for position, next_cause in positions[1:]:
        if position != previous + 1 or next_cause != cause:
            segments.append(
                {"start": start, "end": previous + 1, "by": cause}
            )
            start, cause = position, next_cause
        previous = position
    segments.append(
        {"start": start, "end": None if previous == last else previous + 1, "by": cause}
    )
    return segments


def build_payload(architecture: Architecture, source_name: str) -> dict[str, Any]:
    """Compile an architecture into the ``arch-report/v1`` payload."""
    timelines = architecture.timelines or []
    materialized = (
        [{"id": item.id, "milestones": list(item.milestones)} for item in timelines]
        if timelines
        else [
            {
                "id": None,
                "milestones": [item.id for item in architecture.milestones],
            }
        ]
    )
    rows = {kind: list(getattr(architecture, kind)) for kind in KINDS}
    groups = {kind: group_revisions(rows[kind]) for kind in KINDS}
    indices = {
        kind: {id(row): index for index, row in enumerate(rows[kind])} for kind in KINDS
    }
    live: dict[str, list[list[list[int]]]] = {
        kind: [[[] for _ in materialized] for _ in rows[kind]] for kind in KINDS
    }
    clips: dict[str, list[list[list[tuple[int, str]]]]] = {
        kind: [[[] for _ in materialized] for _ in rows[kind]] for kind in KINDS
    }

    for timeline_index, item in enumerate(materialized):
        view = timeline_view(architecture, item["id"])
        selectors = ["current", *view.milestones]
        for payload_position, at in enumerate(selectors):
            state = resolve(architecture, StateSelector(at=at, timeline=view.id))
            clip_causes = {(clip.kind, clip.id): clip.clipped_by for clip in state.clips}
            effective = {
                kind: {id(row) for row in state.entities[kind]} for kind in KINDS
            }
            for kind in KINDS:
                for group in groups[kind].values():
                    row = governing_row(group, state.timeline, state.position)
                    if row is None:
                        continue
                    row_index = indices[kind][id(row)]
                    if id(row) in effective[kind]:
                        live[kind][row_index][timeline_index].append(payload_position)
                    elif cause := clip_causes.get((kind, group.id)):
                        clips[kind][row_index][timeline_index].append(
                            (payload_position, cause)
                        )

    serialized_rows: dict[str, list[dict[str, Any]]] = {}
    for kind in KINDS:
        serialized_rows[kind] = []
        for row_index, row in enumerate(rows[kind]):
            value = _serialize(row)
            value["intervals"] = [
                {
                    "live": _live_segments(
                        live[kind][row_index][timeline_index],
                        len(item["milestones"]),
                    ),
                    "clips": _clip_segments(
                        clips[kind][row_index][timeline_index],
                        len(item["milestones"]),
                    ),
                }
                for timeline_index, item in enumerate(materialized)
            ]
            serialized_rows[kind].append(value)

    return {
        "payload": "arch-report/v1",
        "schema_version": 3,
        "source": Path(source_name).name,
        "milestones": [_serialize(item) for item in architecture.milestones],
        "timelines": materialized,
        "rows": serialized_rows,
    }
