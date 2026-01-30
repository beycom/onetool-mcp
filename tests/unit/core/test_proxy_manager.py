"""Tests for MCP ProxyManager class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ot.proxy.manager import ProxyManager, get_proxy_manager, reset_proxy_manager


@pytest.mark.unit
@pytest.mark.core
class TestProxyManager:
    """Tests for ProxyManager class."""

    def test_init_creates_empty_state(self) -> None:
        """Should initialize with empty state."""
        manager = ProxyManager()

        assert manager._clients == {}
        assert manager._tools_by_server == {}
        assert manager._initialized is False
        assert manager._loop is None

    def test_servers_returns_client_keys(self) -> None:
        """Should return list of connected server names."""
        manager = ProxyManager()
        manager._clients = {"server1": MagicMock(), "server2": MagicMock()}

        assert set(manager.servers) == {"server1", "server2"}

    def test_tool_count_sums_all_servers(self) -> None:
        """Should return total tool count across servers."""
        manager = ProxyManager()
        manager._tools_by_server = {
            "server1": [MagicMock(), MagicMock()],
            "server2": [MagicMock()],
        }

        assert manager.tool_count == 3

    def test_get_connection_returns_client(self) -> None:
        """Should return client by server name."""
        manager = ProxyManager()
        mock_client = MagicMock()
        manager._clients = {"server1": mock_client}

        assert manager.get_connection("server1") is mock_client
        assert manager.get_connection("unknown") is None


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerReconnectSync:
    """Tests for reconnect_sync method."""

    def test_reconnect_sync_without_loop_resets_state(self) -> None:
        """Should reset state when no event loop available."""
        manager = ProxyManager()
        manager._clients = {"old": MagicMock()}
        manager._tools_by_server = {"old": [MagicMock()]}
        manager._initialized = True
        manager._loop = None

        # Call with empty configs - should reset state
        manager.reconnect_sync({})

        assert manager._clients == {}
        assert manager._tools_by_server == {}
        assert manager._initialized is False

    def test_reconnect_sync_with_stored_loop_uses_it(self) -> None:
        """Should use stored loop for reconnection."""
        import asyncio

        manager = ProxyManager()
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        manager._loop = mock_loop

        # Mock run_coroutine_threadsafe to avoid actual async execution
        with patch("asyncio.run_coroutine_threadsafe") as mock_threadsafe:
            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_threadsafe.return_value = mock_future

            manager.reconnect_sync({})

            mock_threadsafe.assert_called_once()
            # Verify it was called with the stored loop
            call_args = mock_threadsafe.call_args
            assert call_args[0][1] is mock_loop


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerListTools:
    """Tests for list_tools method."""

    def test_list_tools_all_servers(self) -> None:
        """Should list tools from all servers."""
        from mcp import types

        manager = ProxyManager()

        # Create mock tools
        tool1 = MagicMock(spec=types.Tool)
        tool1.name = "search"
        tool1.description = "Search the web"
        tool1.inputSchema = {"type": "object"}

        tool2 = MagicMock(spec=types.Tool)
        tool2.name = "fetch"
        tool2.description = "Fetch a URL"
        tool2.inputSchema = {"type": "object"}

        manager._tools_by_server = {
            "brave": [tool1],
            "web": [tool2],
        }

        tools = manager.list_tools()

        assert len(tools) == 2
        assert any(t.server == "brave" and t.name == "search" for t in tools)
        assert any(t.server == "web" and t.name == "fetch" for t in tools)

    def test_list_tools_filtered_by_server(self) -> None:
        """Should filter tools by server name."""
        from mcp import types

        manager = ProxyManager()

        tool1 = MagicMock(spec=types.Tool)
        tool1.name = "search"
        tool1.description = "Search"
        tool1.inputSchema = {}

        tool2 = MagicMock(spec=types.Tool)
        tool2.name = "fetch"
        tool2.description = "Fetch"
        tool2.inputSchema = {}

        manager._tools_by_server = {
            "brave": [tool1],
            "web": [tool2],
        }

        tools = manager.list_tools(server="brave")

        assert len(tools) == 1
        assert tools[0].name == "search"
        assert tools[0].server == "brave"


@pytest.mark.unit
@pytest.mark.core
class TestGlobalProxyManager:
    """Tests for global proxy manager functions."""

    def test_get_proxy_manager_creates_singleton(self) -> None:
        """Should create singleton instance."""
        reset_proxy_manager()

        manager1 = get_proxy_manager()
        manager2 = get_proxy_manager()

        assert manager1 is manager2

    def test_reset_proxy_manager_clears_singleton(self) -> None:
        """Should clear singleton instance."""
        manager1 = get_proxy_manager()
        reset_proxy_manager()
        manager2 = get_proxy_manager()

        assert manager1 is not manager2
