"""Integration tests for p12 core-flow-hardening concurrency/cache behavior.

Covers the always-offload non-blocking guarantee (D3/R8 P1), the same-loop
sync-bridge guard (D3), and restart cache eviction resolving the new schema (D14).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from ot.executor.runner import execute_command
from ot.proxy.manager import ProxyManager


def _tool_mock(name: str, schema: dict) -> MagicMock:
    tool = MagicMock(spec=types.Tool)
    tool.name = name
    tool.description = "desc"
    tool.inputSchema = schema
    return tool


@pytest.mark.integration
@pytest.mark.core
class TestNonBlockingExecution:
    """D3/R8 P1: a blocking tool call never freezes the event loop."""

    async def test_blocking_call_does_not_freeze_loop(self, monkeypatch) -> None:
        import time

        import ot.executor.runner as runner

        def _slow(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            time.sleep(0.8)
            return ("ok", None, True, "json", False, None)

        # No proxy servers connected: the old code ran this synchronously on the loop.
        monkeypatch.setattr(runner, "execute_python_code", _slow)

        loop = asyncio.get_running_loop()
        slow_task = asyncio.create_task(execute_command("1 + 1"))

        # The ticker (~0.3s of loop work) must finish while the 0.8s blocking call is
        # still running on the worker thread — i.e. there is a clear gap before the
        # call completes. If the loop were frozen (old sync path), the ticker could
        # not progress until the call finished and the gap would collapse to ~0.
        for _ in range(10):
            await asyncio.sleep(0.03)
        ticker_done = loop.time()

        result = await slow_task
        slow_done = loop.time()
        assert result.success
        assert slow_done - ticker_done > 0.2


@pytest.mark.integration
@pytest.mark.core
class TestSyncBridgeSameLoopGuard:
    """D3: server-control sync bridges called from their own loop return promptly."""

    async def test_connect_additional_sync_schedules_without_blocking(self) -> None:
        manager = ProxyManager()
        manager._loop = asyncio.get_running_loop()
        started = asyncio.Event()

        async def _fake_connect(name: str, config: object) -> str:
            started.set()
            return "ok"

        manager.connect_additional = _fake_connect  # type: ignore[method-assign]
        cfg = MagicMock()
        cfg.enabled = True

        # Called synchronously from the loop thread — must schedule, not block 120s.
        result = manager.connect_additional_sync("srv", cfg)
        assert result == "scheduled"
        await asyncio.wait_for(started.wait(), timeout=2.0)

    async def test_disconnect_server_sync_schedules_without_blocking(self) -> None:
        manager = ProxyManager()
        manager._loop = asyncio.get_running_loop()
        manager._clients["srv"] = MagicMock()
        started = asyncio.Event()

        async def _fake_disconnect(name: str) -> str:
            started.set()
            return "disconnected"

        manager.disconnect_server = _fake_disconnect  # type: ignore[method-assign]

        result = manager.disconnect_server_sync("srv")
        assert result == "scheduled"
        await asyncio.wait_for(started.wait(), timeout=2.0)


@pytest.mark.integration
@pytest.mark.core
class TestRestartCacheEviction:
    """D14: a restart (disconnect + reconnect) resolves against the new schema."""

    async def test_restart_resolves_new_schema(self) -> None:
        from ot.executor import param_resolver

        manager = ProxyManager()
        manager._loop = asyncio.get_running_loop()

        # Stale param-cache entry from the pre-restart connection.
        param_resolver._mcp_param_cache[("srv", "tool")] = ("old_param",)

        # Restart: disconnect the old client, then reconnect with a NEW schema.
        client = MagicMock()
        client.__aexit__ = AsyncMock()
        client.transport = None
        manager._clients["srv"] = client
        manager._tools_by_server["srv"] = []

        await manager.disconnect_server("srv")
        assert ("srv", "tool") not in param_resolver._mcp_param_cache

        # Reconnect: _connect_server is stubbed; the manager now exposes the new tool.
        manager._connect_server = AsyncMock()  # type: ignore[method-assign]
        manager._tools_by_server["srv"] = [
            _tool_mock("tool", {"properties": {"new_param": {}}})
        ]
        cfg = MagicMock()
        cfg.enabled = True
        await manager.connect_additional("srv", cfg)

        # Resolution now reads the new schema, not the evicted stale entry.
        with patch("ot.proxy.get_proxy_manager", return_value=manager):
            names = param_resolver.get_mcp_tool_param_names("srv", "tool")
        assert names == ("new_param",)
