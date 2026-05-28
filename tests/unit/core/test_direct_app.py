"""Unit tests for MCP-owned direct API startup and auth configuration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_direct_auth_key_uses_mcp_direct_namespace() -> None:
    """Direct API auth must use the dedicated config-scoped mcp-direct namespace."""
    from ot.direct_auth import direct_auth_key

    with (
        patch("ot.direct_auth.ensure_hmac_key", return_value=b"x" * 32) as mock_key,
        patch("ot.meta.resolve_ot_path", return_value=Path("/tmp/project/.onetool")),
    ):
        assert direct_auth_key() == b"x" * 32

    mock_key.assert_called_once_with("mcp-direct", base_dir=Path("/tmp/project/.onetool"))


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
