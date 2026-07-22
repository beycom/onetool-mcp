"""Production schema-v2 batch exporter tests."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from otdev.tools import arch
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.write import strip_sources
from tests.otdev.arch_v2_fixtures import (
    ARCH_V2_FIXTURES,
    write_arch_v2_workspace_with_external_diagram,
)

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES
SOURCE = FIXTURES / "arch-v2-canonical.yaml"


def _export(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    arguments = {
        "input_path": str(SOURCE),
        "output_path": str(tmp_path / "exports"),
        "formats": ["svg"],
        "selections": [{"state": "arch-v2-base"}],
        "drawio_mode": "per-view",
        "continue_on_error": False,
        "force": False,
    }
    arguments.update(overrides)
    return arch.export(**arguments)


def _artifact(result: dict[str, Any], suffix: str) -> Path:
    return Path(
        next(
            item["path"]
            for item in result["artifacts"]
            if item["path"].endswith(suffix)
        )
    )


def test_svg_all_diagram_classes(tmp_path: Path) -> None:
    """svg-all-diagram-classes: independent XML parsing sees direct dynamic geometry."""
    result = _export(
        tmp_path,
        selections=[
            {"roadmap": "preferred", "order": 1, "diagram": "platform-delivery"}
        ],
    )
    assert result["ok"] is True
    svg = _artifact(result, ".svg")
    root = ET.parse(svg).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    assert root.attrib["data-selection-id"] == result["selections"][0]
    assert {
        item.attrib["id"] for item in root.findall(".//svg:g[@data-kind]", namespace)
    } == {"B", "C"}
    dynamic_edges = root.findall(".//svg:polyline", namespace)
    assert len(dynamic_edges) == 1
    assert dynamic_edges[0].attrib["data-source"] == "B"
    assert dynamic_edges[0].attrib["data-target"] == "C"


def test_drawio_per_view_multitab(tmp_path: Path) -> None:
    """drawio-per-view-multitab: native editable outputs parse in both modes."""
    per_view = _export(tmp_path, formats=["drawio"])
    assert per_view["ok"] is True
    per_root = ET.parse(_artifact(per_view, ".drawio")).getroot()
    assert per_root.tag == "mxfile"
    assert len(per_root.findall("diagram")) == 1
    assert per_root.find("diagram").attrib["name"] == (
        "arch-v2-base · All systems · System · depth 0"
    )

    multi = _export(
        tmp_path,
        output_path=str(tmp_path / "multi"),
        formats=["drawio"],
        selections=[{"state": "arch-v2-base"}, {"roadmap": "preferred", "order": 1}],
        drawio_mode="multi-tab",
    )
    multi_root = ET.parse(_artifact(multi, ".drawio")).getroot()
    pages = multi_root.findall("diagram")
    assert len(pages) == 2
    assert len({page.attrib["id"] for page in pages}) == 2
    assert [page.attrib["name"] for page in pages] == [
        "arch-v2-base · All systems · System · depth 0",
        "2027 delivery · All systems · System · depth 0",
    ]


def test_drawio_active_projection_geometry_metadata_and_determinism(
    tmp_path: Path,
) -> None:
    """Draw.io is an editable deterministic rendering of the normalized projection."""
    selection = {
        "roadmap": "preferred",
        "order": 0,
        "system_set": {"systems": ["A"]},
        "interface_depth": 1,
        "level": "component",
        "color_by": "change_status",
        "theme": "clean",
    }
    first = _export(
        tmp_path,
        formats=["drawio"],
        selections=[selection],
    )
    second = _export(
        tmp_path,
        output_path=str(tmp_path / "second"),
        formats=["drawio"],
        selections=[selection],
    )
    first_path = _artifact(first, ".drawio")
    assert first_path.read_bytes() == _artifact(second, ".drawio").read_bytes()
    assert first_path.name == "arch-v2-base-a-preferred-0-n1-component.drawio"

    root = ET.parse(first_path).getroot()
    diagram = root.find("diagram")
    assert diagram is not None
    assert diagram.attrib["selectionId"] == first["selections"][0]
    assert diagram.attrib["viewGraphId"].startswith("solution-")
    assert diagram.attrib["snapshotId"] == "arch-v2-base@preferred:0"
    normalized = json.loads(diagram.attrib["selection"])
    assert normalized["system_set"] == {
        "systems": ["A"],
        "system_groups": [],
        "changes": [],
        "change_groups": [],
        "tags": [],
    }
    assert normalized | {"roadmap": "preferred", "order": 0} == normalized
    cells = {cell.attrib["id"]: cell for cell in diagram.findall(".//mxCell")}
    assert {
        cell_id for cell_id, cell in cells.items() if cell.get("vertex") == "1"
    } == {
        "A",
        "D",
        "app-a",
        "app-d",
        "cmp-d",
    }
    assert cells["app-a"].attrib["parent"] == "A"
    assert cells["cmp-d"].attrib["parent"] == "app-d"
    assert "fillColor=#D5E8D4" in cells["A"].attrib["style"]
    edge = cells["arch-v2-interface-a-to-d"]
    assert (
        edge.attrib
        | {
            "source": "app-a",
            "target": "app-d",
            "canonicalId": "arch-v2-interface-a-to-d",
            "interfaceIds": "arch-v2-interface-a-to-d",
            "kind": "interface",
        }
        == edge.attrib
    )
    assert len(edge.findall(".//mxPoint")) >= 2
    assert all(
        cell.find("mxGeometry") is not None
        for cell in cells.values()
        if cell.get("vertex") == "1"
    )
    assert root.find(".//image") is None and root.find(".//svg") is None


def test_drawio_does_not_add_boundary_nodes(tmp_path: Path) -> None:
    """A listed boundary interface does not expand the exported projection."""
    result = _export(
        tmp_path,
        formats=["drawio"],
        selections=[
            {
                "roadmap": "preferred",
                "order": 0,
                "system_set": {"systems": ["A"]},
                "interface_depth": 0,
            }
        ],
    )
    root = ET.parse(_artifact(result, ".drawio")).getroot()
    assert {cell.attrib["id"] for cell in root.findall(".//mxCell[@vertex='1']")} == {
        "A"
    }
    assert root.findall(".//mxCell[@edge='1']") == []


def test_svg_drawio_match_explorer_layout(tmp_path: Path) -> None:
    """svg-drawio-match-explorer-layout: both formats retain the same selected view."""
    result = _export(tmp_path, formats=["svg", "drawio"])
    svg = ET.parse(_artifact(result, ".svg")).getroot()
    drawio = ET.parse(_artifact(result, ".drawio")).getroot()
    assert svg.attrib["data-selection-id"] == result["selections"][0]
    assert drawio.find("diagram") is not None
    assert drawio.find("diagram").attrib["name"] == (
        "arch-v2-base · All systems · System · depth 0"
    )


def test_no_placeholder_or_renamed_output(tmp_path: Path) -> None:
    """no-placeholder-or-renamed-output: SVG is semantic geometry, not an intermediary."""
    result = _export(tmp_path)
    content = _artifact(result, ".svg").read_text(encoding="utf-8")
    assert '<polyline id="arch-v2-interface-a-to-d"' in content
    assert '<g id="A"' in content
    assert "placeholder" not in content.lower()
    assert "drawio" not in content.lower()


def test_state_yaml_excel_export_equivalent(tmp_path: Path) -> None:
    """state-yaml-excel-export-equivalent: both state formats normalize identically."""
    result = _export(
        tmp_path,
        formats=["yaml", "excel"],
        selections=[{"roadmap": "preferred", "order": 1}],
    )
    yaml_state = load_workspace(_artifact(result, ".yaml")).workspace.states[0]
    excel_state = load_workspace(_artifact(result, ".xlsx")).workspace.states[0]
    assert strip_sources(yaml_state.model_dump(mode="json")) == strip_sources(
        excel_state.model_dump(mode="json")
    )


def test_likec4_source_id_map(tmp_path: Path) -> None:
    """likec4-source-id-map: generated source discloses deterministic canonical IDs."""
    result = _export(tmp_path, formats=["likec4"])
    content = _artifact(result, ".c4").read_text(encoding="utf-8")
    assert content.startswith("// canonical-id-map: {")
    assert '"A":"sta_viewgraph_' in content
    assert "specification {" in content and "views {" in content


def test_export_selection_dedup(tmp_path: Path) -> None:
    """export-selection-dedup: equivalent requests share one artifact identity."""
    result = _export(
        tmp_path,
        selections=[{"roadmap": "preferred", "order": 1}, "state-2027"],
    )
    assert result["ok"] is True
    assert len(result["selections"]) == 1
    assert len(result["data"]["request_map"]) == 2
    assert len([item for item in result["artifacts"] if item["format"] == "svg"]) == 1


def test_manifest_incremental_reuse(tmp_path: Path) -> None:
    """manifest-incremental-reuse: unchanged content is not rewritten."""
    first = _export(tmp_path, formats=["svg", "yaml"])
    svg = _artifact(first, ".svg")
    modified = svg.stat().st_mtime_ns
    second = _export(tmp_path, formats=["svg", "yaml"])
    assert all(
        item["status"] == "reused"
        for item in second["artifacts"]
        if item["format"] in {"svg", "yaml"}
    )
    assert svg.stat().st_mtime_ns == modified


def test_stale_owned_safe_cleanup(tmp_path: Path) -> None:
    """stale-owned-safe-cleanup: later exports remove only prior manifest artifacts."""
    output = tmp_path / "exports"
    user_file = output / "notes.txt"
    first = _export(tmp_path, formats=["svg", "yaml"])
    user_file.write_text("keep", encoding="utf-8")
    svg = _artifact(first, ".svg")
    second = _export(tmp_path, formats=["yaml"])
    assert not svg.exists()
    assert user_file.read_text(encoding="utf-8") == "keep"
    assert any(item["status"] == "removed_stale" for item in second["artifacts"])


def test_protect_user_owned_output(tmp_path: Path) -> None:
    """protect-user-owned-output: nonempty destinations require explicit force."""
    output = tmp_path / "exports"
    output.mkdir()
    (output / "mine.txt").write_text("mine", encoding="utf-8")
    result = _export(tmp_path)
    assert result["ok"] is False
    assert result["issues"]["errors"][0]["code"] == "arch.export_failed"
    assert not (output / "manifest.json").exists()


def test_partial_export_envelope(tmp_path: Path) -> None:
    """partial-export-envelope: supported artifacts continue beside explicit failures."""
    result = _export(
        tmp_path,
        formats=["yaml", "unsupported-document"],
        continue_on_error=True,
    )
    assert result["ok"] is False
    assert result["partial"] is True
    assert result["summary"]["failed"] == 1
    assert result["summary"]["generated"] >= 2
    assert _artifact(result, ".yaml").is_file()
    assert result["issues"]["errors"][0]["code"] == "arch.unsupported_export_format"


def test_unsupported_fidelity_diagnostic(tmp_path: Path) -> None:
    """unsupported-fidelity-diagnostic: native Draw.io lists exact React-only limits."""
    result = _export(tmp_path, formats=["drawio"])
    drawio = next(item for item in result["artifacts"] if item["format"] == "drawio")
    assert drawio["fidelity"] == [
        "React-only inspector fields and non-color status glyphs are not represented"
    ]
    manifest = json.loads(
        _artifact(result, "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["artifacts"][0]["fidelity"] == drawio["fidelity"]


def test_external_diagram_visual_export_fails_without_silent_fallback(
    tmp_path: Path,
) -> None:
    """External selections fail visual export while independent state export continues."""
    source = write_arch_v2_workspace_with_external_diagram(tmp_path / "workspace")
    result = arch.export(
        input_path=str(source),
        output_path=str(tmp_path / "exports"),
        formats=["svg", "yaml"],
        selections=[{"roadmap": "preferred", "order": 1, "diagram": "overview"}],
        continue_on_error=True,
    )

    assert result["ok"] is False
    assert result["partial"] is True
    assert result["issues"]["errors"][0]["code"] == (
        "arch.unsupported_external_diagram_export"
    )
    outcomes = {item["format"]: item["status"] for item in result["artifacts"]}
    assert outcomes["svg"] == "failed"
    assert outcomes["yaml"] == "generated"
