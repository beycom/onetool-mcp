"""Tests for project-local otpack state helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.pkg
def test_state_returns_default_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing project state returns the caller default."""
    import otpack.state as state

    monkeypatch.setattr(state, "get_effective_cwd", lambda: tmp_path)

    assert state.get_state("ide", "connection_id") is None
    assert state.get_state("ide", "connection_id", "default") == "default"


@pytest.mark.unit
@pytest.mark.pkg
def test_state_writes_pack_scoped_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """set_state creates .onetool/state.yaml and scopes values by pack."""
    import otpack.state as state

    monkeypatch.setattr(state, "get_effective_cwd", lambda: tmp_path)

    state.set_state("ide", "connection_id", "onetool-mcp")

    path = tmp_path / ".onetool" / "state.yaml"
    data = yaml.safe_load(path.read_text())
    assert data == {
        "packs": {"ide": {"connection_id": "onetool-mcp"}},
        "version": 1,
    }
    assert state.get_state("ide", "connection_id") == "onetool-mcp"


@pytest.mark.unit
@pytest.mark.pkg
def test_state_rejects_unsupported_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only state version 1 is accepted."""
    import otpack.state as state

    monkeypatch.setattr(state, "get_effective_cwd", lambda: tmp_path)
    path = tmp_path / ".onetool" / "state.yaml"
    path.parent.mkdir()
    path.write_text("version: 2\npacks: {}\n")

    with pytest.raises(ValueError, match="Unsupported OneTool state version"):
        state.get_state("ide", "connection_id")


@pytest.mark.unit
@pytest.mark.pkg
def test_state_rejects_malformed_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed YAML raises a clear state error."""
    import otpack.state as state

    monkeypatch.setattr(state, "get_effective_cwd", lambda: tmp_path)
    path = tmp_path / ".onetool" / "state.yaml"
    path.parent.mkdir()
    path.write_text("version: [")

    with pytest.raises(ValueError, match="Malformed OneTool state file"):
        state.get_state("ide", "connection_id")
