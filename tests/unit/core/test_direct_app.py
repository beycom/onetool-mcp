"""Unit tests for MCP-owned direct API startup and auth configuration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_console_storage_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep general lifespan tests focused and free of real Console state I/O."""
    monkeypatch.setattr(
        "ot.console.storage.initialize_console_storage", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        "ot.console.storage.cleanup_console_instance", lambda **_kwargs: None
    )


@pytest.mark.unit
@pytest.mark.core
def test_direct_auth_key_uses_config_scoped_auth_file() -> None:
    """Direct API auth must use the dedicated config-scoped auth key file."""
    from ot.direct_auth import direct_auth_key

    with (
        patch("ot.direct_auth.ensure_hmac_key_file", return_value=b"x" * 32) as mock_key,
        patch("ot.meta.resolve_ot_path", return_value=Path("/tmp/project/.onetool")),
    ):
        assert direct_auth_key() == b"x" * 32

    mock_key.assert_called_once_with(Path("/tmp/project/.onetool/auth/mcp-direct.key"))


@pytest.mark.unit
@pytest.mark.core
def test_start_direct_api_skips_occupied_port() -> None:
    """MCP direct API startup should try the next port when preferred is occupied."""
    from ot import server

    fake_server = MagicMock()
    fake_server.started = True
    fake_thread = MagicMock()
    fake_thread.is_alive.return_value = True

    with (
        patch.object(server, "_direct_candidate_ports", return_value=[8770, 8771]),
        patch.object(server, "_tcp_port_bound", side_effect=[True, False]),
        patch.object(server, "_direct_health_probe_once", return_value=True),
        patch("uvicorn.Server", return_value=fake_server),
        patch("threading.Thread", return_value=fake_thread),
    ):
        _, _, port = server._start_direct_api()

    assert port == 8771
    fake_thread.start.assert_called_once()


@pytest.mark.unit
@pytest.mark.core
def test_direct_api_failure_is_degraded_in_lifespan() -> None:
    """MCP lifespan should continue when direct API startup fails."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={},
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=True)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )

    with (
        patch.object(server, "_config", cfg),
        patch.object(server, "get_proxy_manager", return_value=SimpleNamespace(
            bind_runtime_loop=lambda: None,
            connect_background=lambda _servers: None,
            servers={},
            is_connecting=False,
        )),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch.object(server, "_start_direct_api", side_effect=RuntimeError("boom")),
        patch("ot.telemetry.ping"),
        patch.object(server, "logger"),
    ):
        asyncio.run(_run_lifespan())


@pytest.mark.unit
@pytest.mark.core
def test_lifespan_binds_runtime_with_only_disabled_proxy_servers() -> None:
    """MCP startup should bind the proxy loop even with no enabled servers."""
    from ot import server
    from ot.config.models import McpServerConfig
    from ot.proxy.manager import ProxyManager

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            assert proxy._loop is asyncio.get_running_loop()
            cfg.servers["disabled"].enabled = True

            client = MagicMock()
            client.__aexit__ = AsyncMock(return_value=None)
            client.transport = None

            async def fake_connect(name: str, _config: McpServerConfig) -> None:
                proxy._clients[name] = client
                proxy._tools_by_server[name] = []

            with patch.object(proxy, "_connect_server", side_effect=fake_connect):
                result = await asyncio.to_thread(
                    proxy.connect_additional_sync,
                    "disabled",
                    cfg.servers["disabled"],
                )
            assert result == "ok (0 tools)"
            assert proxy.get_connection("disabled") is client

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={
            "disabled": McpServerConfig(
                type="stdio",
                command="uvx",
                args=["disabled"],
                enabled=False,
            )
        },
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=False)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )
    proxy = ProxyManager()
    connect_background = MagicMock(wraps=proxy.connect_background)

    with (
        patch.object(server, "_config", cfg),
        patch.object(server, "get_proxy_manager", return_value=proxy),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch("ot.telemetry.ping"),
        patch.object(server, "logger"),
    ):
        with patch.object(proxy, "connect_background", connect_background):
            asyncio.run(_run_lifespan())

    connect_background.assert_not_called()


def _direct_enabled_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={},
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=True, port=8765)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )


@pytest.mark.unit
@pytest.mark.core
def test_lifespan_writes_discovery_file_on_direct_api_start() -> None:
    """Direct API startup writes the discovery file with the bound port and instance id."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    fake_server = MagicMock()
    fake_thread = MagicMock()

    with (
        patch.object(server, "_config", _direct_enabled_cfg()),
        patch.object(server, "get_proxy_manager", return_value=SimpleNamespace(
            bind_runtime_loop=lambda: None,
            connect_background=lambda _servers: None,
            servers={},
            is_connecting=False,
        )),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch.object(server, "_start_direct_api", return_value=(fake_server, fake_thread, 8766)),
        patch.object(server, "_stop_direct_api"),
        patch("ot.telemetry.ping"),
        patch("ot.direct_discovery.sweep_stale_discovery_files") as sweep_mock,
        patch("ot.direct_discovery.write_discovery_file") as write_mock,
        patch("ot.runtime_meta.get_or_create_instance_id", return_value="mcp-fixedid"),
        patch("ot.runtime_meta.set_direct_api") as set_direct_api_mock,
    ):
        asyncio.run(_run_lifespan())

    sweep_mock.assert_called_once_with()
    write_mock.assert_called_once_with(instance_id="mcp-fixedid", port=8766)
    set_direct_api_mock.assert_called_once_with(base_url="http://127.0.0.1:8766", port=8766)


