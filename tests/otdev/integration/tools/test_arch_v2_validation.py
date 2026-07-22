"""Unified production validation and publication-gate tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import yaml

from otdev.tools import arch
from otdev.tools._arch.v2.cache import ContentAddressedCache
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES
SOURCE = FIXTURES / "arch-v2-canonical.yaml"


def _payload() -> dict[str, Any]:
    return yaml.safe_load(SOURCE.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "architecture.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_validate_canonical_yaml_excel_identically() -> None:
    """Production validation produces equivalent format-independent counts."""
    yaml_result = arch.validate(input_path=str(SOURCE))
    excel_result = arch.validate(input_path=str(FIXTURES / "arch-v2-canonical.xlsx"))
    assert yaml_result["ok"] is excel_result["ok"] is True
    assert yaml_result["valid"] is excel_result["valid"] is True
    assert yaml_result["data"]["counts"] == excel_result["data"]["counts"]
    assert yaml_result["summary"] == excel_result["summary"]


def test_duplicate_id_all_locations(tmp_path: Path) -> None:
    """duplicate-id-all-locations: one diagnostic retains every conflicting source."""
    payload = _payload()
    payload["diagrams"] = []
    payload["states"][0]["systems"].append(
        {"id": "A", "name": "Duplicate system A"}
    )
    result = arch.validate(input_path=str(_write(tmp_path, payload)))
    duplicate = next(
        issue
        for issue in result["issues"]["errors"]
        if issue["code"] == "arch.duplicate_id" and issue["details"]["id"] == "A"
    )
    assert len(duplicate["locations"]) == 2
    assert all(location["yaml_path"].startswith("states[0].systems[") for location in duplicate["locations"])


def test_roadmap_order_errors(tmp_path: Path) -> None:
    """roadmap-order-errors: gaps retain the roadmap identity."""
    payload = _payload()
    payload["diagrams"] = []
    payload["roadmaps"][0]["items"][1]["order"] = 4
    result = arch.validate(input_path=str(_write(tmp_path, payload)))
    issue = next(
        item
        for item in result["issues"]["errors"]
        if item["code"] == "arch.non_contiguous_roadmap_orders"
    )
    assert issue["identity"]["roadmap"] == "preferred"


def test_reorder_diagnostic_complete(tmp_path: Path) -> None:
    """reorder-diagnostic-complete: dependency diagnostics include actionable order."""
    payload = _payload()
    payload["diagrams"] = []
    payload["changes"][0]["depends_on"] = ["arch-v2-change-2028"]
    result = arch.validate(input_path=str(_write(tmp_path, payload)))
    issue = next(
        item
        for item in result["issues"]["errors"]
        if item["code"] == "arch.invalid_dependency_order"
    )
    assert issue["identity"] == {
        "roadmap": "preferred",
        "order": 1,
        "change": "arch-v2-change-2027",
    }
    assert issue["details"]["suggested_order"] == (
        "apply arch-v2-change-2028 before arch-v2-change-2027"
    )


def test_cascade_diagnostic_trace() -> None:
    """cascade-diagnostic-trace: generated removals retain ancestor, path, and change."""
    result = arch.validate(input_path=str(SOURCE))
    cascades = [
        issue for issue in result["issues"]["warnings"] if issue["code"] == "arch.cascade_expansion"
    ]
    assert cascades
    assert all(issue["identity"]["change"] == "arch-v2-change-2027" for issue in cascades)
    assert all(issue["details"]["initiating_ancestor"] == "D" for issue in cascades)
    assert all(issue["details"]["cascade_path"] for issue in cascades)


def test_selector_reference_errors(tmp_path: Path) -> None:
    """selector-reference-errors: an unknown diagram retains the saved-view identity."""
    payload = _payload()
    payload["diagrams"] = []
    payload["views"][0]["diagram"] = "missing-diagram"
    result = arch.validate(input_path=str(_write(tmp_path, payload)))
    issue = next(
        item for item in result["issues"]["errors"] if item["code"] == "arch.unknown_diagram"
    )
    assert issue["identity"]["view"] == "state-2027"


def test_likec4_location_errors(tmp_path: Path) -> None:
    """likec4-location-errors: disallowed declarations report file, line, and diagram."""
    workspace = tmp_path / "workspace"
    assert arch.init(output_path=str(workspace))["ok"] is True
    source = workspace / "views" / "platform-delivery.c4"
    source.write_text(
        "views {\n  dynamic view platform_delivery {}\n}\ndeployment {\n}\n",
        encoding="utf-8",
    )
    result = arch.validate(input_path=str(workspace))
    issue = next(
        item
        for item in result["issues"]["errors"]
        if item["code"] == "arch.likec4_logical_declaration"
    )
    assert issue["identity"]["diagram"] == "platform-delivery"
    assert issue["details"]["line"] == 4
    assert issue["details"]["path"].endswith("platform-delivery.c4")


def test_asset_path_containment(tmp_path: Path) -> None:
    """asset-path-containment: local icons cannot traverse outside assets/icons."""
    payload = _payload()
    payload["diagrams"] = []
    payload["states"][0]["systems"][0]["icon"] = "@icons/../outside.svg"
    result = arch.validate(input_path=str(_write(tmp_path, payload)))
    assert any(
        issue["code"] == "arch.unsafe_icon_path" for issue in result["issues"]["errors"]
    )


def test_export_prerequisite_and_publication_gate(tmp_path: Path) -> None:
    """export-prerequisite: invalid workspaces publish neither explorer nor exports."""
    payload = _payload()
    payload["diagrams"] = []
    payload["states"][0]["interfaces"][0]["consumer"] = "missing"
    source = _write(tmp_path, payload)
    report = tmp_path / "report"
    exports = tmp_path / "exports"
    generated = arch.generate(input_path=str(source), output_path=str(report))
    exported = arch.export(
        input_path=str(source),
        output_path=str(exports),
        formats=["svg"],
    )
    assert generated["ok"] is exported["ok"] is False
    assert not report.exists()
    assert not exports.exists()


def test_content_addressed_cache_is_immutable() -> None:
    """Cache keys include length-delimited inputs and reject content mutation."""
    cache = ContentAddressedCache()
    key = cache.key(b"source", b"selection", b"theme", b"layout", b"exporter")
    cache.put(key, b"result")
    cache.put(key, b"result")
    assert cache.get(key) == b"result"
    with pytest.raises(ValueError, match="cache collision"):
        cache.put(key, b"different")


def test_content_addressed_cache_evicts_by_entry_and_byte_bounds() -> None:
    """Long-lived renderer caches retain only their configured working set."""
    cache = ContentAddressedCache(max_entries=2, max_bytes=5)
    cache.put("a", b"aa")
    cache.put("b", b"bb")
    assert cache.get("a") == b"aa"
    cache.put("c", b"cc")
    assert cache.get("b") is None
    assert len(cache) == 2
    cache.put("oversized", b"123456")
    assert cache.get("oversized") is None
