"""Generated LikeC4 identifiers, theme precedence, and safe icon tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.tools._arch.v2.likec4 import (
    generate_likec4,
    generate_prepared_likec4,
    generated_identifier,
)
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.models import ColorPalettes, ElementStyle, Presentation, Theme
from otdev.tools._arch.v2.presentation import (
    CLEAN_THEME,
    PresentationError,
    pinned_icon_inventory,
    resolve_graph_presentation,
    resolve_icon,
    resolve_theme,
)
from otdev.tools._arch.v2.viewgraph import resolve_view_graph
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def test_cyclic_theme_inheritance_is_rejected() -> None:
    """Theme cycles produce a stable validation error rather than recursion failure."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    presentation = workspace.presentation.model_copy(
        update={
            "themes": [
                Theme(id="a", name="A", extends="b"),
                Theme(id="b", name="B", extends="a"),
            ]
        }
    )
    workspace = workspace.model_copy(update={"presentation": presentation})

    with pytest.raises(PresentationError, match="a -> b -> a") as error:
        resolve_theme(workspace=workspace, theme_id="a")

    assert error.value.code == "arch.cyclic_theme"


def _canonical_graph() -> tuple[object, object]:
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    result = resolve_view_graph(workspace=workspace, value="compare-base-2027")
    assert result.graph is not None
    return workspace, result.graph


def test_generated_id_mapping() -> None:
    """generated-id-mapping: canonical IDs map uniquely and deterministically."""
    _, graph = _canonical_graph()
    first = generate_likec4(graph)  # type: ignore[arg-type]
    second = generate_likec4(graph)  # type: ignore[arg-type]

    assert first == second
    assert set(first.canonical_to_likec4) == {node.id for node in graph.nodes}  # type: ignore[attr-defined]
    assert len(set(first.canonical_to_likec4.values())) == len(
        first.canonical_to_likec4
    )
    assert first.canonical_to_likec4["app-a"].startswith(
        first.canonical_to_likec4["A"] + "."
    )
    assert generated_identifier(
        kind="system", canonical_id="Payments API"
    ) == generated_identifier(kind="system", canonical_id="Payments API")
    assert "canonicalId 'arch-v2-interface-a-to-d'" in first.source


def test_prepared_layout_matches_runtime_direction() -> None:
    """API export uses the same left-to-right layout direction as the runtime adapter."""
    _, graph = _canonical_graph()

    generated = generate_prepared_likec4([graph])  # type: ignore[list-item]

    assert "autoLayout LeftRight" in generated.source


def test_clean_status_palette() -> None:
    """clean-status-palette: every contextual status has exact color and non-color cue."""
    expected = {
        "out_of_scope": ("#F5F5F5", "#666666"),
        "future": ("#E1D5E7", "#9673A6"),
        "new": ("#DAE8FC", "#6C8EBF"),
        "change": ("#FFF2CC", "#D6B656"),
        "no_change": ("#D5E8D4", "#82B366"),
        "decommission": ("#F8CECC", "#B85450"),
    }

    assert set(CLEAN_THEME.statuses) == set(expected)
    for status, (fill, border) in expected.items():
        style = CLEAN_THEME.statuses[status]  # type: ignore[index]
        assert style.color == fill
        assert style.border is not None
        assert style.border.startswith(border)
        assert any(cue in style.border for cue in ("solid", "dashed", "double"))


def test_style_precedence(tmp_path: Path) -> None:
    """style-precedence: kind, tag, status, entity, authored, and view merge in order."""
    workspace, graph = _canonical_graph()
    custom = Theme(
        id="custom",
        elements={
            "system": ElementStyle(shape="rectangle", color="#111111"),
            "tag:core": ElementStyle(opacity=0.8, color="#222222"),
            "entity:A": ElementStyle(padding=23, color="#333333"),
        },
        statuses={"change": ElementStyle(border="#444444 dashed")},
    )
    workspace = workspace.model_copy(  # type: ignore[attr-defined]
        update={
            "presentation": Presentation(
                default_roadmap="preferred",
                default_theme="custom",
                themes=[custom],
            )
        }
    )
    nodes = [
        node.model_copy(update={"style": ElementStyle(text_size=17, color="#555555")})
        if node.id == "A"
        else node
        for node in graph.nodes  # type: ignore[attr-defined]
    ]
    selection = graph.selection.model_copy(  # type: ignore[attr-defined]
        update={
            "selection": graph.selection.selection.model_copy(  # type: ignore[attr-defined]
                update={"theme": "custom"}
            )
        }
    )
    graph = graph.model_copy(  # type: ignore[attr-defined]
        update={"nodes": nodes, "selection": selection}
    )

    resolved = resolve_graph_presentation(
        graph=graph,
        workspace=workspace,
        workspace_root=tmp_path,
        view_styles={"A": ElementStyle(color="#666666", node_size="large")},
    )
    style = next(node.style for node in resolved.nodes if node.id == "A")

    assert style is not None
    assert style.shape == "rectangle"
    assert style.opacity == 0.8
    assert style.border == "#D6B656 solid"
    assert style.padding == 23
    assert style.text_size == 17
    assert style.node_size == "large"
    assert style.color == "#666666"


