"""Runs only in the independent installed-wheel environment."""

import os
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    "ONETOOL_INSTALLED_ROOT" not in os.environ, reason="installed-wheel proof runs outside checkout"
)
def test_installed_identity_and_python_floor() -> None:
    import onetool

    expected = Path(os.environ["ONETOOL_INSTALLED_ROOT"]).resolve()
    assert Path(onetool.__file__).resolve().is_relative_to(expected)
    assert "site-packages" in Path(onetool.__file__).parts
    assert sys.version_info[:2] == (3, 12)
    assert onetool.__version__ == "4.0.0rc1"
