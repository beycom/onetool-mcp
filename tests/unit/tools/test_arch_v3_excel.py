"""Schema-v3 Excel adapter control tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from otdev.tools._arch.v3.excel import (
    WorkbookError,
    generate_template,
    import_workbook,
    read_workbook,
    write_workbook,
)
from otdev.tools._arch.v3.yamlio import load_architecture

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_acme_model_round_trip(tmp_path: Path) -> None:
    fixture = Path("tests/unit/tools/fixtures/arch/acme.yaml")
    architecture = load_architecture(fixture)
    workbook = tmp_path / "acme.xlsx"

    write_workbook(architecture, workbook)

    assert read_workbook(workbook) == architecture


def test_failed_import_leaves_yaml_byte_identical(tmp_path: Path) -> None:
    workbook_path = tmp_path / "broken.xlsx"
    yaml_path = tmp_path / "architecture.yaml"
    original = b"existing canonical bytes\n"
    yaml_path.write_bytes(original)
    generate_template(workbook_path)
    workbook = load_workbook(workbook_path)
    sheet = workbook["Subsystems"]
    sheet["A2"] = "orphan"
    sheet["B2"] = "Orphan"
    sheet["C2"] = "missing-system"
    workbook.save(workbook_path)
    workbook.close()

    with pytest.raises(WorkbookError, match="unresolved_parent"):
        import_workbook(workbook_path, yaml_path)

    assert yaml_path.read_bytes() == original
