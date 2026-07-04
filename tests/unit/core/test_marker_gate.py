"""Proves the required-marker collection gate fails fast (p22 M5)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_unmarked_test(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    test_file = directory / "test_deliberately_unmarked.py"
    test_file.write_text(
        "def test_no_markers_at_all():\n    assert True\n", encoding="utf-8"
    )
    return test_file


@pytest.mark.unit
@pytest.mark.core
def test_missing_marker_fails_by_default_and_skips_with_flag(tmp_path: Path) -> None:
    # Live under tests/ so the temp file inherits tests/conftest.py's marker gate.
    tmp_dir = _REPO_ROOT / "tests" / "_marker_gate_tmp"
    test_file = _write_unmarked_test(tmp_dir)
    try:
        base = [sys.executable, "-m", "pytest", str(test_file), "-q", "-p", "no:cacheprovider"]

        default_run = subprocess.run(
            base, cwd=_REPO_ROOT, capture_output=True, text=True, check=False
        )
        assert default_run.returncode != 0, default_run.stdout + default_run.stderr
        assert "missing" in (default_run.stdout + default_run.stderr).lower()

        allow_run = subprocess.run(
            [*base, "--allow-skips"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert allow_run.returncode == 0, allow_run.stdout + allow_run.stderr
        assert "skip" in (allow_run.stdout + allow_run.stderr).lower()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
