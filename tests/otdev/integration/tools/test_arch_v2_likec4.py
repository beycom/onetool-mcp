"""Pinned LikeC4 compile/layout integration tests using production ViewGraph data."""

from __future__ import annotations

import pytest

from otdev.tools._arch.v2.likec4 import compile_likec4, generate_likec4
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.viewgraph import resolve_view_graph
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def test_standard_view_compilation() -> None:
    """standard-view-compilation: generated hierarchy and views pass pinned layout."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    result = resolve_view_graph(workspace=workspace, value="compare-base-2027")
    assert result.graph is not None
    generated = generate_likec4(result.graph)

    compiled = compile_likec4(generated.source)

    views = {view["id"]: view for view in compiled["views"]}
    assert list(views) == generated.view_ids
    assert views["index"]["nodes"] > 0
    assert views["index"]["edges"] > 0
    assert views["index"]["width"] > 0
    assert views["index"]["height"] > 0
    assert any(view_id.startswith("vie_a_") for view_id in views)
    assert any(view_id.startswith("vie_arch_v2_change_2027") for view_id in views)
