"""Diagram catalog, view-only LikeC4, and attachment boundary tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.tools._arch.v2.diagram import (
    MAX_ATTACHMENT_BYTES,
    VIEW_ONLY_ALLOWLIST,
    VIEW_ONLY_VERSION,
    DiagramCatalogError,
    extend_with_diagram_catalog,
    validate_view_only_source,
)
from otdev.tools._arch.v2.frontend import prepare_explorer_data
from otdev.tools._arch.v2.likec4 import compile_likec4, generate_prepared_likec4
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.models import DiagramCatalogEntry
from otdev.tools._arch.v2.viewgraph import resolve_view_graph
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def _base_graph():
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    resolved = resolve_view_graph(workspace=workspace, value={"state": "arch-v2-base"})
    assert resolved.graph is not None
    return workspace, resolved.graph


def test_catalog_all_diagram_classes(tmp_path: Path) -> None:
    """catalog-all-diagram-classes: generated, static, dynamic, and external coexist."""
    workspace, graph = _base_graph()
    (tmp_path / "views").mkdir()
    (tmp_path / "assets" / "attachments").mkdir(parents=True)
    (tmp_path / "views" / "platform-delivery.c4").write_text(
        "views {\n  dynamic view platform_delivery {\n    title 'Delivery'\n  }\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "views" / "systems.c4").write_text(
        "views {\n  view systems {\n    include @{A}\n  }\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "assets" / "attachments" / "overview.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'><text>Overview</text></svg>",
        encoding="utf-8",
    )
    workspace = workspace.model_copy(
        update={
            "diagrams": [
                workspace.diagrams[0].model_copy(update={"systems": []}),
                DiagramCatalogEntry(
                    id="systems-static",
                    name="Systems",
                    kind="static",
                    source="views/systems.c4",
                ),
                DiagramCatalogEntry(
                    id="overview",
                    name="Overview",
                    kind="external",
                    source="assets/attachments/overview.svg",
                    folder="Reference",
                ),
            ]
        }
    )
    generated = generate_prepared_likec4([graph])
    source, catalogs, attachments = extend_with_diagram_catalog(
        generated=generated,
        graphs=[graph],
        workspace=workspace,
        workspace_root=tmp_path,
    )
    compiled = compile_likec4(source)
    catalog = catalogs[graph.id]

    assert VIEW_ONLY_VERSION == "likec4-1.58.0-subset-1"
    assert {"views", "dynamic view", "parallel"} <= VIEW_ONLY_ALLOWLIST
    assert {item["kind"] for item in catalog} == {
        "generated",
        "static",
        "dynamic",
        "external",
    }
    attachment_id = next(item for item in catalog if item["id"] == "overview")[
        "attachmentId"
    ]
    assert attachments[attachment_id]["dataUrl"].startswith(
        "data:image/svg+xml;base64,"
    )
    assert any(
        view["id"]
        == next(item for item in catalog if item["id"] == "systems-static")[
            "likec4View"
        ]
        for view in compiled["views"]
    )


def test_canonical_dynamic_compiles() -> None:
    """canonical-dynamic-compiles: production preparation compiles the authored source."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    data, source = prepare_explorer_data(
        workspace=workspace,
        workspace_root=FIXTURES,
        selections=[{"roadmap": "preferred", "order": 1}],
    )
    graph_id = data["initialGraphId"]
    catalog = data["diagramCatalogByGraph"][graph_id]
    authored = next(item for item in catalog if item["id"] == "platform-delivery")
    assert authored["likec4View"] in {
        view["id"] for view in compile_likec4(source)["views"]
    }


def test_logical_declaration_rejected(tmp_path: Path) -> None:
    """logical-declaration-rejected: authored sources cannot redefine logical content."""
    _workspace, graph = _base_graph()
    path = tmp_path / "bad.c4"
    source = "views {}\nmodel { x = system 'X' }\n"
    with pytest.raises(DiagramCatalogError, match="disallowed 'model'") as raised:
        validate_view_only_source(
            source=source,
            path=path,
            diagram_id="bad",
            canonical_mapping={node.id: node.id for node in graph.nodes},
            graph=graph,
        )
    assert raised.value.code == "arch.likec4_logical_declaration"
    assert raised.value.line == 2


