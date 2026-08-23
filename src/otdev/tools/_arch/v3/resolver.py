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
        raise NotImplementedError

    def contains(self, milestone_id: str) -> bool:
        """True when ``milestone_id`` is on this timeline."""
        raise NotImplementedError


def timeline_view(
    architecture: Architecture, timeline_id: str | None = None
) -> TimelineView:
    """Resolve ``timeline_id`` to a TimelineView.

    None selects the implicit timeline when no timelines are declared, or the
    sole declared timeline when there is exactly one; otherwise ResolverError.
    An unknown id is a ResolverError.
    """
    raise NotImplementedError


def resolve_position(
    architecture: Architecture, selector: StateSelector
) -> tuple[TimelineView, int]:
    """Resolve a selector to (timeline view, position).

    ``current`` -> -1. A milestone id -> its position on the selected
    timeline (ResolverError if it is not on it, or does not exist at all).
    ``end`` -> the last position, or -1 when the timeline has no milestones
    (zero-milestone architectures: end == current).
    """
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
        raise NotImplementedError

    def entity(self, kind: str, entity_id: str) -> EntityRow | None:
        """The effectively-live governing row, or None."""
        raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError
