"""Unit tests for runtime proxy server management behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _server_cfg(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(enabled=enabled)


def _proxy(*, connected: bool = False, error: str | None = None) -> MagicMock:
    proxy = MagicMock()
    proxy.get_connection.return_value = object() if connected else None
    proxy.list_tools.return_value = [object(), object()] if connected else []
    proxy.get_error.return_value = error
    return proxy


@pytest.mark.unit
@pytest.mark.serve
def test_status_reports_proxy_error_without_mutation() -> None:
    """Status reads expose proxy degradation without mutating server state."""
    from ottools.server import status

    cfg = SimpleNamespace(servers={"broken_proxy": _server_cfg(enabled=True)})
    proxy = _proxy(error="spawn failed")

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
    ):
        result = status(name="broken_proxy")

    assert "Server: broken_proxy" in result
    assert "Last error: spawn failed" in result
    proxy.connect_additional_sync.assert_not_called()
    proxy.disconnect_server_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_enable_disable_restart_runtime_operations() -> None:
    """Runtime server mutations update only in-memory state and proxy connections."""
    from ottools.server import disable, enable, restart

    cfg = SimpleNamespace(servers={"worker": _server_cfg(enabled=False)})
    proxy = _proxy()

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
        patch("ottools.server.get_loaded_config_path", return_value=None),
    ):
        assert "enabled" in enable(name="worker")
        assert cfg.servers["worker"].enabled is True
        proxy.connect_additional_sync.assert_called_once_with("worker", cfg.servers["worker"])

        assert "disabled" in disable(name="worker")
        assert cfg.servers["worker"].enabled is False
        proxy.disconnect_server_sync.assert_called_once_with("worker")

        assert "restarted" in restart(name="worker")
        assert cfg.servers["worker"].enabled is True
        assert proxy.disconnect_server_sync.call_count == 2
        assert proxy.connect_additional_sync.call_count == 2


@pytest.mark.unit
@pytest.mark.serve
def test_restart_applies_fresh_config_from_disk() -> None:
    """restart() re-reads the server's entry from disk and swaps it into the shared dict."""
    from pathlib import Path

    from ottools.server import restart

    stale = SimpleNamespace(enabled=True, tool_prefix="")
    fresh = SimpleNamespace(enabled=True, tool_prefix="codegraph_")
    cfg = SimpleNamespace(servers={"codegraph": stale})
    fresh_full = SimpleNamespace(servers={"codegraph": fresh})
    proxy = _proxy(connected=True)

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
        patch(
            "ottools.server.get_loaded_config_path",
            return_value=Path("/tmp/onetool.yaml"),
        ),
        patch("ottools.server.get_loaded_secrets_path", return_value=None),
        patch("ottools.server.load_config", return_value=fresh_full) as mock_load,
    ):
        result = restart(name="codegraph")

    assert "restarted" in result
    mock_load.assert_called_once()
    # Shared config dict updated in place — the execution-namespace
    # fingerprint (name, tool_prefix) must see the new prefix.
    assert cfg.servers["codegraph"] is fresh
    proxy.connect_additional_sync.assert_called_once_with("codegraph", fresh)


@pytest.mark.unit
@pytest.mark.serve
def test_restart_errors_when_server_removed_from_disk() -> None:
    """restart() refuses to reconnect a server that no longer exists on disk."""
    from pathlib import Path

    from ottools.server import restart

    cfg = SimpleNamespace(servers={"codegraph": _server_cfg(enabled=True)})
    proxy = _proxy()

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
        patch(
            "ottools.server.get_loaded_config_path",
            return_value=Path("/tmp/onetool.yaml"),
        ),
        patch("ottools.server.get_loaded_secrets_path", return_value=None),
        patch(
            "ottools.server.load_config",
            return_value=SimpleNamespace(servers={}),
        ),
    ):
        result = restart(name="codegraph")

    assert "no longer exists" in result
    proxy.disconnect_server_sync.assert_not_called()
    proxy.connect_additional_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_restart_errors_when_disk_config_invalid() -> None:
    """restart() reports a config error instead of silently reusing stale config."""
    from pathlib import Path

    from ottools.server import restart

    cfg = SimpleNamespace(servers={"codegraph": _server_cfg(enabled=True)})
    proxy = _proxy()

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
        patch(
            "ottools.server.get_loaded_config_path",
            return_value=Path("/tmp/onetool.yaml"),
        ),
        patch("ottools.server.get_loaded_secrets_path", return_value=None),
        patch(
            "ottools.server.load_config",
            side_effect=ValueError("Invalid YAML"),
        ),
    ):
        result = restart(name="codegraph")

    assert "could not re-read config" in result
    proxy.disconnect_server_sync.assert_not_called()
    proxy.connect_additional_sync.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_concurrent_runtime_mutations_are_serialized() -> None:
    """Concurrent enable/restart/disable calls for one server use the mutation guard."""
    import ottools.server as server_tools

    cfg = SimpleNamespace(servers={"worker": _server_cfg(enabled=True)})
    proxy = _proxy()
    events: list[str] = []

    def connect(_name: str, _cfg: object) -> str:
        events.append("connect")
        return "ok"

    def disconnect(_name: str) -> str:
        events.append("disconnect")
        return "disconnected"

    proxy.connect_additional_sync.side_effect = connect
    proxy.disconnect_server_sync.side_effect = disconnect

    with (
        patch("ottools.server.get_config", return_value=cfg),
        patch("ottools.server.get_proxy_manager", return_value=proxy),
        patch("ottools.server.get_loaded_config_path", return_value=None),
    ):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(
                    lambda fn: fn(name="worker"),
                    [server_tools.disable, server_tools.enable, server_tools.restart],
                )
            )

    assert len(results) == 3
    assert cfg.servers["worker"].enabled is True
    assert events