def test_unknown_generated_id(tmp_path: Path) -> None:
    """unknown-generated-id: canonical references must resolve through the mapping."""
    _workspace, graph = _base_graph()
    source = "views {\n  view bad {\n    include @{missing-system}\n  }\n}\n"
    with pytest.raises(DiagramCatalogError, match="missing-system") as raised:
        validate_view_only_source(
            source=source,
            path=tmp_path / "unknown.c4",
            diagram_id="unknown",
            canonical_mapping={node.id: node.id for node in graph.nodes},
            graph=graph,
        )
    assert raised.value.code == "arch.likec4_unknown_generated_id"


def test_invalid_sequence_participant(tmp_path: Path) -> None:
    """invalid-sequence-participant: dynamic steps require leaf participants."""
    _workspace, graph = _base_graph()
    source = "views {\n  dynamic view bad {\n    @{A} -> @{D} 'Call'\n  }\n}\n"
    with pytest.raises(DiagramCatalogError, match="non-leaf participant 'A'") as raised:
        validate_view_only_source(
            source=source,
            path=tmp_path / "sequence.c4",
            diagram_id="sequence",
            canonical_mapping={node.id: node.id for node in graph.nodes},
            graph=graph,
        )
    assert raised.value.code == "arch.invalid_sequence_participant"


def test_diagram_applicability() -> None:
    """diagram-applicability: requested diagrams must apply to the selected context."""
    workspace, _graph = _base_graph()
    restricted = DiagramCatalogEntry(
        id="restricted",
        name="Restricted",
        kind="generated",
        systems=["not-in-state"],
    )
    workspace = workspace.model_copy(
        update={"diagrams": [*workspace.diagrams, restricted]}
    )
    resolved = resolve_view_graph(
        workspace=workspace,
        value={"state": "arch-v2-base", "diagram": "restricted"},
    )
    assert resolved.graph is None
    assert resolved.issues.errors[0].code == "arch.inapplicable_diagram"


def test_unsafe_attachment(tmp_path: Path) -> None:
    """unsafe-attachment: remote, escaping, and unsafe markup are rejected."""
    workspace, graph = _base_graph()
    unsafe = DiagramCatalogEntry(
        id="unsafe",
        name="Unsafe",
        kind="external",
        source="../outside.svg",
    )
    workspace = workspace.model_copy(update={"diagrams": [unsafe]})
    with pytest.raises(DiagramCatalogError) as raised:
        extend_with_diagram_catalog(
            generated=generate_prepared_likec4([graph]),
            graphs=[graph],
            workspace=workspace,
            workspace_root=tmp_path,
        )
    assert raised.value.code == "arch.diagram_path_escape"


def test_attachment_payload_is_deduplicated_across_graphs(tmp_path: Path) -> None:
    """One attachment blob is serialized once even when applicable to many graphs."""
    workspace, graph = _base_graph()
    attachment_path = tmp_path / "assets" / "attachments" / "overview.svg"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'><text>Overview</text></svg>",
        encoding="utf-8",
    )
    workspace = workspace.model_copy(
        update={
            "diagrams": [
                DiagramCatalogEntry(
                    id="overview",
                    name="Overview",
                    kind="external",
                    source="assets/attachments/overview.svg",
                )
            ]
        }
    )
    other = graph.model_copy(update={"id": "other-graph"})
    _source, catalogs, attachments = extend_with_diagram_catalog(
        generated=generate_prepared_likec4([graph, other]),
        graphs=[graph, other],
        workspace=workspace,
        workspace_root=tmp_path,
    )

    assert len(attachments) == 1
    assert (
        catalogs[graph.id][1]["attachmentId"] == catalogs[other.id][1]["attachmentId"]
    )


def test_oversized_attachment_is_rejected_before_read(tmp_path: Path) -> None:
    """Attachment payloads cannot exceed the deterministic per-file budget."""
    workspace, graph = _base_graph()
    attachment_path = tmp_path / "assets" / "attachments" / "large.pdf"
    attachment_path.parent.mkdir(parents=True)
    with attachment_path.open("wb") as handle:
        handle.truncate(MAX_ATTACHMENT_BYTES + 1)
    workspace = workspace.model_copy(
        update={
            "diagrams": [
                DiagramCatalogEntry(
                    id="large",
                    name="Large",
                    kind="external",
                    source="assets/attachments/large.pdf",
                )
            ]
        }
    )

    with pytest.raises(DiagramCatalogError) as raised:
        extend_with_diagram_catalog(
            generated=generate_prepared_likec4([graph]),
            graphs=[graph],
            workspace=workspace,
            workspace_root=tmp_path,
        )

    assert raised.value.code == "arch.attachment_too_large"
