"""Schema-v2 selection resolution and ViewGraph projection tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.models import SavedView
from otdev.tools._arch.v2.viewgraph import normalize_selection, resolve_view_graph
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

if TYPE_CHECKING:
    from otdev.tools._arch.v2.models import ArchitectureWorkspace, ViewGraph

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


@pytest.fixture
def canonical() -> ArchitectureWorkspace:
    return load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace


def _graph(workspace: ArchitectureWorkspace, value: object) -> ViewGraph:
    result = resolve_view_graph(workspace=workspace, value=value)  # type: ignore[arg-type]
    assert result.issues.errors == []
    assert result.graph is not None
    return result.graph


def test_compare_base_to_2027(canonical: ArchitectureWorkspace) -> None:
    """compare-base-to-2027: complete state, net change, history, and tombstones coexist."""
    graph = _graph(canonical, "compare-base-2027")

    assert graph.resolved_state.id == "arch-v2-base@preferred:1"
    assert {system.id for system in graph.resolved_state.systems} == {
        "A",
        "B",
        "C",
        "E",
        "F",
        "G",
        "H",
    }
    assert graph.comparison is not None
    assert graph.comparison.base_state_id.endswith(":0")
    assert [item.change_id for item in graph.comparison.contributing_history] == [
        "arch-v2-change-2027"
    ]
    assert {item.entity_id for item in graph.tombstones} >= {
        "D",
        "app-d",
        "cmp-d",
        "arch-v2-interface-a-to-d",
    }
    assert all(operation.source is not None for operation in graph.comparison.change.operations)


def test_compare_origin_after_endpoint(canonical: ArchitectureWorkspace) -> None:
    """compare-origin-after-endpoint: later origins fail with both orders."""
    result = resolve_view_graph(
        workspace=canonical,
        value={"roadmap": "preferred", "order": 1, "compare_from": 2},
    )

    assert result.graph is None
    assert [issue.code for issue in result.issues.errors] == [
        "arch.comparison_after_endpoint"
    ]
    assert result.issues.errors[0].details == {"compare_from": 2, "endpoint": 1}


def test_focus_2027_at_2028(canonical: ArchitectureWorkspace) -> None:
    """focus-2027-at-2028: resolution stays final and later C override is disclosed."""
    graph = _graph(canonical, "focus-2027-at-2028")

    assert graph.selection.order == 2
    assert "I" in {system.id for system in graph.resolved_state.systems}
    assert graph.focus == ["arch-v2-change-2027"]
    assert [(item.change_id, item.entity_id) for item in graph.focus_overrides] == [
        ("arch-v2-change-2028", "C")
    ]


def test_reject_future_focus(canonical: ArchitectureWorkspace) -> None:
    """reject-future-focus: later focus requires explicit future context."""
    result = resolve_view_graph(
        workspace=canonical,
        value={
            "roadmap": "preferred",
            "order": 1,
            "focus": ["arch-v2-change-2028"],
        },
    )

    assert [issue.code for issue in result.issues.errors] == [
        "arch.future_focus_requires_context"
    ]


def test_browse_independent_changes(canonical: ArchitectureWorkspace) -> None:
    """browse-independent-changes: roadmap changes retain separate metadata and counts."""
    graph = _graph(
        canonical,
        {"roadmap": "preferred", "order": 1, "browse_by": "change"},
    )

    assert [(item.id, item.order) for item in graph.changes] == [
        ("arch-v2-change-2027", 1),
        ("arch-v2-change-2028", 2),
    ]
    assert graph.changes[0].metadata["owner"] == "Team Payments"
    assert graph.changes[0].affected_systems == ["A", "B", "C", "D"]
    assert graph.changes[0].operation_counts["remove"] == 4


@pytest.mark.parametrize(
    ("browse_by", "subject", "selector_field"),
    [
        ("system", "I", "systems"),
        ("system_group", "payments", "system_groups"),
        ("change", "arch-v2-change-2027", "changes"),
        ("change_group", "wave-one", "change_groups"),
        ("tag", "core", "tags"),
    ],
)
def test_browse_subjects_union_into_canonical_system_set(
    canonical: ArchitectureWorkspace,
    browse_by: str,
    subject: str,
    selector_field: str,
) -> None:
    """Every browse kind preserves other axes and leaves focus independent."""
    graph = _graph(
        canonical,
        {
            "roadmap": "preferred",
            "order": 0,
            "browse_by": browse_by,
            "subject": subject,
            "system_set": {"systems": ["E"]},
            "interface_depth": 2,
            "level": "component",
            "color_by": "tag",
        },
    )
    selection = graph.selection.selection

    expected_systems = sorted({"E", subject}) if selector_field == "systems" else ["E"]
    expected_subjects = expected_systems if selector_field == "systems" else [subject]
    assert getattr(selection.system_set, selector_field) == expected_subjects
    assert selection.system_set.systems == expected_systems
    assert selection.focus == []
    assert selection.interface_depth == 2
    assert selection.level == "component"
    assert selection.color_by == "tag"


@pytest.mark.parametrize(
    "browse_by",
    ["system", "system_group", "change", "change_group", "tag"],
)
def test_unknown_browse_subjects_fail_normal_validation(
    canonical: ArchitectureWorkspace,
    browse_by: str,
) -> None:
    """Unknown browse subjects fail through the canonical selector validator."""
    result = resolve_view_graph(
        workspace=canonical,
        value={
            "roadmap": "preferred",
            "order": 0,
            "browse_by": browse_by,
            "subject": "missing",
        },
    )

    assert result.graph is None
    assert [issue.code for issue in result.issues.errors] == [
        "arch.inapplicable_subject"
    ]


def test_saved_view_browse_subject_uses_same_canonical_selection(
    canonical: ArchitectureWorkspace,
) -> None:
    """Saved views use the same subject-to-system-set normalization as ad hoc values."""
    saved = SavedView(
        id="browse-wave-one",
        roadmap="preferred",
        order=0,
        browse_by="change_group",
        subject="wave-one",
        interface_depth=1,
    )
    workspace = canonical.model_copy(update={"views": [*canonical.views, saved]})

    graph = _graph(workspace, "browse-wave-one")

    assert graph.selection.selection.system_set.change_groups == ["wave-one"]
    assert graph.selection.selection.focus == []
    assert graph.selection.selection.interface_depth == 1


def test_system_change_default_visibility(canonical: ArchitectureWorkspace) -> None:
    """system-change-default-visibility: browse intent derives stable visibility defaults."""
    system = normalize_selection(
        workspace=canonical,
        value={"roadmap": "preferred", "order": 1, "browse_by": "system"},
    )
    change = normalize_selection(
        workspace=canonical,
        value={"roadmap": "preferred", "order": 1, "browse_by": "change"},
    )

    assert system.visibility == "all"
    assert change.visibility == "changes_with_context"
    graph = _graph(canonical, system)
    a = next(node for node in graph.nodes if node.id == "A")
    assert a.related_changes == ["arch-v2-change-2027"]


def test_changes_only_prelayout(canonical: ArchitectureWorkspace) -> None:
    """changes-only-prelayout: stable unrelated content and dangling edges are absent."""
    graph = _graph(
        canonical,
        {
            "roadmap": "preferred",
            "order": 1,
            "compare_from": "base",
            "visibility": "changes_only",
        },
    )

    assert all(node.context_status != "no_change" for node in graph.nodes)
    assert not {"E", "F", "G", "H", "app-a"} & {node.id for node in graph.nodes}
    node_ids = {node.id for node in graph.nodes}
    assert all(
        edge.source_id in node_ids and edge.target_id in node_ids for edge in graph.edges
    )


def test_changes_with_context(canonical: ArchitectureWorkspace) -> None:
    """changes-with-context: required endpoints remain while unrelated stable nodes do not."""
    graph = _graph(canonical, "compare-base-2027")
    nodes = {node.id: node for node in graph.nodes}

    assert nodes["app-a"].status == "No Change"
    assert "E" not in nodes
    assert "arch-v2-interface-a-to-d" in {edge.id for edge in graph.edges}


def test_future_i_opt_in(canonical: ArchitectureWorkspace) -> None:
    """future-i-opt-in: later additions appear only with explicit future context."""
    absent = _graph(canonical, {"roadmap": "preferred", "order": 1})
    present = _graph(
        canonical,
        {"roadmap": "preferred", "order": 1, "include_future": True},
    )

    assert "I" not in {node.id for node in absent.nodes}
    future_i = next(node for node in present.nodes if node.id == "I")
    assert future_i.context_status == "future"
    assert future_i.status == "No Change"
    assert future_i.future is True
    assert future_i.related_changes == ["arch-v2-change-2028"]


def test_removed_interface_tombstone(canonical: ArchitectureWorkspace) -> None:
    """removed-interface-tombstone: cascaded interfaces remain source-traced context."""
    graph = _graph(canonical, "compare-base-2027")
    edge = next(item for item in graph.edges if item.id == "arch-v2-interface-a-to-d")

    assert edge.tombstone is True
    assert edge.status == "Removed"
    assert edge.source is not None
    assert edge.source.yaml_path == "changes[0].patches.systems[3]"


def test_saved_ad_hoc_precedence_and_identity(canonical: ArchitectureWorkspace) -> None:
    """Saved selection values survive a selective ad hoc visibility override."""
    selection = normalize_selection(
        workspace=canonical,
        value={"view": "compare-base-2027", "visibility": "changes_only"},
    )
    first = _graph(canonical, selection)
    second = _graph(canonical, selection)

    assert selection.compare_from == "base"
    assert selection.visibility == "changes_only"
    assert first.id == second.id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
