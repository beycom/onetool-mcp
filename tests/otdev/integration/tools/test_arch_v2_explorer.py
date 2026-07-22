"""Production generated-explorer browser and portability tests."""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from otdev.tools import arch
from otdev.tools._arch.v2.frontend import prepare_explorer_data
from otdev.tools._arch.v2.load import load_workspace
from tests.otdev.arch_v2_fixtures import (
    ARCH_V2_FIXTURES,
    write_arch_v2_workspace_with_external_diagram,
)

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES
ROOT = Path(__file__).parents[4]
BROWSER_SCRIPT = (
    ROOT
    / "src"
    / "otdev"
    / "tools"
    / "_arch"
    / "frontend"
    / "scripts"
    / "test-generated-explorer.mjs"
)
EXTERNAL_BROWSER_SCRIPT = (
    ROOT
    / "src"
    / "otdev"
    / "tools"
    / "_arch"
    / "frontend"
    / "scripts"
    / "test-external-diagram.mjs"
)


def _drawio_projection(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    diagram = root.find("diagram")
    assert diagram is not None
    model = diagram.find("mxGraphModel")
    assert model is not None
    nodes: dict[str, Any] = {}
    edges: dict[str, Any] = {}
    for cell in diagram.findall(".//mxCell"):
        if cell.get("vertex") == "1":
            geometry = cell.find("mxGeometry")
            assert geometry is not None
            nodes[cell.attrib["id"]] = {
                "parent": cell.get("parent"),
                "value": cell.get("value"),
                "style": cell.get("style"),
                "kind": cell.get("kind"),
                "status": cell.get("status"),
                "geometry": dict(sorted(geometry.attrib.items())),
            }
        elif cell.get("edge") == "1":
            edges[cell.attrib["id"]] = {
                "source": cell.get("source"),
                "target": cell.get("target"),
                "value": cell.get("value"),
                "style": cell.get("style"),
                "kind": cell.get("kind"),
                "status": cell.get("status"),
                "interfaceIds": cell.get("interfaceIds"),
                "points": [
                    dict(sorted(point.attrib.items()))
                    for point in cell.findall(".//mxPoint")
                ],
            }
    return {
        "selectionId": diagram.attrib["selectionId"],
        "viewGraphId": diagram.attrib["viewGraphId"],
        "selection": json.loads(diagram.attrib["selection"]),
        "bounds": {key: model.attrib[key] for key in ("pageWidth", "pageHeight")},
        "nodes": nodes,
        "edges": edges,
    }


@pytest.fixture(scope="module")
def explorer_proof(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Generate canonical production data and exercise the self-contained report."""
    output = tmp_path_factory.mktemp("explorer path with spaces") / "report with spaces"
    generated = arch.generate(
        input_path=str(FIXTURES / "arch-v2-canonical.yaml"),
        output_path=str(output),
        selections=None,
        force=False,
    )
    assert generated["ok"] is True
    report = output / "architecture-explorer.html"
    completed = subprocess.run(
        [
            "node",
            str(BROWSER_SCRIPT),
            str(report),
            str(output / "visual snapshot.png"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    proof = json.loads(completed.stdout.strip().splitlines()[-1])
    api_output = output / "api-drawio"
    api_export = arch.export(
        input_path=str(FIXTURES / "arch-v2-canonical.yaml"),
        output_path=str(api_output),
        formats=["drawio"],
        selections=[
            {
                "roadmap": "preferred",
                "order": 1,
                "browse_by": "system",
                "subject": "A",
                "interface_depth": 1,
                "visibility": "all",
                "level": "component",
                "color_by": "tag",
                "theme": "clean",
            }
        ],
        drawio_mode="per-view",
        continue_on_error=False,
        force=False,
    )
    assert api_export["ok"] is True
    api_drawio = Path(
        next(
            item["path"]
            for item in api_export["artifacts"]
            if item["path"].endswith(".drawio")
        )
    )
    proof["apiBrowserDrawioParity"] = _drawio_projection(
        Path(proof["drawioPath"])
    ) == _drawio_projection(api_drawio)
    proof["report"] = report
    proof["snapshot_path"] = Path(proof["snapshot"])
    return proof


def test_explorer_groups_preserve_endpoint(explorer_proof: dict[str, Any]) -> None:
    """explorer-groups-preserve-endpoint: navigation does not resolve another state."""
    assert len(set(explorer_proof["snapshotLabels"])) == 3


def test_interface_edge_selects_row() -> None:
    """interface-edge-selects-row: rendered edges retain canonical row identities."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    data, _source = prepare_explorer_data(
        workspace=workspace,
        workspace_root=FIXTURES,
        selections=[{"state": "arch-v2-base"}],
    )
    mappings = next(iter(data["likec4EdgeToCanonicalByGraph"].values()))
    assert "arch-v2-interface-a-to-d" in {
        canonical for values in mappings.values() for canonical in values
    }


def test_saved_external_diagram_is_rendered_offline(tmp_path: Path) -> None:
    """A selected external diagram is restored and rendered without network access."""
    source = write_arch_v2_workspace_with_external_diagram(tmp_path)
    output = tmp_path / "report"
    result = arch.generate(
        input_path=str(source),
        output_path=str(output),
        selections=[{"roadmap": "preferred", "order": 1, "diagram": "overview"}],
        force=False,
    )
    assert result["ok"] is True

    completed = subprocess.run(
        [
            "node",
            str(EXTERNAL_BROWSER_SCRIPT),
            str(output / "architecture-explorer.html"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr


def test_merged_interface_edge() -> None:
    """merged-interface-edge: browser mappings preserve a list of canonical interfaces."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    data, _source = prepare_explorer_data(
        workspace=workspace,
        workspace_root=FIXTURES,
        selections=[{"state": "arch-v2-base"}],
    )
    mappings = next(iter(data["likec4EdgeToCanonicalByGraph"].values()))
    assert mappings
    assert all(isinstance(canonical_ids, list) for canonical_ids in mappings.values())


def test_full_explorer_properties_and_relationships(
    explorer_proof: dict[str, Any],
) -> None:
    """Full explorer exposes canonical properties and nested relationships."""
    assert explorer_proof["fullExplorerDetails"] is True
    assert explorer_proof["interfaceRowFound"] is True


def test_base_2027_2028_offline_switch(explorer_proof: dict[str, Any]) -> None:
    """base-2027-2028-offline-switch: prepared states switch with networking blocked."""
    assert len(set(explorer_proof["snapshotLabels"])) == 3
    assert explorer_proof["networkRequests"] == []
    assert explorer_proof["pageErrors"] == []


def test_browser_controls_change_topology_and_preserve_color_geometry(
    explorer_proof: dict[str, Any],
) -> None:
    """System set, snapshot, depth, level, and color controls affect the diagram itself."""
    assert explorer_proof["baseNodeIds"] != explorer_proof["changedNodeIds"]
    assert explorer_proof["applicationNodeIds"] != explorer_proof["componentNodeIds"]
    assert explorer_proof["changeGroupNodeIds"] == explorer_proof["changeNodeIds"]
    assert explorer_proof["systemGroupNodeIds"] == explorer_proof["tagNodeIds"] == ["A"]
    assert explorer_proof["systemAEdgeIds"] != explorer_proof["systemBEdgeIds"]
    assert "No Change" in explorer_proof["baseDStatus"]
    assert "Removed" in explorer_proof["changedDStatus"]
    assert explorer_proof["colorGeometryStable"] is True
    assert explorer_proof["historyNavigation"] is True
    assert explorer_proof["emptyState"] is True
    assert explorer_proof["urlRestoration"] is True


def test_browser_drawio_matches_active_projection(
    explorer_proof: dict[str, Any],
) -> None:
    """The offline browser export contains the active nodes, selection, and geometry."""
    exported = explorer_proof["drawioExport"]
    assert exported["nodeIds"] == explorer_proof["componentNodeIds"]
    assert exported["selection"]["system_set"]["systems"] == ["A"]
    assert exported["selectionId"] == "selection-736ee4371dab3235"
    assert "compare_from" not in exported["selection"]
    assert exported["edgeIds"]
    assert exported["hasGeometry"] is True
    assert exported["embedsImage"] is False
    assert explorer_proof["apiBrowserDrawioParity"] is True
    assert Path(explorer_proof["drawioPath"]).is_file()


def test_production_report_browser_visual_states(
    explorer_proof: dict[str, Any],
) -> None:
    """Narrow, large, dark, reduced-motion, print, path, and visual states render."""
    assert explorer_proof["report"].is_file()
    assert " " in str(explorer_proof["report"])
    assert explorer_proof["snapshot_path"].is_file()
    assert explorer_proof["snapshot_path"].stat().st_size > 10_000


def test_generated_payload_does_not_precompile_selector_product() -> None:
    """Generated data contains roadmap snapshots, not a Cartesian projection matrix."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    data, _source = prepare_explorer_data(
        workspace=workspace,
        workspace_root=FIXTURES,
        selections=None,
    )
    assert "solutionProjections" not in data
    assert (
        sum(
            len(prepared["snapshots"])
            for prepared in data["solutionSnapshots"].values()
        )
        == 3
    )
