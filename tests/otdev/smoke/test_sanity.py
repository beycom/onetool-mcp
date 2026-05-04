"""Smoke tests for onetool-dev - verify basic functionality."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pkg


@pytest.mark.smoke
def test_import_package() -> None:
    """Test that the package can be imported."""
    import otdev

    assert otdev.__version__ == "1.0.0"
    assert otdev.__package_name__ == "onetool-dev"


@pytest.mark.smoke
def test_import_tool_modules() -> None:
    """Test that all tool modules can be imported."""
    from otdev.tools import arch, context7, db, diagram, package, ripgrep, webfetch

    # Check pack names (alphabetical order)
    assert arch.pack == "arch"
    assert context7.pack == "context7"
    assert db.pack == "db"
    assert diagram.pack == "diagram"
    assert package.pack == "package"
    assert ripgrep.pack == "ripgrep"
    assert webfetch.pack == "webfetch"