def test_tag_and_integration_palettes_resolve_to_exportable_styles(
    tmp_path: Path,
) -> None:
    """Tag fills and integration strokes resolve before renderer/export boundaries."""
    workspace, graph = _canonical_graph()
    presentation = Presentation(
        default_roadmap="preferred",
        default_theme="clean",
        palettes=ColorPalettes(
            tag={"core": ElementStyle(color="#ABCDEF")},
            integration_type={"api": ElementStyle(color="#123456")},
        ),
    )
    workspace = workspace.model_copy(update={"presentation": presentation})  # type: ignore[attr-defined]

    tag_selection = graph.selection.model_copy(  # type: ignore[attr-defined]
        update={
            "selection": graph.selection.selection.model_copy(  # type: ignore[attr-defined]
                update={"color_by": "tag"}
            )
        }
    )
    tagged = resolve_graph_presentation(
        graph=graph.model_copy(update={"selection": tag_selection}),  # type: ignore[attr-defined]
        workspace=workspace,
        workspace_root=tmp_path,
    )
    assert (
        next(node for node in tagged.nodes if node.id == "A").style.color == "#ABCDEF"
    )  # type: ignore[union-attr]

    integration_selection = graph.selection.model_copy(  # type: ignore[attr-defined]
        update={
            "selection": graph.selection.selection.model_copy(  # type: ignore[attr-defined]
                update={"color_by": "integration_type"}
            )
        }
    )
    integrated = resolve_graph_presentation(
        graph=graph.model_copy(update={"selection": integration_selection}),  # type: ignore[attr-defined]
        workspace=workspace,
        workspace_root=tmp_path,
    )
    edge = next(
        item for item in integrated.edges if item.id == "arch-v2-interface-a-to-d"
    )
    assert edge.style is not None
    assert edge.style.color == "#123456"


def test_all_pinned_icons_offline(tmp_path: Path) -> None:
    """all-pinned-icons-offline: every inventory name resolves without discovery."""
    inventory = pinned_icon_inventory()

    assert set(inventory) == {"aws", "azure", "bootstrap", "gcp", "tech"}
    for namespace, names in inventory.items():
        for name in names:
            icon = f"{namespace}:{name}"
            assert resolve_icon(value=icon, workspace_root=tmp_path) == icon
    assert resolve_icon(value="none", workspace_root=tmp_path) is None


def test_nested_local_svg_portable(tmp_path: Path) -> None:
    """nested-local-svg-portable: contained safe SVG is sanitized and embedded."""
    icon = tmp_path / "assets" / "icons" / "domain" / "safe.svg"
    icon.parent.mkdir(parents=True)
    icon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<path d="M0 0h10v10z" fill="currentColor"/></svg>',
        encoding="utf-8",
    )

    resolved = resolve_icon(value="@icons/domain/safe.svg", workspace_root=tmp_path)

    assert resolved is not None
    assert resolved.startswith("data:image/svg+xml;base64,")
    assert "http" not in resolved


@pytest.mark.parametrize(
    ("icon", "content", "code"),
    [
        ("https://invalid.test/icon.svg", None, "arch.unknown_icon"),
        ("@icons/../escape.svg", None, "arch.unsafe_icon_path"),
        ("@icons/missing.svg", None, "arch.missing_icon"),
        ("unknown:not-real", None, "arch.unknown_icon"),
        (
            "@icons/unsafe.svg",
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "arch.unsafe_icon",
        ),
    ],
)
def test_unsafe_icon_rejected(
    tmp_path: Path, icon: str, content: str | None, code: str
) -> None:
    """unsafe-icon-rejected: remote, traversal, missing, unknown, and active SVG fail."""
    if content is not None:
        path = tmp_path / "assets" / "icons" / "unsafe.svg"
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")

    with pytest.raises(PresentationError) as error:
        resolve_icon(value=icon, workspace_root=tmp_path)

    assert error.value.code == code
