"""Tests for MCP ProxyManager class."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

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
        assert manager._server_timeouts == {}
        assert manager._initialized is False
        assert manager._loop is None
        assert manager._connect_task is None

    def test_get_server_timeout_returns_configured_value(self) -> None:
        """Should return the timeout stored for a connected server."""
        manager = ProxyManager()
        manager._server_timeouts = {"chunkhound": 300.0, "github": 120.0}

        assert manager.get_server_timeout("chunkhound") == 300.0
        assert manager.get_server_timeout("github") == 120.0

    def test_get_server_timeout_defaults_to_30(self) -> None:
        """Should return 30.0 for unknown servers."""
        manager = ProxyManager()

        assert manager.get_server_timeout("unknown") == 30.0

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
        manager = ProxyManager()
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_loop.is_running.return_value = True
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

            # Close the coroutine to avoid "never awaited" warning
            # (the mock doesn't actually schedule it)
            call_args[0][0].close()

    @pytest.mark.asyncio
    async def test_reconnect_sync_from_same_loop_schedules_without_blocking(self) -> None:
        """Should not block waiting on the same event loop during reconnect."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        manager._loop = asyncio.get_running_loop()
        manager._clients = {"old": MagicMock()}
        manager._tools_by_server = {"old": [MagicMock()]}

        async def fake_connect(_configs: dict[str, McpServerConfig]) -> None:
            await asyncio.sleep(0)

        configs = {
            "next": McpServerConfig(type="stdio", command="uvx", args=["next"]),
        }
        with (
            patch("asyncio.run_coroutine_threadsafe") as mock_threadsafe,
            patch.object(manager, "connect", side_effect=fake_connect) as mock_connect,
        ):
            manager.reconnect_sync(configs)
            await asyncio.wait_for(manager._connect_task, timeout=1)

        mock_threadsafe.assert_not_called()
        mock_connect.assert_called_once_with(configs)
        assert manager._clients == {}
        assert manager._tools_by_server == {}


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
            "webfetch": [tool2],
        }

        tools = manager.list_tools()

        assert len(tools) == 2
        assert any(t.server == "brave" and t.name == "search" for t in tools)
        assert any(t.server == "webfetch" and t.name == "fetch" for t in tools)

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
            "webfetch": [tool2],
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


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerAuth:
    """Tests for HTTP client authentication."""

    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_client_no_auth(
        self, mock_client: MagicMock, mock_transport: MagicMock
    ) -> None:
        """Should create HTTP client without auth when not configured."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://test.invalid/mcp",
        )

        manager._create_http_client("test", config)

        # Verify transport created with no auth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] is None

    @patch("ot.proxy.manager.OAuth")
    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_client_oauth(
        self,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        mock_oauth: MagicMock,
    ) -> None:
        """Should create HTTP client with OAuth when configured."""
        from ot.config.models import AuthConfig, McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://test.invalid/mcp",
            auth=AuthConfig(type="oauth", scopes=["tools:read", "tools:write"]),
        )

        manager._create_http_client("test", config)

        # Verify OAuth created with correct params
        mock_oauth.assert_called_once_with(
            mcp_url="https://test.invalid/mcp",
            scopes=["tools:read", "tools:write"],
            client_name="OneTool",
        )

        # Verify transport created with OAuth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] == mock_oauth.return_value

    @patch("ot.proxy.manager.BearerAuth")
    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    @patch("ot.proxy.manager.expand_vars")
    def test_http_client_bearer(
        self,
        mock_expand: MagicMock,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        mock_bearer: MagicMock,
    ) -> None:
        """Should create HTTP client with Bearer auth when configured."""
        from ot.config.models import AuthConfig, McpServerConfig

        mock_expand.return_value = "expanded-token-123"

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://test.invalid/mcp",
            auth=AuthConfig(type="bearer", token="${GITHUB_TOKEN}"),
        )

        manager._create_http_client("test", config)

        # Verify token expansion
        mock_expand.assert_called_once_with("${GITHUB_TOKEN}")

        # Verify BearerAuth created with expanded token
        mock_bearer.assert_called_once_with("expanded-token-123")

        # Verify transport created with BearerAuth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] == mock_bearer.return_value

    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_url_preserved(
        self, mock_client: MagicMock, mock_transport: MagicMock
    ) -> None:
        """Should preserve explicitly configured HTTP URLs."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="http://test.invalid/mcp",
        )

        manager._create_http_client("test", config)

        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["url"] == "http://test.invalid/mcp"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerStdio:
    """Tests for stdio client environment variable handling."""

    @patch("ot.proxy.manager.StdioTransport")
    @patch("ot.proxy.manager.Client")
    def test_stdio_client_passes_configured_env(
        self, mock_client: MagicMock, mock_transport: MagicMock
    ) -> None:
        """Should pass configured env vars to StdioTransport."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="stdio",
            command="npx",
            args=["-y", "some-mcp-server"],
            env={
                "GITHUB_TOKEN": "test_token_123",
                "GITHUB_APP_ID": "test_app_456",
            },
        )

        manager._create_stdio_client("github", config)

        mock_transport.assert_called_once()
        env = mock_transport.call_args[1]["env"]
        assert env["GITHUB_TOKEN"] == "test_token_123"
        assert env["GITHUB_APP_ID"] == "test_app_456"

    @patch("ot.proxy.manager.StdioTransport")
    @patch("ot.proxy.manager.Client")
    def test_stdio_client_clean_env_by_default(
        self,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should NOT inherit parent env by default (clean env)."""
        from ot.config.models import McpServerConfig

        monkeypatch.setenv("MY_PARENT_VAR", "parent_value")

        manager = ProxyManager()
        config = McpServerConfig(
            type="stdio",
            command="node",
            args=["server.js"],
        )

        manager._create_stdio_client("test", config)

        mock_transport.assert_called_once()
        env = mock_transport.call_args[1]["env"]
        assert "MY_PARENT_VAR" not in env
        assert "PATH" in env

    @patch("ot.proxy.manager.StdioTransport")
    @patch("ot.proxy.manager.Client")
    def test_stdio_client_inherits_parent_env_when_enabled(
        self,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should inherit parent env when inherit_env is true."""
        from ot.config.models import McpServerConfig

        monkeypatch.setenv("MY_PARENT_VAR", "parent_value")

        manager = ProxyManager()
        config = McpServerConfig(
            type="stdio",
            command="node",
            args=["server.js"],
            inherit_env=True,
        )

        manager._create_stdio_client("test", config)

        mock_transport.assert_called_once()
        env = mock_transport.call_args[1]["env"]
        assert env["MY_PARENT_VAR"] == "parent_value"
        assert "PATH" in env

    @patch("ot.proxy.manager.StdioTransport")
    @patch("ot.proxy.manager.Client")
    def test_stdio_client_config_env_overrides_parent(
        self,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should let config env override parent env vars when inheriting."""
        from ot.config.models import McpServerConfig

        monkeypatch.setenv("LOG_LEVEL", "info")

        manager = ProxyManager()
        config = McpServerConfig(
            type="stdio",
            inherit_env=True,
            command="node",
            args=["server.js"],
            env={"LOG_LEVEL": "debug"},
        )

        manager._create_stdio_client("test", config)

        mock_transport.assert_called_once()
        env = mock_transport.call_args[1]["env"]
        assert env["LOG_LEVEL"] == "debug"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerResources:
    """Tests for resource methods."""

    @pytest.mark.asyncio
    async def test_list_resources_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.list_resources("unknown")

    @pytest.mark.asyncio
    async def test_list_resources_success(self) -> None:
        """Should list resources from connected server."""
        manager = ProxyManager()

        # Mock client with list_resources method
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.uri = "file:///test.txt"
        mock_resource.name = "Test File"
        mock_resource.description = "A test file"
        mock_client.list_resources = AsyncMock(return_value=[mock_resource])

        manager._clients = {"test_server": mock_client}

        resources = await manager.list_resources("test_server")

        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///test.txt"
        assert resources[0]["name"] == "Test File"
        assert resources[0]["description"] == "A test file"

    @pytest.mark.asyncio
    async def test_read_resource_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.read_resource("unknown", "file:///test.txt")

    @pytest.mark.asyncio
    async def test_read_resource_success(self) -> None:
        """Should read resource content from connected server."""
        manager = ProxyManager()

        # Mock client with read_resource method
        mock_client = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Resource content"

        # Mock ReadResourceResult with contents attribute
        mock_result = MagicMock()
        mock_result.contents = [mock_content]
        mock_client.read_resource = AsyncMock(return_value=mock_result)

        manager._clients = {"test_server": mock_client}

        content = await manager.read_resource("test_server", "file:///test.txt")

        assert content == "Resource content"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerPrompts:
    """Tests for prompt methods."""

    @pytest.mark.asyncio
    async def test_list_prompts_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.list_prompts("unknown")

    @pytest.mark.asyncio
    async def test_list_prompts_success(self) -> None:
        """Should list prompts from connected server."""
        manager = ProxyManager()

        # Mock client with list_prompts method
        mock_client = MagicMock()
        mock_prompt = MagicMock()
        mock_prompt.name = "summarize"
        mock_prompt.description = "Summarize text"
        mock_client.list_prompts = AsyncMock(return_value=[mock_prompt])

        manager._clients = {"test_server": mock_client}

        prompts = await manager.list_prompts("test_server")

        assert len(prompts) == 1
        assert prompts[0]["name"] == "summarize"
        assert prompts[0]["description"] == "Summarize text"

    @pytest.mark.asyncio
    async def test_get_prompt_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.get_prompt("unknown", "summarize")

    @pytest.mark.asyncio
    async def test_get_prompt_success(self) -> None:
        """Should get rendered prompt from connected server."""
        manager = ProxyManager()

        # Mock client with get_prompt method
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Summarize this text"
        mock_result = MagicMock()
        mock_result.messages = [mock_message]
        mock_client.get_prompt = AsyncMock(return_value=mock_result)

        manager._clients = {"test_server": mock_client}

        content = await manager.get_prompt("test_server", "summarize", {"text": "test"})

        assert content == "Summarize this text"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerCancelledError:
    """Tests for CancelledError handling in connect() and _connect_server()."""

    @pytest.mark.asyncio
    async def test_connect_sets_initialized_on_cancellation(self) -> None:
        """_initialized must be True even when CancelledError aborts the loop."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="node", args=["s.js"])

        async def raise_cancelled(name: str, cfg: McpServerConfig) -> None:
            raise asyncio.CancelledError

        with patch.object(manager, "_connect_server", side_effect=raise_cancelled):
            with contextlib.suppress(asyncio.CancelledError):
                await manager.connect({"srv": config})

        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_connect_records_error_on_cancellation(self) -> None:
        """connect() should record a 'cancelled' error entry before re-raising."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="node", args=["s.js"])

        async def raise_cancelled(name: str, cfg: McpServerConfig) -> None:
            raise asyncio.CancelledError

        with patch.object(manager, "_connect_server", side_effect=raise_cancelled):
            with contextlib.suppress(asyncio.CancelledError):
                await manager.connect({"srv": config})

        assert manager._errors.get("srv") == "cancelled"

    @pytest.mark.asyncio
    async def test_connect_reraises_cancellederror(self) -> None:
        """connect() must re-raise CancelledError so the task stays cancelled."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="node", args=["s.js"])

        async def raise_cancelled(name: str, cfg: McpServerConfig) -> None:
            raise asyncio.CancelledError

        with patch.object(manager, "_connect_server", side_effect=raise_cancelled):
            with pytest.raises(asyncio.CancelledError):
                await manager.connect({"srv": config})

    @pytest.mark.asyncio
    async def test_connect_server_calls_aexit_on_cancellation(self) -> None:
        """_connect_server() must call client.__aexit__ even on CancelledError."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="node", args=["s.js"])

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.list_tools = AsyncMock(side_effect=asyncio.CancelledError)

        with patch.object(manager, "_create_client", return_value=mock_client):
            with pytest.raises(asyncio.CancelledError):
                await manager._connect_server("srv", config)

        mock_client.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerBackgroundConnect:
    """Tests for background proxy connection (connect_background / is_connecting)."""

    def test_is_connecting_false_when_no_task(self) -> None:
        """Should return False when no background task exists."""
        manager = ProxyManager()
        assert manager.is_connecting is False

    @pytest.mark.asyncio
    async def test_is_connecting_true_while_task_pending(self) -> None:
        """Should return True while a background task is still running."""
        manager = ProxyManager()

        # Create a long-running task to simulate an in-progress connection
        task = asyncio.create_task(asyncio.sleep(100))
        manager._connect_task = task

        assert manager.is_connecting is True

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_is_connecting_false_after_task_completes(self) -> None:
        """Should return False after the background task finishes."""
        manager = ProxyManager()

        task = asyncio.create_task(asyncio.sleep(0))
        manager._connect_task = task
        await task

        assert manager.is_connecting is False

    @pytest.mark.asyncio
    async def test_connect_background_creates_task(self) -> None:
        """Should schedule connect() as a background task and return it."""
        manager = ProxyManager()

        with patch.object(manager, "connect", new_callable=AsyncMock) as mock_connect:
            task = manager.connect_background({})

            assert task is manager._connect_task
            assert manager.is_connecting is True

            await task

            mock_connect.assert_awaited_once_with({})

    @pytest.mark.asyncio
    async def test_connect_background_sets_loop(self) -> None:
        """Should capture the running event loop."""
        manager = ProxyManager()

        with patch.object(manager, "connect", new_callable=AsyncMock):
            task = manager.connect_background({})
            await task

        assert manager._loop is asyncio.get_event_loop()

    @pytest.mark.asyncio
    async def test_call_tool_still_connecting_error(self) -> None:
        """Should raise informative error when server not yet connected but task is running."""
        manager = ProxyManager()

        task = asyncio.create_task(asyncio.sleep(100))
        manager._connect_task = task

        with pytest.raises(ValueError, match="still connecting"):
            await manager.call_tool("devtools", "some_tool")

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_call_tool_not_connected_error_when_idle(self) -> None:
        """Should raise 'not connected' error when no task is running."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.call_tool("devtools", "some_tool")

    @pytest.mark.asyncio
    async def test_shutdown_cancels_background_task(self) -> None:
        """Should cancel the background connect task on shutdown."""
        manager = ProxyManager()

        task = asyncio.create_task(asyncio.sleep(100))
        manager._connect_task = task

        await manager.shutdown()

        assert task.cancelled()
        assert manager._connect_task is None

    def test_reset_state_clears_connect_task(self) -> None:
        """Should clear _connect_task on reset."""
        manager = ProxyManager()
        manager._connect_task = MagicMock()  # type: ignore[assignment]

        manager._reset_state()

        assert manager._connect_task is None

    @pytest.mark.asyncio
    async def test_connect_runs_servers_concurrently_and_records_failures(self) -> None:
        """Should connect independent proxy servers without waiting sequentially."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        started: set[str] = set()
        release = asyncio.Event()

        async def fake_connect(name: str, _config: McpServerConfig) -> None:
            started.add(name)
            if len(started) == 3:
                release.set()
            await asyncio.wait_for(release.wait(), timeout=1)
            if name == "bad":
                raise RuntimeError("boom")
            manager._clients[name] = MagicMock()
            manager._tools_by_server[name] = []

        configs = {
            "one": McpServerConfig(type="stdio", command="uvx", args=["one"]),
            "two": McpServerConfig(type="stdio", command="uvx", args=["two"]),
            "bad": McpServerConfig(type="stdio", command="uvx", args=["bad"]),
        }

        with patch.object(manager, "_connect_server", side_effect=fake_connect):
            await manager.connect(configs)

        assert started == {"one", "two", "bad"}
        assert set(manager._clients) == {"one", "two"}
        assert manager._errors["bad"] == "boom"
        assert manager._initialized is True

    def test_readiness_reports_connecting_connected_and_failed_servers(self) -> None:
        """Should expose proxy readiness separate from HTTP health."""
        manager = ProxyManager()
        manager._clients = {"ok": MagicMock()}
        manager._tools_by_server = {"ok": [MagicMock(), MagicMock()]}
        manager._errors = {"bad": "boom"}
        manager._connect_task = MagicMock()
        manager._connect_task.done.return_value = False

        result = manager.readiness(("ok", "bad", "pending"))

        assert result["ready"] is False
        assert result["status"] == "degraded"
        assert result["connected"] == 1
        assert result["failed"] == 1
        assert result["servers"]["ok"] == {"status": "connected", "tool_count": 2}
        assert result["servers"]["bad"] == {"status": "failed", "error": "boom"}
        assert result["servers"]["pending"] == {"status": "connecting"}


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerIncrementalConnect:
    """Tests for connect_additional and disconnect_server methods."""

    @pytest.mark.asyncio
    async def test_connect_additional_already_connected(self) -> None:
        """Should return 'already connected' without reconnecting."""
        manager = ProxyManager()
        manager._clients = {"my-server": MagicMock()}

        from ot.config.models import McpServerConfig

        config = McpServerConfig(type="stdio", command="uvx", args=["my-server"])
        result = await manager.connect_additional("my-server", config)

        assert result == "already connected"

    @pytest.mark.asyncio
    async def test_connect_additional_disabled(self) -> None:
        """Should return 'disabled' without connecting when config.enabled is false."""
        manager = ProxyManager()

        from ot.config.models import McpServerConfig

        config = McpServerConfig(type="stdio", command="uvx", args=["my-server"], enabled=False)
        result = await manager.connect_additional("my-server", config)

        assert result == "disabled"

    @pytest.mark.asyncio
    async def test_connect_additional_success(self) -> None:
        """Should connect new server and return 'ok (N tools)'."""
        from mcp import types
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="uvx", args=["my-server"])

        mock_tool = MagicMock(spec=types.Tool)
        mock_tool.name = "do_thing"
        mock_tool.description = "Does a thing"
        mock_tool.inputSchema = {}

        async def fake_connect(name: str, cfg: McpServerConfig) -> None:
            manager._clients[name] = MagicMock()
            manager._tools_by_server[name] = [mock_tool, mock_tool]

        with patch.object(manager, "_connect_server", side_effect=fake_connect):
            result = await manager.connect_additional("my-server", config)

        assert result == "ok (2 tools)"
        assert "my-server" in manager._clients

    @pytest.mark.asyncio
    async def test_connect_additional_failure(self) -> None:
        """Should return 'failed: <reason>' and record error on connection failure."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(type="stdio", command="uvx", args=["my-server"])

        with patch.object(manager, "_connect_server", side_effect=RuntimeError("process failed")):
            result = await manager.connect_additional("my-server", config)

        assert result.startswith("failed:")
        assert "process failed" in result
        assert manager._errors.get("my-server") is not None

    @pytest.mark.asyncio
    async def test_connect_additional_does_not_affect_other_servers(self) -> None:
        """Should not disconnect existing servers when connecting a new one."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        existing_client = MagicMock()
        manager._clients = {"existing": existing_client}

        config = McpServerConfig(type="stdio", command="uvx", args=["new-server"])

        async def fake_connect(name: str, cfg: McpServerConfig) -> None:
            manager._clients[name] = MagicMock()
            manager._tools_by_server[name] = []

        with patch.object(manager, "_connect_server", side_effect=fake_connect):
            await manager.connect_additional("new-server", config)

        assert manager._clients["existing"] is existing_client

    @pytest.mark.asyncio
    async def test_disconnect_server_not_connected(self) -> None:
        """Should return 'not connected' when server is not in clients."""
        manager = ProxyManager()
        result = await manager.disconnect_server("nonexistent")
        assert result == "not connected"

    @pytest.mark.asyncio
    async def test_disconnect_server_success(self) -> None:
        """Should disconnect server and unregister its tools."""
        from mcp import types

        manager = ProxyManager()
        mock_client = AsyncMock()
        mock_client.transport = AsyncMock()
        mock_tool = MagicMock(spec=types.Tool)
        manager._clients = {"aws-iam": mock_client}
        manager._tools_by_server = {"aws-iam": [mock_tool]}
        manager._server_timeouts = {"aws-iam": 120.0}

        result = await manager.disconnect_server("aws-iam")

        assert result == "disconnected"
        assert "aws-iam" not in manager._clients
        assert "aws-iam" not in manager._tools_by_server
        assert "aws-iam" not in manager._server_timeouts
        mock_client.__aexit__.assert_awaited_once_with(None, None, None)
        mock_client.transport.close.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_disconnect_server_does_not_affect_other_servers(self) -> None:
        """Should not affect other connected servers."""
        manager = ProxyManager()
        other_client = MagicMock()
        target_client = AsyncMock()

        manager._clients = {"keep": other_client, "remove": target_client}
        manager._tools_by_server = {"keep": [], "remove": []}

        await manager.disconnect_server("remove")

        assert "keep" in manager._clients
        assert manager._clients["keep"] is other_client

    def test_connect_additional_sync_no_loop(self) -> None:
        """Should return failure string when no running event loop."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        manager._loop = None
        config = McpServerConfig(type="stdio", command="uvx", args=["my-server"])

        result = manager.connect_additional_sync("my-server", config)
        assert "failed" in result

    def test_disconnect_server_sync_no_loop(self) -> None:
        """Should remove from clients dict directly when no running loop."""
        manager = ProxyManager()
        manager._loop = None
        manager._clients = {"aws-iam": MagicMock()}
        manager._tools_by_server = {"aws-iam": []}

        result = manager.disconnect_server_sync("aws-iam")
        assert result == "disconnected"
        assert "aws-iam" not in manager._clients

    def test_disconnect_server_sync_no_loop_not_connected(self) -> None:
        """Should return 'not connected' when no loop and server not in clients."""
        manager = ProxyManager()
        manager._loop = None

        result = manager.disconnect_server_sync("nonexistent")
        assert result == "not connected"


@pytest.mark.unit
@pytest.mark.core
class TestStripCtxFromSchema:
    """Tests for _strip_ctx_from_schema helper."""

    def _make_tool(self, schema: dict) -> "types.Tool":
        from mcp import types

        return types.Tool(name="test_tool", description="test", inputSchema=schema)

    def test_strips_ctx_from_required(self) -> None:
        """Should remove 'ctx' from the required list."""
        from mcp import types

        from ot.proxy.manager import _strip_ctx_from_schema

        tool = self._make_tool({
            "type": "object",
            "required": ["ctx", "user_name"],
            "properties": {
                "ctx": {"type": "object"},
                "user_name": {"type": "string"},
            },
        })

        result = _strip_ctx_from_schema(tool)

        assert "ctx" not in result.inputSchema.get("required", [])
        assert "user_name" in result.inputSchema["required"]

    def test_strips_ctx_from_properties(self) -> None:
        """Should remove 'ctx' from properties dict."""
        from ot.proxy.manager import _strip_ctx_from_schema

        tool = self._make_tool({
            "type": "object",
            "required": ["ctx"],
            "properties": {
                "ctx": {"type": "object"},
            },
        })

        result = _strip_ctx_from_schema(tool)

        assert "ctx" not in result.inputSchema.get("properties", {})

    def test_no_ctx_returns_same_tool(self) -> None:
        """Should return the same tool object if no ctx field present."""
        from ot.proxy.manager import _strip_ctx_from_schema

        tool = self._make_tool({
            "type": "object",
            "required": ["user_name"],
            "properties": {"user_name": {"type": "string"}},
        })

        result = _strip_ctx_from_schema(tool)

        assert result is tool  # identical object, no copy made

    def test_preserves_other_required_fields(self) -> None:
        """Should preserve all required fields other than ctx."""
        from ot.proxy.manager import _strip_ctx_from_schema

        tool = self._make_tool({
            "type": "object",
            "required": ["ctx", "a", "b"],
            "properties": {
                "ctx": {},
                "a": {"type": "string"},
                "b": {"type": "integer"},
            },
        })

        result = _strip_ctx_from_schema(tool)

        assert result.inputSchema["required"] == ["a", "b"]
        assert "a" in result.inputSchema["properties"]
        assert "b" in result.inputSchema["properties"]

    def test_ctx_only_in_required_not_properties(self) -> None:
        """Should handle ctx only in required (not in properties) gracefully."""
        from ot.proxy.manager import _strip_ctx_from_schema

        tool = self._make_tool({
            "type": "object",
            "required": ["ctx", "name"],
            "properties": {"name": {"type": "string"}},
        })

        result = _strip_ctx_from_schema(tool)

        assert "ctx" not in result.inputSchema["required"]
        assert "name" in result.inputSchema["required"]
