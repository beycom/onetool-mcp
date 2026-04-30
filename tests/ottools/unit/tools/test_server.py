"""Unit tests for server runtime management helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_server_cfg(enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.enabled = enabled
    return cfg


def _make_mock_env(servers: dict, connected: list[str] | None = None, tool_counts: dict | None = None):
    """Create a mock environment with config and proxy manager."""
    connected = connected or []
    tool_counts = tool_counts or {}

    mock_cfg = MagicMock()
    mock_cfg.servers = servers

    mock_proxy = MagicMock()

    def get_connection(name: str):
        return MagicMock() if name in connected else None

    def list_tools(server: str | None = None):
        if server:
            return [MagicMock()] * tool_counts.get(server, 0)
        return []

    mock_proxy.get_connection = get_connection
    mock_proxy.list_tools = list_tools
    mock_proxy.get_error = MagicMock(return_value=None)
    mock_proxy.connect_additional_sync = MagicMock()
    mock_proxy.disconnect_server_sync = MagicMock()

    return mock_cfg, mock_proxy


def _patch_env(mock_cfg, mock_proxy):
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch("ottools.server.get_config", return_value=mock_cfg))
    stack.enter_context(patch("ottools.server.get_proxy_manager", return_value=mock_proxy))
    return stack


@pytest.mark.unit
@pytest.mark.tools
def test_server_list_all() -> None:
    """server() lists all configured servers."""
    from ottools.server import server

    servers = {
        "devtools": _make_server_cfg(enabled=True),
        "playwright": _make_server_cfg(enabled=False),
    }
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server()

    assert "devtools" in result
    assert "playwright" in result
    assert "enabled" in result
    assert "disabled" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_status_connected() -> None:
    """server(status=...) shows connection status and tool count."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(status="devtools")

    assert "devtools" in result
    assert "connected" in result
    assert "26" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_status_unknown() -> None:
    """server(status='unknown') returns error with configured server names."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg()}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = server(status="nonexistent-server")

    assert "Error" in result or "Unknown" in result
    assert "devtools" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_no_servers_configured() -> None:
    """server() returns a clear message when no servers are configured."""
    from ottools.server import server

    mock_cfg, mock_proxy = _make_mock_env({})

    with _patch_env(mock_cfg, mock_proxy):
        result = server()

    assert "No servers configured" in result


@pytest.mark.unit
@pytest.mark.tools
def test_enable_disabled_server() -> None:
    """enable(name=...) enables a disabled server."""
    from ottools.server import enable

    srv_cfg = _make_server_cfg(enabled=False)
    servers = {"devtools-auto": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools-auto"], tool_counts={"devtools-auto": 10})

    with _patch_env(mock_cfg, mock_proxy):
        result = enable(name="devtools-auto")

    assert mock_proxy.connect_additional_sync.called
    assert srv_cfg.enabled is True
    assert "enabled" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_enable_already_enabled_connected_is_noop() -> None:
    """enable(name=...) does not reconnect an already connected server."""
    from ottools.server import enable

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"devtools": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = enable(name="devtools")

    mock_proxy.connect_additional_sync.assert_not_called()
    assert "already enabled and connected" in result


@pytest.mark.unit
@pytest.mark.tools
def test_enable_unknown_server() -> None:
    """enable(name=...) returns clear error for unknown server."""
    from ottools.server import enable

    servers = {"devtools": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = enable(name="missing")

    assert "Unknown server" in result
    assert "devtools" in result


@pytest.mark.unit
@pytest.mark.tools
def test_disable_enabled_server() -> None:
    """disable(name=...) disables an enabled server."""
    from ottools.server import disable

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"devtools": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"])

    with _patch_env(mock_cfg, mock_proxy):
        result = disable(name="devtools")

    assert mock_proxy.disconnect_server_sync.called
    assert srv_cfg.enabled is False
    assert "disabled" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_disable_already_disabled_is_noop() -> None:
    """disable(name=...) on a disabled server is a no-op."""
    from ottools.server import disable

    srv_cfg = _make_server_cfg(enabled=False)
    servers = {"devtools": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = disable(name="devtools")

    mock_proxy.disconnect_server_sync.assert_not_called()
    assert "already disabled" in result


@pytest.mark.unit
@pytest.mark.tools
def test_disable_unknown_server() -> None:
    """disable(name=...) returns clear error for unknown server."""
    from ottools.server import disable

    servers = {"devtools": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = disable(name="missing")

    assert "Unknown server" in result
    assert "devtools" in result


@pytest.mark.unit
@pytest.mark.tools
def test_restart_server() -> None:
    """restart(name=...) reconnects a server."""
    from ottools.server import restart

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"playwright": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["playwright"], tool_counts={"playwright": 15})

    with _patch_env(mock_cfg, mock_proxy):
        result = restart(name="playwright")

    assert mock_proxy.disconnect_server_sync.called
    assert mock_proxy.connect_additional_sync.called
    assert "restarted" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_restart_unknown_server() -> None:
    """restart(name=...) returns clear error for unknown server."""
    from ottools.server import restart

    servers = {"playwright": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = restart(name="missing")

    assert "Unknown server" in result
    assert "playwright" in result