@pytest.mark.unit
@pytest.mark.core
def test_lifespan_removes_discovery_file_on_clean_shutdown() -> None:
    """Direct API shutdown removes the discovery file for the current instance."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    fake_server = MagicMock()
    fake_thread = MagicMock()

    with (
        patch.object(server, "_config", _direct_enabled_cfg()),
        patch.object(server, "get_proxy_manager", return_value=SimpleNamespace(
            bind_runtime_loop=lambda: None,
            connect_background=lambda _servers: None,
            servers={},
            is_connecting=False,
        )),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch.object(server, "_start_direct_api", return_value=(fake_server, fake_thread, 8766)),
        patch.object(server, "_stop_direct_api") as stop_mock,
        patch("ot.telemetry.ping"),
        patch("ot.direct_discovery.sweep_stale_discovery_files"),
        patch("ot.direct_discovery.write_discovery_file"),
        patch("ot.runtime_meta.get_or_create_instance_id", return_value="mcp-fixedid"),
        patch("ot.runtime_meta.set_direct_api"),
        patch("ot.direct_discovery.remove_discovery_file") as remove_mock,
    ):
        asyncio.run(_run_lifespan())

    stop_mock.assert_called_once_with(fake_server, fake_thread, 8766)
    remove_mock.assert_called_once_with(instance_id="mcp-fixedid")


@pytest.mark.unit
@pytest.mark.core
def test_lifespan_disabled_direct_api_never_touches_discovery_files() -> None:
    """No discovery file write/sweep/remove happens when the Direct API is disabled."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={},
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=False)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )

    with (
        patch.object(server, "_config", cfg),
        patch.object(server, "get_proxy_manager", return_value=SimpleNamespace(
            bind_runtime_loop=lambda: None,
            connect_background=lambda _servers: None,
            servers={},
            is_connecting=False,
        )),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch("ot.telemetry.ping"),
        patch("ot.direct_discovery.sweep_stale_discovery_files") as sweep_mock,
        patch("ot.direct_discovery.write_discovery_file") as write_mock,
        patch("ot.direct_discovery.remove_discovery_file") as remove_mock,
    ):
        asyncio.run(_run_lifespan())

    sweep_mock.assert_not_called()
    write_mock.assert_not_called()
    remove_mock.assert_not_called()


