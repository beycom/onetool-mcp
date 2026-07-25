"""Public project-path contract tests."""

from __future__ import annotations

import importlib.util

import pytest

import otpack


@pytest.mark.unit
@pytest.mark.pkg
def test_project_state_directory_surface_is_path_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("OT_CWD", str(tmp_path))

    assert otpack.get_project_state_dir("bridge") == (
        tmp_path / ".onetool" / "state" / "bridge"
    )
    assert "get_project_state_dir" in otpack.__all__
    assert "get_state" not in otpack.__all__
    assert "set_state" not in otpack.__all__
    assert not hasattr(otpack, "get_state")
    assert not hasattr(otpack, "set_state")
    assert importlib.util.find_spec("otpack.state") is None
