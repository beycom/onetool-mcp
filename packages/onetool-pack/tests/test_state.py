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

    monkeypatch.setenv("OT_CWD", str(tmp_path))

    assert state.get_state("bridge", "connection_id") is None
    assert state.get_state("bridge", "connection_id", "default") == "default"


@pytest.mark.unit
@pytest.mark.pkg
def test_state_writes_pack_scoped_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """set_state creates .onetool/state/{pack}/state.yaml with pack-owned values."""
    import otpack.state as state

    monkeypatch.setenv("OT_CWD", str(tmp_path))

    state.set_state("bridge", "connection_id", "onetool-mcp")

    path = tmp_path / ".onetool" / "state" / "bridge" / "state.yaml"
    content = path.read_text()
    data = yaml.safe_load(content)
    assert data == {"connection_id": "onetool-mcp"}
    assert state.get_state("bridge", "connection_id") == "onetool-mcp"


@pytest.mark.unit
@pytest.mark.pkg
def test_state_accepts_explicit_path(tmp_path: Path) -> None:
    """State helpers can read/write a caller-selected state file."""
    import otpack.state as state

    state_path = tmp_path / "custom-state.yaml"
    state.set_state("sample_pack", "enabled", True, state_path=state_path)

    assert state.get_state("sample_pack", "enabled", state_path=state_path) is True


@pytest.mark.unit
@pytest.mark.pkg
def test_state_ignores_stale_shared_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy shared state files are not read as aliases."""
    import otpack.state as state

    monkeypatch.setenv("OT_CWD", str(tmp_path))
    path = tmp_path / ".onetool" / "state.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("version: 2\npacks: {}\n")

    assert state.get_state("bridge", "connection_id", "default") == "default"


@pytest.mark.unit
@pytest.mark.pkg
def test_state_rejects_malformed_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed YAML raises a clear state error."""
    import otpack.state as state

    monkeypatch.setenv("OT_CWD", str(tmp_path))
    path = tmp_path / ".onetool" / "state" / "bridge" / "state.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("version: [")

    with pytest.raises(ValueError, match="Malformed OneTool state file"):
        state.get_state("bridge", "connection_id")
