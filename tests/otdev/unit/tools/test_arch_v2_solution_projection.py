"""Focused tests for local system-set solution projections."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest

from otdev.tools._arch.v2.drawio_export import drawio_document
from otdev.tools._arch.v2.load import (
    WorkspaceLoadError,
    load_workspace,
    parse_properties_cell,
)
from otdev.tools._arch.v2.models import (
    ArchitectureWorkspace,
    LayoutBounds,
    LayoutPoint,
    SolutionLayoutEdge,
    SolutionLayoutNode,
    SolutionLayoutResult,
    SystemSetSelector,
    ViewSelection,
)
from otdev.tools._arch.v2.projection import (
    SolutionProjectionError,
    prepare_solution_snapshots,
    project_solution,
    solution_projection_cache_key,
)
from otdev.tools._arch.v2.viewgraph import normalize_selection
from otdev.tools._arch.v2.write import write_workspace
from tests.otdev.arch_v2_fixtures import CANONICAL_ARCH_V2_YAML

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURE = CANONICAL_ARCH_V2_YAML


def _workspace_with_groups() -> ArchitectureWorkspace:
    workspace = load_workspace(FIXTURE).workspace
    payload = workspace.model_dump(mode="python")
    payload["states"][0]["systems"][0]["group"] = ["payments", "core"]
    payload["changes"][0]["group"] = ["wave-one"]
    return ArchitectureWorkspace.model_validate(payload)


def _chain_workspace() -> ArchitectureWorkspace:
    return ArchitectureWorkspace.model_validate(
        {
            "schema_version": 2,
            "states": [
                {
                    "id": "base",
                    "systems": [
                        {"id": "A", "name": "A", "group": ["pair"], "tags": ["core"]},
                        {"id": "B", "name": "B", "group": ["pair"]},
                        {"id": "C", "name": "C"},
                        {"id": "X", "name": "X"},
                    ],
                    "interfaces": [
                        {
                            "id": "a-b",
                            "name": "A to B",
                            "provider": "A",
                            "consumer": "B",
                        },
                        {
                            "id": "b-c",
                            "name": "B to C",
                            "provider": "B",
                            "consumer": "C",
                        },
                    ],
                    "relationships": [
                        {
                            "id": "a-x",
                            "name": "A owns X",
                            "source_id": "A",
                            "target_id": "X",
                        }
                    ],
                }
            ],
            "changes": [
                {
                    "id": "delivery",
                    "name": "Delivery",
                    "group": ["wave"],
                    "patches": {
                        "systems": [
                            {
                                "id": "A",
                                "change_type": "changed",
                                "description": "changed",
                            },
                            {
                                "id": "C",
                                "change_type": "changed",
                                "description": "changed",
                            },
                        ]
                    },
                }
            ],
            "roadmaps": [
                {
                    "id": "delivery",
                    "base": "base",
                    "items": [{"change": "delivery", "order": 1}],
                }
            ],
        }
    )


def _impact_workspace() -> ArchitectureWorkspace:
    return ArchitectureWorkspace.model_validate(
        {
            "schema_version": 2,
            "states": [
                {
                    "id": "base",
                    "systems": [
                        {"id": "A", "name": "A"},
                        {"id": "B", "name": "B"},
                        {"id": "C", "name": "C"},
                    ],
                    "applications": [
                        {"id": "app-a", "name": "App A", "system": "A"},
                        {"id": "app-b", "name": "App B", "system": "B"},
                    ],
                    "components": [
                        {"id": "cmp-a", "name": "Component A", "application": "app-a"}
                    ],
                    "users": [{"id": "actor", "name": "Actor", "kind": "actor"}],
                    "interfaces": [
                        {
                            "id": "actor-app",
                            "name": "Actor to app",
                            "provider": "actor",
                            "consumer": "app-a",
                        },
                        {
                            "id": "component-app",
                            "name": "Component to app",
                            "provider": "cmp-a",
                            "consumer": "app-b",
                        },
                    ],
                    "relationships": [
                        {
                            "id": "component-c",
                            "name": "Component to C",
                            "source_id": "cmp-a",
                            "target_id": "C",
                        }
                    ],
                }
            ],
            "changes": [
                {
                    "id": "move-and-retarget",
                    "name": "Move and retarget",
                    "group": ["wave"],
                    "patches": {
                        "applications": [
                            {
                                "id": "app-a",
                                "parent": "B",
                                "description": "Moved application",
                            }
                        ],
                        "components": [{"id": "cmp-a", "parent": "app-b"}],
                        "interfaces": [{"id": "actor-app", "consumer": "app-b"}],
                        "relationships": [
                            {"id": "component-c", "direction": "reverse"}
                        ],
                    },
                },
                {
                    "id": "remove-b",
                    "name": "Remove B",
                    "group": ["wave"],
                    "patches": {"systems": [{"id": "B", "change_type": "removed"}]},
                },
                {
                    "id": "add-d",
                    "name": "Add D",
                    "group": ["future"],
                    "patches": {
                        "systems": [{"id": "D", "change_type": "added", "name": "D"}],
                        "applications": [
                            {
                                "id": "app-d",
                                "change_type": "added",
                                "name": "App D",
                                "parent": "D",
                            }
                        ],
                        "interfaces": [
                            {
                                "id": "actor-d",
                                "change_type": "added",
                                "name": "Actor to D",
                                "provider": "actor",
                                "consumer": "D",
                            }
                        ],
                    },
                },
            ],
            "roadmaps": [
                {
                    "id": "delivery",
                    "base": "base",
                    "items": [
                        {"change": "move-and-retarget", "order": 1},
                        {"change": "remove-b", "order": 2},
                        {"change": "add-d", "order": 3},
                    ],
                }
            ],
        }
    )


def _projection_workspace() -> ArchitectureWorkspace:
    return ArchitectureWorkspace.model_validate(
        {
            "schema_version": 2,
            "states": [
                {
                    "id": "base",
                    "systems": [
                        {"id": "A", "name": "A"},
                        {"id": "B", "name": "B"},
                        {"id": "C", "name": "C"},
                    ],
                    "applications": [
                        {"id": "app-a1", "name": "App A1", "system": "A"},
                        {"id": "app-a2", "name": "App A2", "system": "A"},
                        {"id": "app-b", "name": "App B", "system": "B"},
                    ],
                    "components": [
                        {
                            "id": "cmp-a1",
                            "name": "Component A1",
                            "application": "app-a1",
                        },
                        {"id": "orphan", "name": "Orphan", "application": "missing"},
                    ],
                    "users": [{"id": "actor", "name": "Actor", "kind": "actor"}],
                    "interfaces": [
                        {
                            "id": "a-b-1",
                            "name": "A to B one",
                            "provider": "cmp-a1",
                            "consumer": "app-b",
                            "type": "api",
                        },
                        {
                            "id": "a-b-2",
                            "name": "A to B two",
                            "provider": "app-a2",
                            "consumer": "B",
                            "type": "api",
                        },
                        {
                            "id": "b-a",
                            "name": "B to A",
                            "provider": "B",
                            "consumer": "A",
                            "type": "api",
                        },
                        {
                            "id": "a-b-event",
                            "name": "A to B event",
                            "provider": "A",
                            "consumer": "B",
                            "type": "event",
                        },
                        {
                            "id": "a-internal",
                            "name": "Internal A",
                            "provider": "cmp-a1",
                            "consumer": "app-a2",
                        },
                        {
                            "id": "actor-a",
                            "name": "Actor to A",
                            "provider": "actor",
                            "consumer": "A",
                        },
                        {
                            "id": "b-c",
                            "name": "B to C",
                            "provider": "B",
                            "consumer": "C",
                        },
                        {
                            "id": "orphan-a",
                            "name": "Orphan to A",
                            "provider": "orphan",
                            "consumer": "A",
                        },
                    ],
                    "relationships": [
                        {
                            "id": "a-c-relationship",
                            "name": "A relates to C",
                            "source_id": "A",
                            "target_id": "C",
                        }
                    ],
                }
            ],
            "roadmaps": [{"id": "delivery", "base": "base", "items": []}],
        }
    )


def test_prepare_snapshots_and_group_indexes() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_workspace_with_groups(), roadmap_id="preferred"
    )

    assert list(prepared.snapshots) == ["0", "1", "2"]
    assert prepared.unavailable_orders == []
    assert prepared.indexes["0"].system_groups["payments"] == ["A"]
    assert prepared.indexes["1"].change_groups["wave-one"] == ["A", "B", "C", "D"]
    assert prepared.indexes["1"].tags["core"] == ["A"]


def test_roadmap_wide_impacts_include_moves_endpoints_actors_and_cascades() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_impact_workspace(), roadmap_id="delivery"
    )
    indexes = prepared.indexes["0"]

    assert indexes.systems == ["A", "B", "C", "D"]
    assert indexes.changes == {
        "add-d": ["D"],
        "move-and-retarget": ["A", "B", "C"],
        "remove-b": ["B", "C"],
    }
    assert indexes.change_groups == {
        "future": ["D"],
        "wave": ["A", "B", "C"],
    }
    moved = indexes.change_impacts["move-and-retarget"]
    assert {reason.code for reason in moved["A"]} >= {
        "moved_from",
        "interface_consumer",
        "relationship_source",
    }
    assert {reason.code for reason in moved["B"]} >= {
        "moved_to",
        "interface_consumer",
        "relationship_source",
    }
    assert {reason.code for reason in moved["C"]} == {"relationship_target"}
    removed = indexes.change_impacts["remove-b"]
    assert {reason.code for reason in removed["B"]} >= {
        "system_patch",
        "cascade_removal",
    }
    assert {reason.code for reason in removed["C"]} >= {
        "relationship_target",
        "cascade_removal",
    }
    assert indexes.change_impacts["add-d"]["D"]
    assert prepared.model_dump(mode="json")["indexes"]["0"]["change_impacts"]


def test_future_change_selector_is_valid_at_base_and_unknown_selectors_fail() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_impact_workspace(), roadmap_id="delivery"
    )

    future = project_solution(
        prepared=prepared,
        order=0,
        selector={"changes": ["add-d"]},
    )
    assert future.selected_systems == ["D"]
    assert future.graph.nodes == []
    with pytest.raises(SolutionProjectionError, match="Unknown changes"):
        project_solution(
            prepared=prepared,
            order=0,
            selector={"changes": ["missing"]},
        )
    with pytest.raises(SolutionProjectionError, match="Unknown change groups"):
        project_solution(
            prepared=prepared,
            order=0,
            selector={"change_groups": ["missing"]},
        )


def test_future_browse_subject_projects_from_roadmap_wide_index() -> None:
    workspace = load_workspace(FIXTURE).workspace
    selection = normalize_selection(
        workspace=workspace,
        value={
            "roadmap": "preferred",
            "order": 0,
            "browse_by": "system",
            "subject": "I",
        },
    )
    prepared = prepare_solution_snapshots(workspace=workspace, roadmap_id="preferred")

    projection = project_solution(
        prepared=prepared,
        order=0,
        selector=selection.system_set,
        selection=selection,
    )

    assert projection.selected_systems == ["I"]
    assert projection.graph.nodes == []
    assert [(item.system_id, item.state) for item in projection.absent_systems] == [
        ("I", "not_yet_present")
    ]


def test_yaml_excel_impacted_system_indexes_match(tmp_path: Path) -> None:
    yaml_path = tmp_path / "impact.yaml"
    excel_path = tmp_path / "impact.xlsx"
    workspace = _impact_workspace()
    write_workspace(path=yaml_path, workspace=workspace)
    write_workspace(path=excel_path, workspace=workspace)

    yaml_indexes = prepare_solution_snapshots(
        workspace=load_workspace(yaml_path).workspace,
        roadmap_id="delivery",
    ).indexes
    excel_indexes = prepare_solution_snapshots(
        workspace=load_workspace(excel_path).workspace,
        roadmap_id="delivery",
    ).indexes
    assert yaml_indexes == excel_indexes


def test_depth_and_boundary_use_before_after_union() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_workspace_with_groups(), roadmap_id="preferred"
    )

    boundary = project_solution(
        prepared=prepared,
        order=1,
        selector={"systems": ["A"]},
        interface_depth=0,
        level="system",
    )
    expanded = project_solution(
        prepared=prepared,
        order=1,
        selector={"systems": ["A"]},
        interface_depth=1,
        level="system",
    )

    assert boundary.included_systems == ["A"]
    assert [item.interface.id for item in boundary.boundary_interfaces] == [
        "arch-v2-interface-a-to-d"
    ]
    assert boundary.graph.edges == []
    assert expanded.included_systems == ["A", "D"]
    assert [(edge.source_id, edge.target_id) for edge in expanded.graph.edges] == [
        ("A", "D")
    ]
    assert (
        next(node for node in expanded.graph.nodes if node.id == "D").status
        == "Removed"
    )


def test_level_projection_and_cache_identity() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_workspace_with_groups(), roadmap_id="preferred"
    )
    selector = SystemSetSelector(system_groups=["payments"])
    projection = project_solution(
        prepared=prepared,
        order=0,
        selector=selector,
        interface_depth=1,
        level="application",
    )

    assert {node.entity_kind for node in projection.graph.nodes} == {
        "system",
        "application",
    }
    assert [(edge.source_id, edge.target_id) for edge in projection.graph.edges] == [
        ("app-a", "app-d")
    ]
    assert projection.cache_key == solution_projection_cache_key(
        snapshot_id="preferred@0",
        model_id=prepared.snapshots["0"].id,
        selector=selector,
        depth=1,
        level="application",
        theme="clean",
    )


def test_recursive_interface_hops_and_boundary_interfaces() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_chain_workspace(), roadmap_id="delivery"
    )

    depths = [
        project_solution(
            prepared=prepared,
            order=1,
            selector={"systems": ["A"]},
            interface_depth=depth,
        )
        for depth in range(3)
    ]

    assert [projection.included_systems for projection in depths] == [
        ["A"],
        ["A", "B"],
        ["A", "B", "C"],
    ]
    assert [
        [edge.interface.id for edge in projection.boundary_interfaces]
        for projection in depths
    ] == [
        ["a-b"],
        ["b-c"],
        [],
    ]
    assert [[edge.id for edge in projection.graph.edges] for projection in depths] == [
        [],
        ["a-b"],
        ["a-b", "b-c"],
    ]
    assert "X" not in depths[2].included_systems


def test_projection_aggregates_edges_and_retains_collapsed_and_boundary_data() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_projection_workspace(), roadmap_id="delivery"
    )

    projection = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A"]},
        interface_depth=1,
        level="system",
    )

    assert projection.system_distances == {"A": 0, "B": 1}
    assert projection.included_systems == ["A", "B"]
    aggregate = next(
        edge for edge in projection.graph.edges if edge.id.startswith("aggregate-")
    )
    assert aggregate.interface_ids == ["a-b-1", "a-b-2"]
    assert {edge.id for edge in projection.graph.edges} >= {"a-b-event", "b-a"}
    assert [item.interface.id for item in projection.collapsed_interfaces] == [
        "a-internal"
    ]
    assert {item.interface.id for item in projection.boundary_interfaces} == {
        "actor-a",
        "b-c",
        "orphan-a",
    }
    actor = next(
        item
        for item in projection.boundary_interfaces
        if item.interface.id == "actor-a"
    )
    assert actor.inside_system == "A"
    assert actor.outside_system is None
    assert actor.outside_endpoint == "actor"
    assert projection.diagnostics[0].code == "unresolved_interface_endpoint"
    assert projection.diagnostics[0].endpoint_id == "orphan"
    assert {edge.id for edge in projection.internal_interfaces} >= {
        "a-b-1",
        "a-b-2",
        "a-internal",
    }


def test_drawio_uses_projection_aggregate_identity_and_plain_geometry() -> None:
    """The Draw.io boundary consumes canonical graph identity and neutral geometry."""
    prepared = prepare_solution_snapshots(
        workspace=_projection_workspace(), roadmap_id="delivery"
    )
    projection = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A"]},
        interface_depth=1,
    )
    aggregate = next(
        edge for edge in projection.graph.edges if edge.id.startswith("aggregate-")
    )
    layout = SolutionLayoutResult(
        request_id=projection.cache_key,
        graph_id=projection.graph.id,
        selection_id=projection.graph.selection.id,
        nodes=[
            SolutionLayoutNode(
                id=node_id,
                bounds=LayoutBounds(x=index * 200, y=0, width=160, height=100),
            )
            for index, node_id in enumerate(["A", "B"])
        ],
        edges=[
            SolutionLayoutEdge(
                id=aggregate.id,
                source="A",
                target="B",
                route=[LayoutPoint(x=160, y=50), LayoutPoint(x=200, y=50)],
                interface_ids=aggregate.interface_ids,
            )
        ],
        bounds=LayoutBounds(x=0, y=0, width=360, height=100),
    )
    root = ET.fromstring(
        drawio_document(pages=[(projection.graph, layout, "A and neighbors")])
    )
    edge = root.find(f".//mxCell[@id='{aggregate.id}']")
    assert edge is not None
    assert edge.attrib["interfaceIds"] == "a-b-1,a-b-2"
    assert edge.attrib["source"] == "A" and edge.attrib["target"] == "B"
    assert [
        (point.attrib["x"], point.attrib["y"]) for point in edge.findall(".//mxPoint")
    ] == [
        ("160", "50"),
        ("200", "50"),
    ]


def test_application_component_rollup_and_relationships_do_not_create_hops() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_projection_workspace(), roadmap_id="delivery"
    )
    application = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A"]},
        interface_depth=1,
        level="application",
    )
    component = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A"]},
        interface_depth=1,
        level="component",
    )
    disconnected = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A", "C"]},
        interface_depth=0,
        level="system",
    )

    assert "C" not in application.included_systems
    assert ("app-a1", "app-a2") in {
        (edge.source_id, edge.target_id) for edge in application.graph.edges
    }
    assert ("cmp-a1", "app-a2") in {
        (edge.source_id, edge.target_id) for edge in component.graph.edges
    }
    assert {node.id for node in disconnected.graph.nodes} == {"A", "C"}
    assert [edge.id for edge in disconnected.graph.edges] == ["a-c-relationship"]


def test_aggregation_keeps_different_statuses_separate() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_projection_workspace(), roadmap_id="delivery"
    )
    graph = prepared.snapshots["0"]
    source = next(edge for edge in graph.edges if edge.id == "a-b-1")
    changed = source.model_copy(
        update={
            "id": "a-b-changed",
            "status": "Changed",
            "context_status": "change",
            "interface_ids": ["a-b-changed"],
        }
    )
    prepared.snapshots["0"] = graph.model_copy(
        update={"edges": [*graph.edges, changed]}
    )

    projection = project_solution(
        prepared=prepared,
        order=0,
        selector={"systems": ["A"]},
        interface_depth=1,
    )
    changed_edge = next(
        edge for edge in projection.graph.edges if edge.status == "Changed"
    )
    assert changed_edge.interface_ids == ["a-b-changed"]


def test_interface_only_change_updates_the_selected_snapshot() -> None:
    payload = _chain_workspace().model_dump(mode="python")
    payload["changes"].append(
        {
            "id": "connect-a-c",
            "name": "Connect A to C",
            "patches": {
                "interfaces": [
                    {
                        "id": "a-c",
                        "change_type": "added",
                        "name": "A to C",
                        "provider": "A",
                        "consumer": "C",
                        "type": "api",
                    }
                ]
            },
        }
    )
    payload["roadmaps"][0]["items"].append({"change": "connect-a-c", "order": 2})
    prepared = prepare_solution_snapshots(
        workspace=ArchitectureWorkspace.model_validate(payload),
        roadmap_id="delivery",
    )

    before = project_solution(
        prepared=prepared,
        order=1,
        selector={"systems": ["A"]},
        interface_depth=2,
    )
    after = project_solution(
        prepared=prepared,
        order=2,
        selector={"systems": ["A"]},
        interface_depth=2,
    )

    assert before.included_systems == after.included_systems == ["A", "B", "C"]
    assert [edge.id for edge in before.graph.edges] == ["a-b", "b-c"]
    assert [edge.id for edge in after.graph.edges] == ["a-b", "a-c", "b-c"]
    assert (
        next(edge for edge in after.graph.edges if edge.id == "a-c").status == "Added"
    )


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ({"systems": ["A", "C"]}, ["A", "C"]),
        ({"system_groups": ["pair"]}, ["A", "B"]),
        ({"changes": ["delivery"]}, ["A", "C"]),
        ({"change_groups": ["wave"]}, ["A", "C"]),
        ({"tags": ["core"]}, ["A"]),
    ],
)
def test_all_system_set_selector_forms(
    selector: dict[str, list[str]], expected: list[str]
) -> None:
    prepared = prepare_solution_snapshots(
        workspace=_chain_workspace(), roadmap_id="delivery"
    )

    projection = project_solution(prepared=prepared, order=1, selector=selector)

    assert projection.selected_systems == expected


def test_projection_preserves_independent_selection_and_unique_identity() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_chain_workspace(), roadmap_id="delivery"
    )
    selection = ViewSelection.model_validate(
        {
            "roadmap": "delivery",
            "order": 1,
            "system_set": {"systems": ["A"]},
            "interface_depth": 1,
            "level": "application",
            "color_by": "tag",
            "theme": "clean",
        }
    )

    first = project_solution(
        prepared=prepared,
        order=1,
        selector=selection.system_set,
        interface_depth=selection.interface_depth,
        level=selection.level,
        selection=selection,
    )
    second = project_solution(
        prepared=prepared,
        order=1,
        selector={"systems": ["B", "B"]},
        interface_depth=0,
        level="system",
        selection=selection,
    )

    assert first.graph.selection.selection.color_by == "tag"
    assert first.graph.selection.selection.theme == "clean"
    assert first.graph.selection.selection.system_set.systems == ["A"]
    assert second.graph.selection.selection.system_set.systems == ["B"]
    assert first.graph.id != second.graph.id
    assert first.graph.selection.id != second.graph.selection.id


def test_snapshot_transition_status_and_absent_scope_are_independent() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_workspace_with_groups(), roadmap_id="preferred"
    )
    selector = {"changes": ["arch-v2-change-2027"]}
    base = project_solution(
        prepared=prepared,
        order=0,
        selector=selector,
        level="component",
    )
    transition = project_solution(
        prepared=prepared,
        order=1,
        selector=selector,
        level="component",
    )
    later = project_solution(
        prepared=prepared,
        order=2,
        selector=selector,
        level="component",
    )

    assert (
        base.selected_systems
        == transition.selected_systems
        == later.selected_systems
        == [
            "A",
            "B",
            "C",
            "D",
        ]
    )
    assert {item.system_id: item.state for item in base.absent_systems} == {
        "B": "not_yet_present",
        "C": "not_yet_present",
    }
    assert {item.system_id: item.state for item in transition.absent_systems} == {
        "D": "no_longer_present"
    }
    assert {item.system_id: item.state for item in later.absent_systems} == {
        "D": "no_longer_present"
    }
    assert {node.status for node in base.graph.nodes} == {"No Change"}
    transition_nodes = {node.id: node for node in transition.graph.nodes}
    assert transition_nodes["A"].status == "Changed"
    assert transition_nodes["B"].status == "Added"
    assert transition_nodes["C"].status == "Added"
    assert transition_nodes["D"].status == "Removed"
    assert transition_nodes["app-d"].status == "Removed"
    assert transition_nodes["cmp-d"].status == "Removed"
    assert (
        next(
            edge
            for edge in transition.internal_interfaces
            if edge.id == "arch-v2-interface-a-to-d"
        ).status
        == "Removed"
    )
    later_nodes = {node.id: node for node in later.graph.nodes}
    assert "D" not in later_nodes
    assert later_nodes["B"].status == "No Change"
    assert later_nodes["C"].status == "Changed"
    assert "arch-v2-interface-a-to-d" not in {
        edge.id for edge in later.internal_interfaces
    }


def test_color_mode_does_not_change_transition_metadata_or_cache_identity() -> None:
    prepared = prepare_solution_snapshots(
        workspace=_workspace_with_groups(), roadmap_id="preferred"
    )
    change_color = ViewSelection.model_validate(
        {
            "roadmap": "preferred",
            "order": 1,
            "system_set": {"systems": ["A", "D"]},
            "color_by": "change_status",
        }
    )
    tag_color = change_color.model_copy(update={"color_by": "tag"})

    first = project_solution(
        prepared=prepared,
        order=1,
        selector=change_color.system_set,
        selection=change_color,
    )
    second = project_solution(
        prepared=prepared,
        order=1,
        selector=tag_color.system_set,
        selection=tag_color,
    )

    assert first.cache_key == second.cache_key
    assert [(node.id, node.status) for node in first.graph.nodes] == [
        (node.id, node.status) for node in second.graph.nodes
    ]
    assert [(edge.id, edge.status) for edge in first.graph.edges] == [
        (edge.id, edge.status) for edge in second.graph.edges
    ]


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ('{"owner":"payments","tier":1}', {"owner": "payments", "tier": 1}),
        ("owner:payments;tier:one", {"owner": "payments", "tier": "one"}),
        ("owner:payments\ntier:one", {"owner": "payments", "tier": "one"}),
        (" owner : payments ; note: ", {"owner": "payments", "note": ""}),
        ("owner:https://service.local/path", {"owner": "https://service.local/path"}),
    ],
)
def test_excel_properties_formats(cell: str, expected: dict[str, object]) -> None:
    assert parse_properties_cell(cell) == expected


@pytest.mark.parametrize(
    "cell",
    [
        "owner",
        ":payments",
        "owner:payments;owner:platform",
        '{"owner":"payments","owner":"platform"}',
    ],
)
def test_excel_properties_reject_malformed_or_duplicate_entries(cell: str) -> None:
    with pytest.raises(WorkspaceLoadError):
        parse_properties_cell(cell)
