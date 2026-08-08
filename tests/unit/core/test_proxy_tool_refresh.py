"""Tool-list notification refresh tests for proxied MCP servers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from ot.executor.pack_proxy import build_execution_namespace, reset
from ot.executor.param_resolver import (
    evict_mcp_param_cache,
    get_mcp_tool_param_names,
)
from ot.proxy.manager import ProxyManager


def _tool(name: str, parameter: str) -> types.Tool:
    return types.Tool(
        name=name,
        description=f"{name} description",
        inputSchema={
            "type": "object",
            "properties": {parameter: {"type": "string"}},
        },
    )


def _live_manager(
    tools: list[types.Tool], *, generation: int = 1
) -> tuple[ProxyManager, MagicMock, AsyncMock]:
    manager = ProxyManager()
    client = MagicMock()
    client.list_tools = AsyncMock(return_value=tools)
    default_handler = AsyncMock()
    client._session_kwargs = {"message_handler": default_handler}
    manager._clients["srv"] = client
    manager._server_generations["srv"] = generation
    manager._tools_by_server["srv"] = []
    manager._install_message_handler("srv", client, generation)
    return manager, client, default_handler


def _tool_notification() -> types.ServerNotification:
    return types.ServerNotification(root=types.ToolListChangedNotification())


async def _send_and_wait(manager: ProxyManager, client: MagicMock) -> None:
    handler = client._session_kwargs["message_handler"]
    await handler(_tool_notification())
    task = next(iter(manager._tool_refresh_tasks.values()))
    await task


@pytest.mark.unit
@pytest.mark.core
class TestProxyToolListRefresh:
    """Live notification refreshes are complete, generation-safe, and coalesced."""

    async def test_added_removed_and_changed_tools_evict_resolution_caches(
        self,
    ) -> None:
        initial = [_tool("removed", "value"), _tool("changed", "old_parameter")]
        replacement = [_tool("added", "value"), _tool("changed", "new_parameter")]
        manager, client, default_handler = _live_manager(replacement)
        manager._tools_by_server["srv"] = initial
        registry = MagicMock(packs={}, pack_aliases={})
        config = SimpleNamespace(
            servers={"srv": SimpleNamespace(tool_prefix=None)}
        )
        reset()
        evict_mcp_param_cache(None)

        with (
            patch("ot.proxy.get_proxy_manager", return_value=manager),
            patch("ot.executor.pack_proxy.get_config", return_value=config),
        ):
            before = build_execution_namespace(registry)["srv"]
            assert callable(before.removed)
            with pytest.raises(AttributeError):
                _ = before.added
            assert get_mcp_tool_param_names("srv", "changed") == (
                "old_parameter",
            )

            await _send_and_wait(manager, client)

            after = build_execution_namespace(registry)["srv"]
            assert callable(after.added)
            with pytest.raises(AttributeError):
                _ = after.removed
            assert get_mcp_tool_param_names("srv", "changed") == (
                "new_parameter",
            )

        client.list_tools.assert_awaited_once()
        default_handler.assert_awaited_once_with(_tool_notification())

    async def test_failed_refresh_preserves_last_good_schema(self) -> None:
        previous = [_tool("stable", "value")]
        manager, client, _default = _live_manager([])
        manager._tools_by_server["srv"] = previous
        client.list_tools.side_effect = RuntimeError(
            "token=ghp_refresh-secret-sentinel"
        )

        await _send_and_wait(manager, client)

        assert manager._tools_by_server["srv"] is previous
        error = manager._tool_refresh_errors["srv"]
        assert "refresh-secret-sentinel" not in error
        assert "[redacted]" in error

    async def test_late_generation_cannot_replace_current_schema(self) -> None:
        manager, old_client, _default = _live_manager(
            [_tool("stale", "value")], generation=1
        )
        started = asyncio.Event()
        release = asyncio.Event()

        async def delayed_list() -> list[types.Tool]:
            started.set()
            await release.wait()
            return [_tool("stale", "value")]

        old_client.list_tools.side_effect = delayed_list
        handler = old_client._session_kwargs["message_handler"]
        await handler(_tool_notification())
        task = next(iter(manager._tool_refresh_tasks.values()))
        await started.wait()

        current_client = MagicMock()
        current = [_tool("current", "value")]
        manager._clients["srv"] = current_client
        manager._server_generations["srv"] = 2
        manager._tools_by_server["srv"] = current
        release.set()
        await task

        assert manager._tools_by_server["srv"] is current

    async def test_overlapping_notifications_are_coalesced(self) -> None:
        manager, client, default_handler = _live_manager([])
        started = asyncio.Event()
        release = asyncio.Event()

        async def delayed_list() -> list[types.Tool]:
            started.set()
            await release.wait()
            return [_tool("fresh", "value")]

        client.list_tools.side_effect = delayed_list
        handler = client._session_kwargs["message_handler"]
        for _ in range(3):
            await handler(_tool_notification())

        task = next(iter(manager._tool_refresh_tasks.values()))
        await started.wait()
        client.list_tools.assert_awaited_once()
        release.set()
        await task

        assert [tool.name for tool in manager._tools_by_server["srv"]] == [
            "fresh"
        ]
        assert default_handler.await_count == 3

    async def test_default_handler_still_receives_task_notifications(self) -> None:
        manager, client, default_handler = _live_manager([])
        now = datetime.now(UTC)
        notification = types.ServerNotification(
            root=types.TaskStatusNotification(
                params=types.TaskStatusNotificationParams(
                    taskId="task-1",
                    status="working",
                    createdAt=now,
                    lastUpdatedAt=now,
                    ttl=None,
                )
            )
        )

        await client._session_kwargs["message_handler"](notification)

        default_handler.assert_awaited_once_with(notification)
        assert manager._tool_refresh_tasks == {}
