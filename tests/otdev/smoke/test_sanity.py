"""Smoke tests for onetool-dev - verify basic functionality."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pkg


@pytest.mark.smoke
@pytest.mark.tools
def test_import_package() -> None:
    """Test that the package can be imported."""
    import otdev

    assert otdev.__version__ == "1.0.0"
    assert otdev.__package_name__ == "onetool-dev"


@pytest.mark.smoke
@pytest.mark.tools
def test_import_tool_modules() -> None:
    """Test that all tool modules can be imported."""
    from otdev.tools import (
        arch,
        context7,
        db,
        diagram,
        localhist,
        package,
        ripgrep,
        webfetch,
    )

    # Check pack names (alphabetical order)
    assert arch.pack == "arch"
    assert context7.pack == "context7"
    assert db.pack == "db"
    assert diagram.pack == "diagram"
    assert localhist.pack == "localhist"
    assert package.pack == "package"
    assert ripgrep.pack == "ripgrep"
    assert webfetch.pack == "webfetch"


@pytest.mark.smoke
@pytest.mark.tools
def test_localhist_minimal_workflow(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Verify localhist can init, save, and log in isolated project state."""
    from otdev.tools import localhist

    monkeypatch.setenv("OT_CWD", str(tmp_path))
    (tmp_path / "note.txt").write_text("hello\n")
    assert localhist.init()["ok"] is True
    assert localhist.status()["initialized"] is True
    assert localhist.save(message="smoke")["created"] is True
    assert len(localhist.log(limit=1)["entries"]) == 1
