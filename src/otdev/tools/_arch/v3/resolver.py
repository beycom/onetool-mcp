"""Temporal resolution for schema v3: state selection, revisions, clipping,
diff, and baseline advance.

Semantics reference: the Intervals, Revisions, Resolution, Diff, and
"Advancing the baseline" sections of plans/arch/arch-v3/schema.md. The
authoritative specification is tests/unit/tools/test_arch_v3_resolver.py —
where prose and tests could be read differently, the tests win.

Everything is evaluated point-wise at a single timeline position; there is no
interval arithmetic. Position ``-1`` is the current state; position ``i >= 0``
is the state *at* the timeline's ``i``-th milestone (intervals are half-open:
a row with ``until: m`` is absent at ``m``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    Architecture,
    Component,
    Interface,
    Relationship,
    Subsystem,
    System,
    User,
)

EntityRow = System | Subsystem | Component | User | Interface | Relationship

#: Collection names in canonical order. Used as the ``kind`` vocabulary
#: everywhere in this module (``Clip.kind``, ``DiffEntry.kind``,
#: ``ResolvedState.entities`` keys, ordering of diff output).
KINDS = (
    "systems",
    "subsystems",
    "components",
    "users",
    "interfaces",
    "relationships",
)

#: Kinds searched (in this order) when resolving interface provider/consumer
#: and relationship source/target endpoints. First match wins.
ENDPOINT_KINDS = ("systems", "subsystems", "components", "users")


class ResolverError(ValueError):
    """Raised for unresolvable selectors and structurally invalid revision
    groups (the resolver's minimal input contract; full validation with
    locations is validate.py's job)."""


@dataclass(frozen=True)
class StateSelector:
    """State selection per schema.md "State selection boundary".

    ``at`` is ``"current"``, a milestone id, or ``"end"`` (the last milestone
    of the timeline). ``timeline`` names a declared timeline; it may be
    omitted (None) when no timelines are declared (implicit timeline: every
    catalog milestone in catalog order) or when exactly one timeline is
    declared (that one is selected). Omitting it with several declared
    timelines is a ResolverError.
    """

    at: str = "current"
    timeline: str | None = None


@dataclass(frozen=True)
class TimelineView:
    """A concrete milestone ordering to resolve against.

    ``id`` is the declared timeline id, or None for the implicit timeline.
    ``milestones`` is the ordered milestone-id tuple.
    """

    id: str | None
    milestones: tuple[str, ...]

    def position(self, milestone_id: str) -> int:
        """0-based position of ``milestone_id`` on this timeline.

        Raises ResolverError if the milestone is not on the timeline.
        """
        try:
            return self.milestones.index(milestone_id)
        except ValueError as exc:
            timeline = self.id or "implicit timeline"
            raise ResolverError(
                f"milestone {milestone_id!r} is not on {timeline!r}"
            ) from exc

    def contains(self, milestone_id: str) -> bool:
        """True when ``milestone_id`` is on this timeline."""
        return milestone_id in self.milestones


def timeline_view(
    architecture: Architecture, timeline_id: str | None = None
) -> TimelineView:
    """Resolve ``timeline_id`` to a TimelineView.

    None selects the implicit timeline when no timelines are declared, or the
    sole declared timeline when there is exactly one; otherwise ResolverError.
    An unknown id is a ResolverError.
    """
    timelines = architecture.timelines or []
    if timeline_id is not None:
        for timeline in timelines:
            if timeline.id == timeline_id:
                return TimelineView(timeline.id, tuple(timeline.milestones))
        raise ResolverError(f"unknown timeline {timeline_id!r}")

    if not timelines:
        return TimelineView(None, tuple(item.id for item in architecture.milestones))
    if len(timelines) == 1:
        timeline = timelines[0]
        return TimelineView(timeline.id, tuple(timeline.milestones))
    raise ResolverError("timeline is required when several timelines are declared")


def resolve_position(
    architecture: Architecture, selector: StateSelector
) -> tuple[TimelineView, int]:
    """Resolve a selector to (timeline view, position).

    ``current`` -> -1. A milestone id -> its position on the selected
    timeline (ResolverError if it is not on it, or does not exist at all).
    ``end`` -> the last position, or -1 when the timeline has no milestones
    (zero-milestone architectures: end == current).
    """
    view = timeline_view(architecture, selector.timeline)
    if selector.at == "current":
        return view, -1
    if selector.at == "end":
        return view, len(view.milestones) - 1
    if selector.at not in {item.id for item in architecture.milestones}:
        raise ResolverError(f"unknown milestone {selector.at!r}")
    return view, view.position(selector.at)


@dataclass(frozen=True)
class RevisionGroup:
    """All authored rows sharing one id within one collection, in authored
    order. ``rows[0]``'s position in the authored collection defines the
    group's ordering for every deterministic output."""

    id: str
    rows: tuple[EntityRow, ...]


def group_revisions(rows: list[EntityRow]) -> dict[str, RevisionGroup]:
    """Group a collection's rows by id, enforcing the Revisions rules.

    ResolverError when: more than one row of a group omits ``from``; two rows
    of a group share a ``from`` value; or any single row has ``from`` equal
    to ``until`` (identity comparison, timeline-independent).
    The returned dict preserves first-appearance order.
    """
    grouped: dict[str, list[EntityRow]] = {}
    for row in rows:
        grouped.setdefault(row.id, []).append(row)

    result: dict[str, RevisionGroup] = {}
    for entity_id, revisions in grouped.items():
        from_values = [row.from_ for row in revisions]
        if from_values.count(None) > 1:
            raise ResolverError(
                f"revision group {entity_id!r} has more than one current row"
            )
        authored_from = [value for value in from_values if value is not None]
        if len(authored_from) != len(set(authored_from)):
            raise ResolverError(
                f"revision group {entity_id!r} repeats a from milestone"
            )
        if any(
            row.from_ is not None and row.from_ == row.until for row in revisions
        ):
            raise ResolverError(
                f"revision group {entity_id!r} has equal from and until"
            )
        result[entity_id] = RevisionGroup(entity_id, tuple(revisions))
    return result


def governing_row(
    group: RevisionGroup, view: TimelineView, position: int
) -> EntityRow | None:
    """The revision governing ``group`` at ``position``, ignoring clipping.

    Per schema.md Intervals/Revisions: a milestone not on ``view`` makes
    ``from`` = +inf (row never appears) or ``until`` = +inf (never retired);
    absent ``from`` = -inf, absent ``until`` = +inf. Among rows with
    pos(from) <= position, the newest (greatest pos(from)) is the candidate —
    a revision implicitly ends its predecessor at its ``from``. The candidate
    governs iff its own pos(until) > position; otherwise the entity is absent
    (None), even when an older revision carries no ``until``.
    """
    candidates: list[tuple[int, EntityRow]] = []
    for row in group.rows:
        if row.from_ is None:
            from_position = -1
        elif view.contains(row.from_):
            from_position = view.position(row.from_)
        else:
            continue
        if from_position <= position:
            candidates.append((from_position, row))

    if not candidates:
        return None
    _, candidate = max(candidates, key=lambda item: item[0])
    if candidate.until is None or not view.contains(candidate.until):
        return candidate
    return candidate if view.position(candidate.until) > position else None


@dataclass(frozen=True)
class Clip:
    """A derived consequence: a row authored-live at the position but not
    effectively live because of its parent chain or endpoints.

    ``clipped_by`` names the authored root cause: walk the blocking chain
    (parents for entities; provider-then-consumer / source-then-target for
    connections, taking the first endpoint that is not effectively live) and
    report the first entity whose *own authored interval* excludes the
    position; a blocking entity that is itself clipped contributes its own
    cause instead. An unresolvable parent/endpoint id is reported as the
    cause itself.
    """

    kind: str
    id: str
    clipped_by: str


@dataclass(frozen=True)
class ResolvedState:
    """The filtered architecture at one position.

    ``entities`` maps each of KINDS to the effectively-live governing rows in
    authored group order. ``clips`` lists authored-live-but-clipped rows in
    KINDS order, then authored group order.
    """

    timeline: TimelineView
    position: int
    entities: dict[str, tuple[EntityRow, ...]] = field(default_factory=dict)
    clips: tuple[Clip, ...] = ()

    def ids(self, kind: str) -> tuple[str, ...]:
        """Ids of the effectively-live rows of ``kind``, in order."""
        return tuple(row.id for row in self.entities[kind])

    def entity(self, kind: str, entity_id: str) -> EntityRow | None:
        """The effectively-live governing row, or None."""
        return next(
            (row for row in self.entities[kind] if row.id == entity_id), None
        )


def resolve(
    architecture: Architecture, selector: StateSelector | None = None
) -> ResolvedState:
    """Resolve the state selected by ``selector`` (default: current).

    Effective liveness per schema.md Resolution: an entity is effectively
    live only while its parent chain (component -> subsystem -> system) is
    effectively live; an interface/relationship only while both endpoints
    are effectively live (endpoint lookup over ENDPOINT_KINDS, first match).
    Rows authored-live but not effectively live appear in ``clips``, not in
    ``entities``.
    """
    selector = selector or StateSelector()
    view, position = resolve_position(architecture, selector)
    groups: dict[str, dict[str, RevisionGroup]] = {}
    authored: dict[str, dict[str, EntityRow]] = {}

    for kind in KINDS:
        kind_groups = group_revisions(list(getattr(architecture, kind)))
        groups[kind] = kind_groups
        authored[kind] = {
            entity_id: row
            for entity_id, group in kind_groups.items()
            if (row := governing_row(group, view, position)) is not None
        }

    effective: dict[str, dict[str, EntityRow]] = {kind: {} for kind in KINDS}
    clip_causes: dict[tuple[str, str], str] = {}

    def blocked_by(kind: str, entity_id: str) -> str | None:
        if entity_id in effective[kind]:
            return None
        return clip_causes.get((kind, entity_id), entity_id)

    def endpoint_kind(entity_id: str) -> str | None:
        return next(
            (kind for kind in ENDPOINT_KINDS if entity_id in groups[kind]), None
        )

    effective["systems"].update(authored["systems"])

    for entity_id, row in authored["subsystems"].items():
        cause = blocked_by("systems", row.system)
        if cause is None:
            effective["subsystems"][entity_id] = row
        else:
            clip_causes[("subsystems", entity_id)] = cause

    for entity_id, row in authored["components"].items():
        cause = blocked_by("subsystems", row.subsystem)
        if cause is None:
            effective["components"][entity_id] = row
        else:
            clip_causes[("components", entity_id)] = cause

    effective["users"].update(authored["users"])

    def connection_cause(endpoint_ids: tuple[str, str]) -> str | None:
        for endpoint_id in endpoint_ids:
            kind = endpoint_kind(endpoint_id)
            if kind is None:
                return endpoint_id
            cause = blocked_by(kind, endpoint_id)
            if cause is not None:
                return cause
        return None

    for entity_id, row in authored["interfaces"].items():
        cause = connection_cause((row.provider, row.consumer))
        if cause is None:
            effective["interfaces"][entity_id] = row
        else:
            clip_causes[("interfaces", entity_id)] = cause

    for entity_id, row in authored["relationships"].items():
        cause = connection_cause((row.source, row.target))
        if cause is None:
            effective["relationships"][entity_id] = row
        else:
            clip_causes[("relationships", entity_id)] = cause

    entities = {
        kind: tuple(effective[kind].values())
        for kind in KINDS
    }
    clips = tuple(
        Clip(kind, entity_id, clip_causes[(kind, entity_id)])
        for kind in KINDS
        for entity_id in groups[kind]
        if (kind, entity_id) in clip_causes
    )
    return ResolvedState(view, position, entities, clips)


@dataclass(frozen=True)
class FieldChange:
    """One field-level difference between two governing revisions. For
    ``properties``, one entry per key, named ``properties.<key>`` (old/new
    None when the key is added/removed); ``tags`` compares as a whole list.
    ``id``, ``from``, and ``until`` are never reported."""

    field: str
    old: object
    new: object


@dataclass(frozen=True)
class DiffEntry:
    """An added or removed entity. ``name`` is the row's display name (the
    ``action`` for relationships). ``clipped_by`` is set on removed entries
    whose absence at ``b`` is a clip (derived consequence), else None."""

    kind: str
    id: str
    name: str
    clipped_by: str | None = None


@dataclass(frozen=True)
class ChangedEntry:
    """An entity live at both states via different revision rows whose
    content differs. Groups with differing rows but identical content fields
    are not reported."""

    kind: str
    id: str
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class Diff:
    """Set arithmetic over two resolved states (schema.md Diff). All three
    tuples are ordered by KINDS, then authored group order."""

    added: tuple[DiffEntry, ...]
    removed: tuple[DiffEntry, ...]
    changed: tuple[ChangedEntry, ...]


def diff(
    architecture: Architecture, a: StateSelector, b: StateSelector
) -> Diff:
    """Diff the states selected by ``a`` (origin) and ``b``."""
    state_a = resolve(architecture, a)
    state_b = resolve(architecture, b)
    clips_b = {(clip.kind, clip.id): clip.clipped_by for clip in state_b.clips}
    added: list[DiffEntry] = []
    removed: list[DiffEntry] = []
    changed: list[ChangedEntry] = []

    def display_name(row: EntityRow) -> str:
        return row.action if isinstance(row, Relationship) else row.name

    def field_changes(old: EntityRow, new: EntityRow) -> tuple[FieldChange, ...]:
        changes: list[FieldChange] = []
        excluded = {"id", "from_", "until", "properties"}
        for field_name in type(old).model_fields:
            if field_name in excluded:
                continue
            old_value = getattr(old, field_name)
            new_value = getattr(new, field_name)
            if old_value != new_value:
                changes.append(FieldChange(field_name, old_value, new_value))

        property_keys = list(old.properties)
        property_keys.extend(key for key in new.properties if key not in old.properties)
        for key in property_keys:
            old_value = old.properties.get(key)
            new_value = new.properties.get(key)
            if old_value != new_value:
                changes.append(
                    FieldChange(f"properties.{key}", old_value, new_value)
                )
        return tuple(changes)

    for kind in KINDS:
        rows_a = {row.id: row for row in state_a.entities[kind]}
        rows_b = {row.id: row for row in state_b.entities[kind]}
        group_order = group_revisions(list(getattr(architecture, kind)))
        for entity_id in group_order:
            old = rows_a.get(entity_id)
            new = rows_b.get(entity_id)
            if old is None and new is not None:
                added.append(DiffEntry(kind, entity_id, display_name(new)))
            elif old is not None and new is None:
                removed.append(
                    DiffEntry(
                        kind,
                        entity_id,
                        display_name(old),
                        clips_b.get((kind, entity_id)),
                    )
                )
            elif old is not None and new is not None and old is not new:
                changes = field_changes(old, new)
                if changes:
                    changed.append(ChangedEntry(kind, entity_id, changes))

    return Diff(tuple(added), tuple(removed), tuple(changed))


def advance(architecture: Architecture, through: str) -> Architecture:
    """Return a new Architecture with the baseline advanced through
    ``through`` (a catalog milestone id; ResolverError if unknown).

    Let D be the delivered set: every milestone at or before ``through`` in
    catalog order. Per schema.md "Advancing the baseline":

    - rows whose ``until`` is in D are deleted;
    - remaining ``from`` markers in D are removed (rows become current);
    - superseded revisions are dropped: among a group's rows whose ``from``
      is in D or absent, only the one with the greatest catalog position of
      ``from`` (absent = -inf) is kept — unless already deleted by its
      ``until``; rows whose ``from`` is not in D are kept untouched;
    - milestones in D are removed from the catalog and from every timeline;
      a timeline left with no milestones is dropped, and ``timelines``
      becomes None when none remain.

    The input architecture is not mutated. Authored row order is preserved.
    """
    catalog_positions = {
        milestone.id: index for index, milestone in enumerate(architecture.milestones)
    }
    if through not in catalog_positions:
        raise ResolverError(f"unknown milestone {through!r}")
    delivered = {
        milestone.id
        for milestone in architecture.milestones[: catalog_positions[through] + 1]
    }

    updates: dict[str, object] = {
        "milestones": [
            milestone.model_copy(deep=True)
            for milestone in architecture.milestones
            if milestone.id not in delivered
        ]
    }

    if architecture.timelines:
        timelines = []
        for timeline in architecture.timelines:
            remaining = [
                milestone for milestone in timeline.milestones if milestone not in delivered
            ]
            if remaining:
                timelines.append(
                    timeline.model_copy(update={"milestones": remaining}, deep=True)
                )
        updates["timelines"] = timelines or None
    else:
        updates["timelines"] = None

    for kind in KINDS:
        rows: list[EntityRow] = list(getattr(architecture, kind))
        groups = group_revisions(rows)
        keep_current: dict[str, EntityRow] = {}
        for entity_id, group in groups.items():
            eligible = [
                row
                for row in group.rows
                if row.until not in delivered
                and (row.from_ is None or row.from_ in delivered)
            ]
            if eligible:
                keep_current[entity_id] = max(
                    eligible,
                    key=lambda row: (
                        -1
                        if row.from_ is None
                        else catalog_positions.get(row.from_, len(catalog_positions))
                    ),
                )

        rewritten: list[EntityRow] = []
        for row in rows:
            if row.until in delivered:
                continue
            if row.from_ is None or row.from_ in delivered:
                if keep_current.get(row.id) is not row:
                    continue
                rewritten.append(row.model_copy(update={"from_": None}, deep=True))
            else:
                rewritten.append(row.model_copy(deep=True))
        updates[kind] = rewritten

    return architecture.model_copy(update=updates, deep=True)
