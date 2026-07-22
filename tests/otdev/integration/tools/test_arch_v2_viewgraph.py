"""Integration tests for deterministic production ViewGraph preparation."""

from __future__ import annotations

import pytest

from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.viewgraph import (
    prepare_roadmap_viewgraphs,
    resolve_view_graph,
)
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def test_viewgraph_deterministic_production_data() -> None:
    """viewgraph-deterministic-production-data: YAML and Excel produce identical graphs."""
    yaml_workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    excel_workspace = load_workspace(FIXTURES / "arch-v2-canonical.xlsx").workspace

    yaml_result = resolve_view_graph(workspace=yaml_workspace, value="compare-base-2027")
    excel_result = resolve_view_graph(workspace=excel_workspace, value="compare-base-2027")

    assert yaml_result.graph is not None
    assert excel_result.graph is not None

    def without_sources(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: without_sources(item)
                for key, item in value.items()
                if key not in {"source", "source_location"}
            }
        if isinstance(value, list):
            return [without_sources(item) for item in value]
        return value

    assert without_sources(yaml_result.graph.model_dump(mode="json")) == without_sources(
        excel_result.graph.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    ("browse_by", "subject"),
    [
        ("system", "I"),
        ("system_group", "payments"),
        ("change", "arch-v2-change-2027"),
        ("change_group", "wave-one"),
        ("tag", "core"),
    ],
)
def test_yaml_excel_browse_subjects_resolve_identically(
    browse_by: str,
    subject: str,
) -> None:
    """All browse subjects produce identical canonical selections from YAML and Excel."""
    yaml_workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    excel_workspace = load_workspace(FIXTURES / "arch-v2-canonical.xlsx").workspace
    value = {
        "roadmap": "preferred",
        "order": 0,
        "browse_by": browse_by,
        "subject": subject,
    }

    yaml_result = resolve_view_graph(workspace=yaml_workspace, value=value)
    excel_result = resolve_view_graph(workspace=excel_workspace, value=value)

    assert yaml_result.issues.errors == excel_result.issues.errors == []
    assert yaml_result.graph is not None
    assert excel_result.graph is not None
    assert (
        yaml_result.graph.selection.selection.model_dump(mode="json")
        == excel_result.graph.selection.selection.model_dump(mode="json")
    )


def test_prepared_base_2027_2028_no_browser_replay() -> None:
    """prepared-base-2027-2028-no-browser-replay: every point ships resolved data."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace

    prepared, issues = prepare_roadmap_viewgraphs(
        workspace=workspace,
        roadmap_id="preferred",
    )

    assert issues.errors == []
    assert list(prepared.graphs) == ["0", "1", "2"]
    assert prepared.unavailable_orders == []
    assert [prepared.graphs[str(order)].selection.order for order in range(3)] == [
        0,
        1,
        2,
    ]
    assert all(graph.resolved_state for graph in prepared.graphs.values())

    restricted, restricted_issues = prepare_roadmap_viewgraphs(
        workspace=workspace,
        roadmap_id="preferred",
        orders=[0, 2],
    )
    assert restricted_issues.errors == []
    assert list(restricted.graphs) == ["0", "2"]
    assert restricted.unavailable_orders == [1]
