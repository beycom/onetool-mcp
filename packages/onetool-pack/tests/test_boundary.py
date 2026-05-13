"""Test that the otpack import boundary is clean."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_otpack_boundary.py"


@pytest.mark.unit
@pytest.mark.pkg
def test_boundary_check_passes() -> None:
    """check_otpack_boundary.py must exit 0 (no violations)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Boundary check failed:\n{result.stdout}\n{result.stderr}"
    )


@pytest.mark.unit
@pytest.mark.pkg
def test_allowed_file_rejects_bare_onetool_import(tmp_path: Path) -> None:
    """Allowed shim files still reject bare imports outside try/except."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    path = tmp_path / "config.py"
    path.write_text("import ot\n")

    errors = module.check_file(path, allow_ot_imports=True)
    assert errors


@pytest.mark.unit
@pytest.mark.pkg
def test_allowed_file_permits_try_wrapped_onetool_import(tmp_path: Path) -> None:
    """Allowed shim files permit optional imports inside try/except."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    path = tmp_path / "config.py"
    path.write_text("try:\n    import ot\nexcept ImportError:\n    ot = None\n")

    assert module.check_file(path, allow_ot_imports=True) == []
