"""Tests for the MCP-owned Direct API discovery file."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from ot.direct_discovery import (
    pid_alive,
    remove_discovery_file,
    sweep_stale_discovery_files,
    write_discovery_file,
)


@pytest.mark.unit
@pytest.mark.core
def test_write_discovery_file_has_pinned_shape_and_mode(tmp_path: Path) -> None:
    """The discovery file matches the pinned contract shape and is chmod 0600."""
    path = write_discovery_file(
        instance_id="mcp-abc123", port=8766, pid=12345, base_dir=tmp_path
    )

    assert path == tmp_path / "mcp-abc123.json"
    payload = json.loads(path.read_text())
    assert payload == {
        "instance_id": "mcp-abc123",
        "port": 8766,
        "pid": 12345,
        "started_at": payload["started_at"],
    }
    # started_at is a parseable ISO-8601 UTC timestamp.
    datetime.fromisoformat(payload["started_at"])

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600

    # No leftover temp files from the atomic write.
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.unit
@pytest.mark.core
def test_write_discovery_file_creates_parent_dirs(tmp_path: Path) -> None:
    """Writing the discovery file creates the runtime/direct-api dir tree as needed."""
    nested = tmp_path / "runtime" / "direct-api"
    assert not nested.exists()

    path = write_discovery_file(instance_id="mcp-nested", port=8767, base_dir=nested)

    assert path.exists()
    assert nested.is_dir()


@pytest.mark.unit
@pytest.mark.core
def test_write_discovery_file_defaults_pid_to_current_process(tmp_path: Path) -> None:
    """When `pid` is omitted, the discovery file records the current process pid."""
    path = write_discovery_file(instance_id="mcp-self", port=8768, base_dir=tmp_path)

    payload = json.loads(path.read_text())
    assert payload["pid"] == os.getpid()


@pytest.mark.unit
@pytest.mark.core
def test_remove_discovery_file_deletes_existing_file(tmp_path: Path) -> None:
    """Clean shutdown removes the discovery file for the current instance."""
    write_discovery_file(instance_id="mcp-remove-me", port=8769, base_dir=tmp_path)
    assert (tmp_path / "mcp-remove-me.json").exists()

    remove_discovery_file(instance_id="mcp-remove-me", base_dir=tmp_path)

    assert not (tmp_path / "mcp-remove-me.json").exists()


@pytest.mark.unit
@pytest.mark.core
def test_remove_discovery_file_is_a_noop_when_missing(tmp_path: Path) -> None:
    """Removing a discovery file that was never written does not raise."""
    remove_discovery_file(instance_id="mcp-never-existed", base_dir=tmp_path)


@pytest.mark.unit
@pytest.mark.core
def test_pid_alive_reports_current_process_as_alive() -> None:
    """The current test process is alive by definition."""
    assert pid_alive(os.getpid()) is True


@pytest.mark.unit
@pytest.mark.core
def test_pid_alive_reports_dead_pid_as_not_alive() -> None:
    """A pid with no live process is reported as not alive."""
    with patch("ot.direct_discovery.os.kill", side_effect=ProcessLookupError):
        assert pid_alive(999999) is False


@pytest.mark.unit
@pytest.mark.core
def test_sweep_removes_sibling_with_dead_pid(tmp_path: Path) -> None:
    """Startup sweep removes sibling discovery files whose pid is not alive."""
    alive_path = write_discovery_file(
        instance_id="mcp-alive", port=8770, pid=os.getpid(), base_dir=tmp_path
    )
    dead_path = write_discovery_file(
        instance_id="mcp-dead", port=8771, pid=424242, base_dir=tmp_path
    )

    def _fake_pid_alive(pid: int) -> bool:
        return pid == os.getpid()

    with patch("ot.direct_discovery.pid_alive", side_effect=_fake_pid_alive):
        removed = sweep_stale_discovery_files(base_dir=tmp_path)

    assert removed == [dead_path]
    assert alive_path.exists()
    assert not dead_path.exists()


@pytest.mark.unit
@pytest.mark.core
def test_sweep_removes_malformed_sibling_file(tmp_path: Path) -> None:
    """A sibling file that cannot be parsed is treated as stale and removed."""
    bad_path = tmp_path / "mcp-bad.json"
    bad_path.write_text("not json")

    removed = sweep_stale_discovery_files(base_dir=tmp_path)

    assert removed == [bad_path]
    assert not bad_path.exists()


@pytest.mark.unit
@pytest.mark.core
def test_sweep_returns_empty_when_directory_missing(tmp_path: Path) -> None:
    """Sweeping a directory that does not exist yet is a no-op, not an error."""
    missing = tmp_path / "does-not-exist"

    assert sweep_stale_discovery_files(base_dir=missing) == []