@pytest.mark.unit
@pytest.mark.core
def test_lifespan_initializes_and_cleans_console_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP lifespan sweeps at startup and removes its instance at shutdown."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={},
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=False)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )
    initialize = MagicMock()
    cleanup = MagicMock()
    monkeypatch.setattr("ot.console.storage.initialize_console_storage", initialize)
    monkeypatch.setattr("ot.console.storage.cleanup_console_instance", cleanup)

    with (
        patch.object(server, "_config", cfg),
        patch.object(
            server,
            "get_proxy_manager",
            return_value=SimpleNamespace(
                bind_runtime_loop=lambda: None,
                connect_background=lambda _servers: None,
                servers={},
                is_connecting=False,
            ),
        ),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch("ot.telemetry.ping"),
        patch("ot.runtime_meta.get_or_create_instance_id", return_value="mcp-fixedid"),
        patch.object(server, "logger"),
    ):
        asyncio.run(_run_lifespan())

    initialize.assert_called_once_with(instance_id="mcp-fixedid")
    cleanup.assert_called_once_with(instance_id="mcp-fixedid")


@pytest.mark.unit
@pytest.mark.core
def test_run_root_server_uses_streamable_http_transport() -> None:
    """HTTP root mode should run the shared FastMCP instance over Streamable HTTP."""
    from ot import server

    with patch.object(server.mcp, "run") as mcp_run:
        server.run_root_server(
            transport="streamable-http",
            host="127.0.0.1",
            port=8767,
            path="/mcp",
        )

    mcp_run.assert_called_once_with(
        transport="streamable-http",
        show_banner=False,
        host="127.0.0.1",
        port=8767,
        path="/mcp",
    )


@pytest.mark.unit
@pytest.mark.core
def test_http_root_option_validation_rejects_bad_path() -> None:
    """HTTP root path must be an MCP endpoint path."""
    from ot.server import validate_http_root_options

    with pytest.raises(ValueError, match="--path must start"):
        validate_http_root_options(host="127.0.0.1", port=8767, path="mcp")


@pytest.mark.unit
@pytest.mark.core
def test_http_root_lifespan_logs_transport_and_non_loopback_warning() -> None:
    """HTTP root startup logs include transport-specific URL fields and bind warning."""
    from ot import server

    async def _run_lifespan() -> None:
        async with server._lifespan(SimpleNamespace()):
            pass

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        servers={},
        include=[],
        prompts=[],
        direct=SimpleNamespace(host=SimpleNamespace(enabled=False)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
    )
    spans: list[tuple[str, dict[str, object]]] = []

    class FakeSpan:
        def __init__(self, *, span: str, **values: object) -> None:
            self.name = span
            self.values = dict(values)

        def __enter__(self) -> FakeSpan:
            spans.append((self.name, self.values))
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def add(self, *args: object, **values: object) -> None:
            if args and isinstance(args[0], dict):
                self.values.update(args[0])
            self.values.update(values)

    runtime = server.RootRuntime(
        transport="streamable-http",
        host="0.0.0.0",
        port=8767,
        path="/mcp",
    )
    proxy = SimpleNamespace(
        bind_runtime_loop=lambda: None,
        connect_background=lambda _servers: None,
        servers={},
        is_connecting=False,
    )

    with (
        patch.object(server, "_config", cfg),
        patch.object(server, "_root_runtime", runtime),
        patch.object(server, "LogSpan", FakeSpan),
        patch.object(server, "get_proxy_manager", return_value=proxy),
        patch.object(server, "get_registry", return_value=SimpleNamespace(tools={})),
        patch("ot.executor.tool_loader.load_tool_registry"),
        patch("ot.telemetry.ping"),
        patch.object(server, "logger") as logger,
    ):
        asyncio.run(_run_lifespan())

    start = next(values for name, values in spans if name == "mcp.server.start")
    stop = next(values for name, values in spans if name == "mcp.server.stop")
    assert start["transport"] == "streamable-http"
    assert start["host"] == "0.0.0.0"
    assert start["port"] == 8767
    assert start["path"] == "/mcp"
    assert start["url"] == "http://0.0.0.0:8767/mcp"
    assert stop["transport"] == "streamable-http"
    assert "duration" in stop
    logger.warning.assert_called_once()
