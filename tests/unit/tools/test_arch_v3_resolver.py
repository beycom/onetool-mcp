"""Authoritative semantics suite for the v3 resolver (the D3 specification).

READ-ONLY for executors: implementation must make these pass unchanged. The
helpers build minimal architectures inline; every assertion is part of the
contract, including ordering and error types.
"""

from __future__ import annotations

import pytest

from otdev.tools._arch.v3.model import Architecture
from otdev.tools._arch.v3.resolver import (
    Diff,
    ResolverError,
    StateSelector,
    advance,
    diff,
    group_revisions,
    resolve,
    resolve_position,
    timeline_view,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def build(**collections) -> Architecture:
    """Build an Architecture from collection lists of plain dicts.

    ``milestones`` entries may be bare id strings. All collections default
    to empty.
    """
    milestones = [
        {"id": m, "name": m.title()} if isinstance(m, str) else m
        for m in collections.pop("milestones", [])
    ]
    data = {
        "schema_version": 3,
        "milestones": milestones,
        "systems": [],
        "subsystems": [],
        "components": [],
        "users": [],
        "interfaces": [],
        "relationships": [],
    }
    data.update(collections)
    return Architecture.model_validate(data)


def sel(at: str = "current", timeline: str | None = None) -> StateSelector:
    return StateSelector(at=at, timeline=timeline)


# ---------------------------------------------------------------- selectors


class TestSelectors:
    def test_implicit_timeline_is_catalog_order(self) -> None:
        arch = build(milestones=["m1", "m2", "m3"])
        view = timeline_view(arch)
        assert view.id is None
        assert view.milestones == ("m1", "m2", "m3")

    @pytest.mark.parametrize(
        ("at", "position"),
        [("current", -1), ("m1", 0), ("m2", 1), ("m3", 2), ("end", 2)],
    )
    def test_position_resolution(self, at: str, position: int) -> None:
        arch = build(milestones=["m1", "m2", "m3"])
        _, pos = resolve_position(arch, sel(at))
        assert pos == position

    def test_end_equals_current_with_zero_milestones(self) -> None:
        arch = build(systems=[{"id": "s", "name": "S"}])
        _, pos = resolve_position(arch, sel("end"))
        assert pos == -1
        assert resolve(arch, sel("end")).ids("systems") == ("s",)

    def test_declared_timeline_selected_by_id(self) -> None:
        arch = build(
            milestones=["m1", "m2", "m3"],
            timelines=[
                {"id": "a", "milestones": ["m1", "m3"]},
                {"id": "b", "milestones": ["m2"]},
            ],
        )
        view, pos = resolve_position(arch, sel("m3", timeline="a"))
        assert view.id == "a"
        assert view.milestones == ("m1", "m3")
        assert pos == 1

    def test_sole_declared_timeline_is_default(self) -> None:
        arch = build(
            milestones=["m1", "m2"],
            timelines=[{"id": "only", "milestones": ["m2"]}],
        )
        view, pos = resolve_position(arch, sel("end"))
        assert view.id == "only"
        assert pos == 0

    def test_omitted_timeline_ambiguous_when_several_declared(self) -> None:
        arch = build(
            milestones=["m1"],
            timelines=[
                {"id": "a", "milestones": ["m1"]},
                {"id": "b", "milestones": ["m1"]},
            ],
        )
        with pytest.raises(ResolverError):
            resolve_position(arch, sel("m1"))

    @pytest.mark.parametrize(
        ("at", "timeline"),
        [
            ("m2", "a"),  # exists in catalog, not on this timeline
            ("nope", None),  # unknown milestone
            ("m1", "ghost"),  # unknown timeline
        ],
    )
    def test_unresolvable_selectors(self, at: str, timeline: str | None) -> None:
        arch = build(
            milestones=["m1", "m2"],
            timelines=[{"id": "a", "milestones": ["m1"]}],
        )
        with pytest.raises(ResolverError):
            resolve_position(arch, sel(at, timeline=timeline))


# ------------------------------------------------------- authored liveness


class TestAuthoredLiveness:
    @pytest.mark.parametrize(
        ("row", "live_at"),
        [
            ({"id": "s", "name": "S"}, {"current": True, "m1": True, "m2": True}),
            (
                {"id": "s", "name": "S", "from": "m1"},
                {"current": False, "m1": True, "m2": True},
            ),
            (  # half-open: absent AT the until milestone
                {"id": "s", "name": "S", "until": "m2"},
                {"current": True, "m1": True, "m2": False},
            ),
            (
                {"id": "s", "name": "S", "from": "m1", "until": "m2"},
                {"current": False, "m1": True, "m2": False},
            ),
        ],
    )
    def test_interval_filter(self, row: dict, live_at: dict[str, bool]) -> None:
        arch = build(milestones=["m1", "m2"], systems=[row])
        for at, expected in live_at.items():
            state = resolve(arch, sel(at))
            assert (state.ids("systems") == ("s",)) is expected, at

    def test_off_timeline_from_never_appears(self) -> None:
        arch = build(
            milestones=["m1", "m2"],
            timelines=[
                {"id": "a", "milestones": ["m1"]},
                {"id": "b", "milestones": ["m2"]},
            ],
            systems=[{"id": "s", "name": "S", "from": "m2"}],
        )
        assert resolve(arch, sel("end", timeline="a")).ids("systems") == ()
        assert resolve(arch, sel("m2", timeline="b")).ids("systems") == ("s",)

    def test_off_timeline_until_never_retires(self) -> None:
        arch = build(
            milestones=["m1", "m2"],
            timelines=[
                {"id": "a", "milestones": ["m1"]},
                {"id": "b", "milestones": ["m2"]},
            ],
            systems=[{"id": "s", "name": "S", "until": "m2"}],
        )
        assert resolve(arch, sel("end", timeline="a")).ids("systems") == ("s",)
        assert resolve(arch, sel("m2", timeline="b")).ids("systems") == ()


# --------------------------------------------------------------- revisions


class TestRevisions:
    def _arch(self) -> Architecture:
        return build(
            milestones=["m1", "m2"],
            systems=[{"id": "host", "name": "Host"}],
            subsystems=[
                {"id": "api", "name": "API", "system": "host"},
                {
                    "id": "api",
                    "name": "API v2",
                    "system": "host",
                    "from": "m1",
                },
            ],
        )

    def test_governing_row_switches_at_revision_from(self) -> None:
        arch = self._arch()
        assert resolve(arch, sel("current")).entity("subsystems", "api").name == "API"
        assert resolve(arch, sel("m1")).entity("subsystems", "api").name == "API v2"
        assert resolve(arch, sel("m2")).entity("subsystems", "api").name == "API v2"

    def test_newest_row_governs_death_despite_open_base(self) -> None:
        # base has no until; the revision does — after its until the entity
        # is absent (the base was implicitly ended at m1 and never returns).
        arch = build(
            milestones=["m1", "m2"],
            systems=[
                {"id": "s", "name": "S"},
                {"id": "s", "name": "S2", "from": "m1", "until": "m2"},
            ],
        )
        assert resolve(arch, sel("m2")).ids("systems") == ()

    def test_gap_reintroduction(self) -> None:
        # absent for a span, then reintroduced with the same identity
        arch = build(
            milestones=["m1", "m2", "m3"],
            systems=[
                {"id": "s", "name": "S", "until": "m1"},
                {"id": "s", "name": "S back", "from": "m3"},
            ],
        )
        assert resolve(arch, sel("current")).ids("systems") == ("s",)
        assert resolve(arch, sel("m1")).ids("systems") == ()
        assert resolve(arch, sel("m2")).ids("systems") == ()
        assert resolve(arch, sel("m3")).entity("systems", "s").name == "S back"

    def test_off_timeline_revision_never_takes_over(self) -> None:
        arch = build(
            milestones=["m1", "m2"],
            timelines=[
                {"id": "a", "milestones": ["m2"]},
                {"id": "b", "milestones": ["m1", "m2"]},
            ],
            systems=[
                {"id": "s", "name": "Old"},
                {"id": "s", "name": "New", "from": "m1"},
            ],
        )
        # on timeline a, m1 does not exist: the base governs forever
        assert resolve(arch, sel("end", timeline="a")).entity("systems", "s").name == "Old"
        assert resolve(arch, sel("end", timeline="b")).entity("systems", "s").name == "New"

    @pytest.mark.parametrize(
        "rows",
        [
            # two rows omitting from
            [{"id": "s", "name": "A"}, {"id": "s", "name": "B"}],
            # duplicate from values
            [
                {"id": "s", "name": "A", "from": "m1"},
                {"id": "s", "name": "B", "from": "m1"},
            ],
            # from == until on one row
            [{"id": "s", "name": "A", "from": "m1", "until": "m1"}],
        ],
    )
    def test_invalid_revision_groups_rejected(self, rows: list[dict]) -> None:
        arch = build(milestones=["m1"], systems=rows)
        with pytest.raises(ResolverError):
            group_revisions(list(arch.systems))


# ---------------------------------------------------------------- clipping


def _tree_arch() -> Architecture:
    """A retiring system tree plus an outside consumer of it."""
    return build(
        milestones=["m1", "m2"],
        systems=[
            {"id": "legacy", "name": "Legacy", "until": "m1"},
            {"id": "shop", "name": "Shop"},
        ],
        subsystems=[
            {"id": "legacy-core", "name": "Core", "system": "legacy"},
            {"id": "shop-api", "name": "Shop API", "system": "shop"},
        ],
        components=[
            {"id": "legacy-db", "name": "DB", "subsystem": "legacy-core"},
        ],
        users=[{"id": "ops", "name": "Ops", "until": "m2"}],
        interfaces=[
            {
                "id": "shop-to-legacy",
                "name": "Query legacy",
                "provider": "legacy-db",
                "consumer": "shop-api",
            },
            {
                "id": "ops-uses-shop",
                "name": "Operate shop",
                "provider": "shop-api",
                "consumer": "ops",
            },
        ],
        relationships=[
            {
                "id": "ops-owns-legacy",
                "action": "owns",
                "source": "ops",
                "target": "legacy-core",
            },
        ],
    )


class TestClipping:
    def test_chain_clips_to_authored_root_cause(self) -> None:
        state = resolve(_tree_arch(), sel("m1"))
        assert state.ids("systems") == ("shop",)
        assert state.ids("subsystems") == ("shop-api",)
        assert state.ids("components") == ()
        assert state.ids("interfaces") == ("ops-uses-shop",)
        assert state.ids("relationships") == ()
        clipped = {(c.kind, c.id): c.clipped_by for c in state.clips}
        assert clipped == {
            ("subsystems", "legacy-core"): "legacy",
            ("components", "legacy-db"): "legacy",
            ("interfaces", "shop-to-legacy"): "legacy",
            ("relationships", "ops-owns-legacy"): "legacy",
        }

    def test_clips_ordered_by_kind_then_group(self) -> None:
        state = resolve(_tree_arch(), sel("m1"))
        assert [c.id for c in state.clips] == [
            "legacy-core",
            "legacy-db",
            "shop-to-legacy",
            "ops-owns-legacy",
        ]

    def test_authored_dead_endpoint_is_cause_itself(self) -> None:
        # at m2 ops is authored-dead: the interface clip names ops, not a
        # deeper cause
        state = resolve(_tree_arch(), sel("m2"))
        clipped = {(c.kind, c.id): c.clipped_by for c in state.clips}
        assert clipped[("interfaces", "ops-uses-shop")] == "ops"
        assert clipped[("relationships", "ops-owns-legacy")] == "ops"

    def test_provider_checked_before_consumer(self) -> None:
        # both endpoints blocked at m2 (provider chain dead via legacy,
        # consumer ops authored-dead): the provider side wins
        state = resolve(_tree_arch(), sel("m2"))
        clipped = {c.id: c.clipped_by for c in state.clips}
        assert clipped["shop-to-legacy"] == "legacy"

    def test_child_before_parent_from_is_clipped(self) -> None:
        arch = build(
            milestones=["m1"],
            systems=[{"id": "s", "name": "S", "from": "m1"}],
            subsystems=[{"id": "sub", "name": "Sub", "system": "s"}],
        )
        current = resolve(arch, sel("current"))
        assert current.ids("subsystems") == ()
        assert [(c.id, c.clipped_by) for c in current.clips] == [("sub", "s")]
        assert resolve(arch, sel("m1")).ids("subsystems") == ("sub",)

    def test_current_state_of_tree_is_unclipped(self) -> None:
        state = resolve(_tree_arch(), sel("current"))
        assert state.clips == ()
        assert state.ids("interfaces") == ("shop-to-legacy", "ops-uses-shop")


# -------------------------------------------------------------------- diff


class TestDiff:
    def _arch(self) -> Architecture:
        return build(
            milestones=["m1", "m2"],
            systems=[
                {"id": "legacy", "name": "Legacy", "until": "m1"},
                {"id": "next", "name": "Next", "from": "m1"},
                {"id": "keep", "name": "Keep"},
            ],
            subsystems=[
                {"id": "legacy-core", "name": "Core", "system": "legacy"},
                {
                    "id": "svc",
                    "name": "Service",
                    "system": "legacy",
                    "tags": ["old"],
                    "properties": {"tech": "cobol", "tier": "1"},
                },
                {
                    "id": "svc",
                    "name": "Service NG",
                    "system": "next",
                    "from": "m1",
                    "tags": ["new"],
                    "properties": {"tech": "rust", "owner": "core-team"},
                },
            ],
        )

    def test_added_removed_with_consequences(self) -> None:
        d = diff(self._arch(), sel("current"), sel("m1"))
        assert [(e.kind, e.id, e.clipped_by) for e in d.removed] == [
            ("systems", "legacy", None),
            ("subsystems", "legacy-core", "legacy"),
        ]
        assert [(e.kind, e.id) for e in d.added] == [("systems", "next")]
        assert d.added[0].name == "Next"
        assert d.added[0].clipped_by is None

    def test_changed_reports_fields_not_markers(self) -> None:
        d = diff(self._arch(), sel("current"), sel("m1"))
        (entry,) = d.changed
        assert (entry.kind, entry.id) == ("subsystems", "svc")
        changes = {c.field: (c.old, c.new) for c in entry.changes}
        assert changes == {
            "name": ("Service", "Service NG"),
            "system": ("legacy", "next"),
            "tags": (["old"], ["new"]),
            "properties.tech": ("cobol", "rust"),
            "properties.tier": ("1", None),
            "properties.owner": (None, "core-team"),
        }

    def test_identical_content_revisions_not_reported(self) -> None:
        arch = build(
            milestones=["m1"],
            systems=[
                {"id": "s", "name": "S"},
                {"id": "s", "name": "S", "from": "m1"},
            ],
        )
        d = diff(arch, sel("current"), sel("m1"))
        assert d == Diff(added=(), removed=(), changed=())

    def test_reverse_direction_swaps_roles(self) -> None:
        d = diff(self._arch(), sel("m1"), sel("current"))
        assert [(e.kind, e.id) for e in d.added] == [
            ("systems", "legacy"),
            ("subsystems", "legacy-core"),
        ]
        assert [(e.kind, e.id) for e in d.removed] == [("systems", "next")]
        (entry,) = d.changed
        assert {c.field: (c.old, c.new) for c in entry.changes}["name"] == (
            "Service NG",
            "Service",
        )

    def test_diff_of_same_state_is_empty(self) -> None:
        d = diff(self._arch(), sel("m2"), sel("end"))
        assert d == Diff(added=(), removed=(), changed=())


# ----------------------------------------------------------------- advance


class TestAdvance:
    def _arch(self) -> Architecture:
        return build(
            milestones=["m1", "m2", "m3"],
            timelines=[
                {"id": "main", "milestones": ["m1", "m2", "m3"]},
                {"id": "early", "milestones": ["m1"]},
            ],
            systems=[
                {"id": "legacy", "name": "Legacy", "until": "m1"},
                {"id": "next", "name": "Next", "from": "m2"},
                {"id": "keep", "name": "Keep"},
                {"id": "later", "name": "Later", "from": "m3"},
                {"id": "phased", "name": "Phased v1"},
                {"id": "phased", "name": "Phased v2", "from": "m1"},
                {"id": "phased", "name": "Phased v3", "from": "m3"},
            ],
        )

    def test_rewrite_through_m2(self) -> None:
        out = advance(self._arch(), through="m2")
        assert [m.id for m in out.milestones] == ["m3"]
        # emptied timeline dropped; surviving one keeps only m3
        assert [(t.id, list(t.milestones)) for t in out.timelines] == [
            ("main", ["m3"])
        ]
        rows = [(s.id, s.name, s.from_, s.until) for s in out.systems]
        assert rows == [
            ("next", "Next", None, None),  # from m2 stripped
            ("keep", "Keep", None, None),
            ("later", "Later", "m3", None),  # untouched
            ("phased", "Phased v2", None, None),  # superseded v1 dropped
            ("phased", "Phased v3", "m3", None),  # future revision kept
        ]

    def test_timelines_none_when_all_emptied(self) -> None:
        arch = build(
            milestones=["m1"],
            timelines=[{"id": "only", "milestones": ["m1"]}],
            systems=[{"id": "s", "name": "S"}],
        )
        out = advance(arch, through="m1")
        assert out.milestones == []
        assert out.timelines is None

    def test_gap_survives_advance(self) -> None:
        arch = build(
            milestones=["m1", "m2", "m3"],
            systems=[
                {"id": "s", "name": "S", "until": "m1"},
                {"id": "s", "name": "S back", "from": "m3"},
            ],
        )
        out = advance(arch, through="m2")
        rows = [(s.id, s.name, s.from_, s.until) for s in out.systems]
        assert rows == [("s", "S back", "m3", None)]

    def test_unknown_milestone_rejected(self) -> None:
        with pytest.raises(ResolverError):
            advance(self._arch(), through="ghost")

    def test_input_not_mutated_and_states_preserved(self) -> None:
        arch = self._arch()
        before = arch.model_copy(deep=True)
        out = advance(arch, through="m1")
        assert arch == before
        # current state of the advanced file == original state at m1, and
        # every remaining milestone resolves identically
        assert resolve(out, sel("current", timeline="main")).ids("systems") == (
            resolve(arch, sel("m1", timeline="main")).ids("systems")
        )
        for at in ("m2", "m3", "end"):
            assert resolve(out, sel(at, timeline="main")).ids("systems") == (
                resolve(arch, sel(at, timeline="main")).ids("systems")
            )
