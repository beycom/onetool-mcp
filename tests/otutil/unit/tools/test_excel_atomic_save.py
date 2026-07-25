"""Failure-injection tests for Excel's atomic workbook save boundary."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

openpyxl = pytest.importorskip(
    "openpyxl",
    reason="openpyxl not installed (install onetool-mcp[util])",
)

_MUTATION_CASES = (
    "create",
    "add_sheet",
    "write",
    "formula",
    "insert_rows",
    "delete_rows",
    "insert_cols",
    "delete_cols",
    "copy_range",
    "create_table",
)


def _seed_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.append(["Name", "Value"])
    worksheet.append(["before", 1])
    workbook.save(path)
    workbook.close()


def _invoke(case: str, target: Path) -> str:
    from otutil.tools import excel

    calls = {
        "create": lambda: excel.create(filepath=str(target)),
        "add_sheet": lambda: excel.add_sheet(
            filepath=str(target), sheet_name="Summary"
        ),
        "write": lambda: excel.write(
            filepath=str(target), data=[["after", 2]], start_cell="A2"
        ),
        "formula": lambda: excel.formula(
            filepath=str(target), cell="B2", formula="=1+1"
        ),
        "insert_rows": lambda: excel.insert_rows(filepath=str(target), row=2),
        "delete_rows": lambda: excel.delete_rows(filepath=str(target), row=2),
        "insert_cols": lambda: excel.insert_cols(filepath=str(target), col="B"),
        "delete_cols": lambda: excel.delete_cols(filepath=str(target), col="B"),
        "copy_range": lambda: excel.copy_range(
            filepath=str(target), source_range="A1:B2", target_cell="D1"
        ),
        "create_table": lambda: excel.create_table(
            filepath=str(target), data_range="A1:B2", table_name="DataTable"
        ),
    }
    return calls[case]()


def _temp_residue(target: Path) -> list[Path]:
    return list(target.parent.glob(f".{target.name}.tmp-*"))


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("case", _MUTATION_CASES)
@pytest.mark.parametrize("failure", ("save", "validation"))
def test_mutation_failure_preserves_target_and_cleans_temp(
    tmp_path: Path,
    case: str,
    failure: str,
) -> None:
    from otutil.tools import excel

    target = tmp_path / f"{case}.xlsx"
    if case != "create":
        _seed_workbook(target)
        original = target.read_bytes()
    else:
        original = None

    if failure == "save":
        failure_patch = patch.object(
            openpyxl.Workbook,
            "save",
            side_effect=OSError("injected save failure"),
        )
    else:
        failure_patch = patch.object(
            excel,
            "_validate_saved_workbook",
            side_effect=ValueError("injected validation failure"),
        )

    with failure_patch:
        result = _invoke(case, target)

    assert result == f"Error: injected {failure} failure"
    if original is None:
        assert not target.exists()
    else:
        assert target.read_bytes() == original
        validated = openpyxl.load_workbook(target)
        validated.close()
    assert _temp_residue(target) == []


@pytest.mark.unit
@pytest.mark.tools
def test_simultaneous_safe_saves_use_distinct_temps(tmp_path: Path) -> None:
    from otutil.tools.excel import _safe_save_workbook

    target = tmp_path / "shared.xlsx"
    barrier = threading.Barrier(2)
    recorded_paths: list[Path] = []
    record_lock = threading.Lock()
    original_save = openpyxl.Workbook.save

    first = openpyxl.Workbook()
    second = openpyxl.Workbook()
    assert first.active is not None
    assert second.active is not None
    first.active["A1"] = "first"
    second.active["A1"] = "second"

    def synchronized_save(workbook: Any, filename: str | Path) -> None:
        with record_lock:
            recorded_paths.append(Path(filename))
        barrier.wait(timeout=5)
        original_save(workbook, filename)

    with (
        patch.object(openpyxl.Workbook, "save", new=synchronized_save),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        futures = [
            executor.submit(_safe_save_workbook, first, target),
            executor.submit(_safe_save_workbook, second, target),
        ]
        for future in futures:
            future.result(timeout=10)

    assert len(recorded_paths) == 2
    assert len(set(recorded_paths)) == 2
    assert all(path.parent == target.parent for path in recorded_paths)
    assert _temp_residue(target) == []
    validated = openpyxl.load_workbook(target)
    assert validated.active is not None
    assert validated.active["A1"].value in {"first", "second"}
    validated.close()
