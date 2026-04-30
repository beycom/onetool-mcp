"""Unit tests for execution server PID file read/write/stale handling (per-port)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_pid_file_factory(tmp_path: Path):
    """Return a _pid_file side_effect that uses tmp_path."""
    def _factory(port: int) -> Path:
        return tmp_path / f"direct-server-{port}.pid"
    return _factory


def _make_log_file_factory(tmp_path: Path):
    """Return a _log_file side_effect that uses tmp_path."""
    def _factory(port: int) -> Path:
        return tmp_path / f"direct-server-{port}.log"
    return _factory


@pytest.mark.unit
@pytest.mark.core
class TestPidFile:
    def _direct_app(self) -> object:
        import onetool.cli_commands.direct_app as da
        return da

    def test_pid_file_path_includes_port(self) -> None:
        da = self._direct_app()
        p = da._pid_file(8765)
        assert "8765" in p.name
        p2 = da._pid_file(9000)
        assert "9000" in p2.name
        assert p != p2

    def test_pid_file_uses_direct_prefix(self) -> None:
        da = self._direct_app()
        p = da._pid_file(8765)
        assert "direct-server" in p.name

    def test_read_absent_returns_none(self, tmp_path: Path) -> None:
        da = self._direct_app()
        with patch("onetool.cli_commands.direct_app._pid_file", side_effect=_make_pid_file_factory(tmp_path)):
            result = da._read_pid_file(8765)
        assert result is None

    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        da = self._direct_app()
        with (
            patch("onetool.cli_commands.direct_app._pid_file", side_effect=_make_pid_file_factory(tmp_path)),
            patch("onetool.cli_commands.direct_app._log_file", side_effect=_make_log_file_factory(tmp_path)),
        ):
            da._write_pid_file(12345, 8765, "/path/to/onetool.yaml", None)
            info = da._read_pid_file(8765)
        assert info is not None
        assert info["pid"] == 12345
        assert info["port"] == 8765
        assert info["config"] == "/path/to/onetool.yaml"
        assert info["secrets"] is None
        assert "started" in info
        assert "log" in info

    def test_two_ports_have_separate_files(self, tmp_path: Path) -> None:
        da = self._direct_app()
        with (
            patch("onetool.cli_commands.direct_app._pid_file", side_effect=_make_pid_file_factory(tmp_path)),
            patch("onetool.cli_commands.direct_app._log_file", side_effect=_make_log_file_factory(tmp_path)),
        ):
            da._write_pid_file(111, 8765, None, None)
            da._write_pid_file(222, 9000, None, None)
            info_a = da._read_pid_file(8765)
            info_b = da._read_pid_file(9000)
        assert info_a["pid"] == 111
        assert info_b["pid"] == 222

    def test_remove_pid_file(self, tmp_path: Path) -> None:
        da = self._direct_app()
        pid_file = tmp_path / "direct-server-8765.pid"
        pid_file.write_text(json.dumps({"pid": 1, "port": 8765, "started": time.time()}))
        with patch("onetool.cli_commands.direct_app._pid_file", side_effect=_make_pid_file_factory(tmp_path)):
            da._remove_pid_file(8765)
        assert not pid_file.exists()

    def test_remove_absent_pid_file_is_silent(self, tmp_path: Path) -> None:
        da = self._direct_app()
        with patch("onetool.cli_commands.direct_app._pid_file", side_effect=_make_pid_file_factory(tmp_path)):
            da._remove_pid_file(8765)  # should not raise

    def test_is_process_alive_with_own_pid(self) -> None:
        da = self._direct_app()
        import os
        assert da._is_process_alive(os.getpid()) is True

    def test_is_process_alive_with_invalid_pid(self) -> None:
        da = self._direct_app()
        # PID 0 is invalid for kill() purposes — platform-dependent, must return a bool
        result = da._is_process_alive(0)
        assert isinstance(result, bool)

    def test_stale_pid_is_detected(self) -> None:
        da = self._direct_app()
        alive = da._is_process_alive(2_000_000)
        assert alive is False

    def test_status_includes_config_and_secrets_when_present(self) -> None:
        da = self._direct_app()
        with (
            patch("onetool.cli_commands.direct_app._read_pid_file", return_value={
                "pid": 12345,
                "port": 8765,
                "started": 1000.0,
                "log": "/tmp/direct.log",
                "config": "/tmp/onetool.yaml",
                "secrets": "/tmp/secrets.yaml",
            }),
            patch("onetool.cli_commands.direct_app._is_process_alive", return_value=True),
            patch("onetool.cli_commands.direct_app.time.time", return_value=1010.0),
            patch("onetool.cli_commands.direct_app.err_console") as mock_console,
        ):
            da.direct_status(port=8765)
            message = mock_console.print.call_args[0][0]
            assert "Config: /tmp/onetool.yaml" in message
            assert "Secrets: /tmp/secrets.yaml" in message
