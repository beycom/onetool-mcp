"""ProxyManager for connecting to external MCP servers using FastMCP Client.

Manages connections to external MCP servers and routes tool calls
through OneTool's single `run` tool interface.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastmcp import Client
from fastmcp.client.auth import BearerAuth, OAuth
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from loguru import logger
from mcp import types

from ot.config import expand_vars
from ot.logging import LogEntry, LogSpan

if TYPE_CHECKING:
    from concurrent.futures import Future

    from ot.config.models import McpServerConfig


def _strip_ctx_from_schema(tool: types.Tool) -> types.Tool:
    """Remove 'ctx' from a tool's inputSchema.

    Some MCP server implementations include
    a 'ctx: Context' parameter in their function signatures that the framework
    fails to strip from the exposed JSON schema.  This parameter is an internal
    MCP framework injection and must never be presented to callers.
    """
    schema = tool.inputSchema
    if not isinstance(schema, dict):
        return tool

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    if "ctx" not in required and "ctx" not in properties:
        return tool

    new_schema = dict(schema)
    if "ctx" in required:
        new_schema["required"] = [f for f in required if f != "ctx"]
    if "ctx" in properties:
        new_schema["properties"] = {k: v for k, v in properties.items() if k != "ctx"}

    return tool.model_copy(update={"inputSchema": new_schema})


@dataclass
class ProxyToolInfo:
    """Information about a proxied tool."""

    server: str
    name: str
    description: str
    input_schema: dict[str, Any]


class ProxyManager:
    """Manages connections to external MCP servers using FastMCP Client.

    Connects to configured MCP servers at startup and provides
    a unified interface for calling their tools.
    """

    def __init__(self) -> None:
        """Initialize the proxy manager."""
        self._clients: dict[str, Client] = {}  # type: ignore[type-arg]
        self._tools_by_server: dict[str, list[types.Tool]] = {}
        self._errors: dict[str, str] = {}  # server name -> last error message
        self._server_timeouts: dict[str, float] = {}  # server name -> configured timeout
        self._server_instructions: dict[str, str] = {}  # server name -> native instructions
        self._initialized = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connect_task: asyncio.Task[None] | None = None
        self._mutation_lock = threading.RLock()

    @property
    def servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._clients.keys())

    @property
    def is_connecting(self) -> bool:
        """True if a background connection task is still in progress."""
        return self._connect_task is not None and not self._connect_task.done()

    @property
    def tool_count(self) -> int:
        """Total number of proxied tools across all servers."""
        return sum(len(tools) for tools in self._tools_by_server.values())

    def server_tool_count(self, name: str) -> int:
        """Number of tools registered for a specific server."""
        return len(self._tools_by_server.get(name, []))

    def get_connection(self, server: str) -> Client | None:  # type: ignore[type-arg]
        """Get a client by server name."""
        return self._clients.get(server)

    def get_server_timeout(self, server: str) -> float:
        """Return the configured timeout for a server, defaulting to 30s."""
        return self._server_timeouts.get(server, 30.0)

    def get_error(self, server: str) -> str | None:
        """Get the last connection error for a server."""
        return self._errors.get(server)

    def get_server_instructions(self, server: str) -> str:
        """Return native instructions from the server's InitializeResult, or ''."""
        return self._server_instructions.get(server, "")

    def readiness(self, configured_servers: list[str] | tuple[str, ...]) -> dict[str, Any]:
        """Return proxy readiness and per-server connection state."""
        servers: dict[str, Any] = {}
        for name in configured_servers:
            if name in self._clients:
                servers[name] = {
                    "status": "connected",
                    "tool_count": len(self._tools_by_server.get(name, [])),
                }
            elif error := self._errors.get(name):
                servers[name] = {"status": "failed", "error": error}
            elif self.is_connecting:
                servers[name] = {"status": "connecting"}
            else:
                servers[name] = {"status": "disconnected"}

        failed = sum(1 for state in servers.values() if state["status"] == "failed")
        connected = sum(1 for state in servers.values() if state["status"] == "connected")
        return {
            "ready": not self.is_connecting,
            "status": "degraded" if failed else "ok",
            "configured": len(configured_servers),
            "connected": connected,
            "failed": failed,
            "servers": servers,
        }

    def list_tools(self, server: str | None = None) -> list[ProxyToolInfo]:
        """List available tools from proxied servers.

        Args:
            server: Optional server name to filter by. If None, returns all tools.

        Returns:
            List of ProxyToolInfo for available tools.
        """
        items = (
            [(server, t) for t in self._tools_by_server.get(server, [])]
            if server
            else [(srv, t) for srv, ts in self._tools_by_server.items() for t in ts]
        )
        return [
            ProxyToolInfo(server=srv, name=t.name, description=t.description or "", input_schema=t.inputSchema)
            for srv, t in items
        ]

    async def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str | dict[str, Any] | list[Any]:
        """Call a tool on a proxied MCP server.

        Args:
            server: Name of the server to call.
            tool: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            timeout: Timeout for the call in seconds.

        Returns:
            Parsed result: dict/list for JSON responses, str for text, str for empty.

        Raises:
            ValueError: If server is not connected.
            RuntimeError: If the tool returns an error.
            TimeoutError: If the call times out.
        """
        client = self._clients.get(server)
        if not client:
            if self.is_connecting:
                raise ValueError(
                    f"Server '{server}' is still connecting. Please try again in a moment."
                )
            available = ", ".join(self._clients.keys()) or "none"
            raise ValueError(f"Server '{server}' not connected. Available: {available}")

        arguments = arguments or {}

        with LogSpan(span="proxy.tool.call", server=server, tool=tool) as span:
            try:
                result = await asyncio.wait_for(
                    client.call_tool(tool, arguments),
                    timeout=timeout,
                )
            except TimeoutError:
                logger.error(
                    LogEntry(
                        event="proxy.tool.timeout",
                        server=server,
                        tool=tool,
                        timeout=timeout,
                    ).failure(error_type="TimeoutError", error_message="proxy tool call timed out")
                )
                raise TimeoutError(
                    f"Tool {server}.{tool} timed out after {timeout}s"
                ) from None

            # Extract and auto-parse text from result
            text_parts: list[str] = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    text_parts.append(content.text)
                elif hasattr(content, "data"):
                    text_parts.append(f"[Binary content: {type(content).__name__}]")

            if not text_parts:
                result_value: str | dict[str, Any] | list[Any] = "Tool returned empty response."
            elif len(text_parts) == 1:
                # Single text part: try to parse as JSON for structured return
                try:
                    result_value = json.loads(text_parts[0])
                except (json.JSONDecodeError, ValueError):
                    result_value = text_parts[0]
            else:
                # Multi-part: concatenate as string
                result_value = "\n".join(text_parts)

            span.add("resultLength", len(str(result_value)))
            return result_value

    def call_tool_sync(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
        fire_and_forget: bool = False,
    ) -> str | dict[str, Any] | list[Any]:
        """Synchronously call a tool on a proxied MCP server.

        This is a blocking wrapper around the async call_tool method,
        suitable for use from sync code (like executed Python code).

        Args:
            server: Name of the server to call.
            tool: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            timeout: Timeout for the call in seconds.
            fire_and_forget: If True, schedule the call and return "started"
                immediately without waiting for the result. Useful for slow
                operations (e.g. browser navigation) where you don't need
                the return value.

        Returns:
            Text result from the tool, or "started" if fire_and_forget=True.
        """
        if self._loop is None:
            raise RuntimeError(
                "Proxy manager not initialized - no event loop available"
            )

        if fire_and_forget:
            fut = asyncio.run_coroutine_threadsafe(
                self.call_tool(server, tool, arguments, timeout),
                self._loop,
            )

            def log_fire_and_forget_failure(
                future: Future[str | dict[str, Any] | list[Any]],
            ) -> None:
                exc = future.exception()
                if exc is None:
                    return
                logger.warning(
                    LogEntry(
                        event="proxy.tool.fire_and_forget_failed",
                        server=server,
                        tool=tool,
                    ).failure(error_type=type(exc).__name__, error_message=str(exc))
                )

            fut.add_done_callback(log_fire_and_forget_failure)
            return "started"

        future = asyncio.run_coroutine_threadsafe(
            self.call_tool(server, tool, arguments, timeout),
            self._loop,
        )
        return future.result(timeout=timeout + 5)

    def list_resources_sync(self, server: str, timeout: float = 5.0) -> list[dict[str, Any]]:
        """Synchronously list resources from a proxied MCP server.

        Blocking wrapper around list_resources, suitable for sync code.

        Args:
            server: Name of the server.
            timeout: Timeout in seconds.

        Returns:
            List of resource metadata dicts, or empty list if not connected.
        """
        if self._loop is None or not self._loop.is_running():
            return []
        future = asyncio.run_coroutine_threadsafe(self.list_resources(server), self._loop)
        return future.result(timeout=timeout)

    def list_prompts_sync(self, server: str, timeout: float = 5.0) -> list[dict[str, Any]]:
        """Synchronously list prompts from a proxied MCP server.

        Blocking wrapper around list_prompts, suitable for sync code.

        Args:
            server: Name of the server.
            timeout: Timeout in seconds.

        Returns:
            List of prompt metadata dicts, or empty list if not connected.
        """
        if self._loop is None or not self._loop.is_running():
            return []
        future = asyncio.run_coroutine_threadsafe(self.list_prompts(server), self._loop)
        return future.result(timeout=timeout)

    async def list_resources(self, server: str) -> list[dict[str, Any]]:
        """List resources from a proxied MCP server.

        Args:
            server: Name of the server.

        Returns:
            List of resource metadata dicts. Empty list if server doesn't support resources.

        Raises:
            ValueError: If server is not connected.
        """
        client = self._clients.get(server)
        if not client:
            raise ValueError(f"Server '{server}' not connected")

        try:
            resources = await client.list_resources()
            return [{"uri": r.uri, "name": r.name, "description": r.description or ""} for r in resources]
        except (AttributeError, NotImplementedError):
            # Server doesn't support resources
            return []
        except Exception as e:
            # Check if error indicates unsupported feature
            error_msg = str(e).lower()
            if any(x in error_msg for x in ["not found", "not supported", "not implemented"]):
                return []
            raise

    async def read_resource(self, server: str, uri: str) -> str:
        """Read a resource from a proxied MCP server.

        Args:
            server: Name of the server.
            uri: Resource URI to read.

        Returns:
            Resource content as text.

        Raises:
            ValueError: If server is not connected.
        """
        client = self._clients.get(server)
        if not client:
            raise ValueError(f"Server '{server}' not connected")

        result = await client.read_resource(uri)
        # Extract text from resource contents (ReadResourceResult.contents)
        text_parts = []
        for content in result.contents:  # type: ignore[attr-defined]
            if hasattr(content, "text"):
                text_parts.append(content.text)
        return "\n".join(text_parts) if text_parts else ""

    async def list_prompts(self, server: str) -> list[dict[str, Any]]:
        """List prompts from a proxied MCP server.

        Args:
            server: Name of the server.

        Returns:
            List of prompt metadata dicts. Empty list if server doesn't support prompts.

        Raises:
            ValueError: If server is not connected.
        """
        client = self._clients.get(server)
        if not client:
            raise ValueError(f"Server '{server}' not connected")

        try:
            prompts = await client.list_prompts()
            return [{"name": p.name, "description": p.description or ""} for p in prompts]
        except (AttributeError, NotImplementedError):
            # Server doesn't support prompts
            return []
        except Exception as e:
            # Check if error indicates unsupported feature
            error_msg = str(e).lower()
            if any(x in error_msg for x in ["not found", "not supported", "not implemented"]):
                return []
            raise

    async def get_prompt(self, server: str, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Get a rendered prompt from a proxied MCP server.

        Args:
            server: Name of the server.
            name: Prompt name.
            arguments: Optional arguments for the prompt.

        Returns:
            Rendered prompt content as text.

        Raises:
            ValueError: If server is not connected.
        """
        client = self._clients.get(server)
        if not client:
            raise ValueError(f"Server '{server}' not connected")

        result = await client.get_prompt(name, arguments or {})
        # Extract text from prompt messages
        text_parts = []
        for message in result.messages:
            if hasattr(message, "content"):
                content = message.content
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    # Content is a list of content parts
                    for part in content:
                        if hasattr(part, "text"):
                            text_parts.append(part.text)
                elif hasattr(content, "text"):
                    text_parts.append(content.text)
        return "\n".join(text_parts) if text_parts else ""

    async def connect(self, configs: dict[str, McpServerConfig]) -> None:
        """Connect to all enabled MCP servers.

        Args:
            configs: Dictionary of server name -> configuration.
        """
        if self._initialized:
            return

        self._loop = asyncio.get_running_loop()

        enabled_configs = {name: cfg for name, cfg in configs.items() if cfg.enabled}

        if not enabled_configs:
            logger.debug("No MCP servers configured for proxying")
            self._initialized = True
            return

        try:
            with LogSpan(span="proxy.init", serverCount=len(enabled_configs)) as span:
                connected = 0
                failed = 0

                async def connect_one(name: str, config: McpServerConfig) -> bool:
                    try:
                        await self._connect_server(name, config)
                        self._errors.pop(name, None)  # Clear any previous error
                        return True
                    except asyncio.CancelledError:
                        self._errors[name] = "cancelled"
                        raise
                    except Exception as e:
                        self._errors[name] = str(e)
                        logger.warning(
                            LogEntry(event="proxy.connect.failed", server=name).failure(e)
                        )
                        return False

                results = await asyncio.gather(
                    *(connect_one(name, config) for name, config in enabled_configs.items())
                )
                connected = sum(1 for result in results if result)
                failed = len(results) - connected

                span.add("connected", connected)
                span.add("failed", failed)
                span.add("toolCount", self.tool_count)
        finally:
            self._initialized = True

    def connect_background(self, configs: dict[str, McpServerConfig]) -> asyncio.Task[None]:
        """Start connecting to proxy servers in the background.

        Returns immediately after scheduling the connection task. The MCP server
        can begin handling requests right away; proxy tools return a "still connecting"
        error until their server is ready.

        Args:
            configs: Dictionary of server name -> configuration.

        Returns:
            The asyncio Task driving the connection.
        """
        self._loop = asyncio.get_running_loop()
        self._connect_task = asyncio.create_task(self.connect(configs))
        return self._connect_task

    async def _connect_server(self, name: str, config: McpServerConfig) -> None:
        """Connect to a single MCP server using FastMCP Client."""
        with LogSpan(span="proxy.connect", server=name, type=config.type) as span:
            client = self._create_client(name, config)

            # Enter the client context manager for persistent connection
            await client.__aenter__()  # type: ignore[no-untyped-call]

            try:
                # List tools to verify connection and cache tool info
                tools = await client.list_tools()
                tools = [_strip_ctx_from_schema(t) for t in tools]

                # Capture native instructions from InitializeResult (MCP standard)
                init_result = getattr(client, "initialize_result", None)
                with self._mutation_lock:
                    self._clients[name] = client
                    self._tools_by_server[name] = tools
                    self._server_timeouts[name] = float(config.timeout)
                    self._server_instructions[name] = (
                        (init_result.instructions or "") if init_result else ""
                    )

                span.add("toolCount", len(tools))
                logger.info(
                    LogEntry(
                        event="proxy.connect.ready",
                        server=name,
                        serverType=config.type,
                        toolCount=len(tools),
                    ).success()
                )

            except BaseException:
                # Clean up on failure — catches CancelledError too
                await client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
                raise

    def _create_client(self, name: str, config: McpServerConfig) -> Client:  # type: ignore[type-arg]
        """Create a FastMCP Client for the given configuration."""
        if config.type == "http":
            return self._create_http_client(name, config)
        elif config.type == "stdio":
            return self._create_stdio_client(name, config)
        else:
            raise ValueError(f"Unknown server type: {config.type}")

    def _create_http_client(self, name: str, config: McpServerConfig) -> Client:  # type: ignore[type-arg]
        """Create an HTTP client using Streamable HTTP transport.

        Streamable HTTP is the recommended MCP transport for web-based servers,
        supporting both batch responses and streaming via SSE.
        """
        if not config.url:
            raise RuntimeError(f"Server {name}: HTTP server requires url")

        url = config.url

        # Expand secrets in headers
        headers = {}
        for key, value in config.headers.items():
            if "${" in value:
                headers[key] = expand_vars(value)
            else:
                headers[key] = value

        # Configure authentication
        auth: OAuth | BearerAuth | None = None
        if config.auth:
            if config.auth.type == "oauth":
                auth = OAuth(
                    mcp_url=url,
                    scopes=config.auth.scopes or [],
                    client_name="OneTool",
                )
                logger.debug(f"Configured OAuth for {name} with scopes: {config.auth.scopes}")
            else:  # bearer
                token = expand_vars(config.auth.token) if config.auth.token else ""
                auth = BearerAuth(token)
                logger.debug(f"Configured bearer auth for {name}")

        transport = StreamableHttpTransport(url=url, headers=headers if headers else None, auth=auth)
        return Client(transport, timeout=float(config.timeout))

    def _create_stdio_client(self, name: str, config: McpServerConfig) -> Client:  # type: ignore[type-arg]
        """Create a stdio client."""
        if not config.command:
            raise RuntimeError(f"Server {name}: stdio server requires command")

        # Build environment variables for subprocess
        # Default: clean env with only PATH. With inherit_env: true, inherit parent env.
        if config.inherit_env:
            env = os.environ.copy()
        else:
            env = {"PATH": os.environ.get("PATH", "")}

        # Get root-level env from config (if available)
        try:
            from ot.config import get_config
            root_config = get_config()
            root_env = root_config.env
        except (ImportError, AttributeError, RuntimeError):
            root_env = {}

        # Merge: root env first, then server-specific env (overrides parent/root)
        configured_keys: set[str] = set()
        for key, value in root_env.items():
            env[key] = value
            configured_keys.add(key)
        for key, value in config.env.items():
            env[key] = value
            configured_keys.add(key)

        # Expand ${VAR} patterns from secrets and config env: in configured values only
        for key in configured_keys:
            value = env[key]
            if "${" in value:
                env[key] = expand_vars(value)

        transport = StdioTransport(
            command=config.command,
            args=config.args,
            env=env,
        )

        return Client(transport, timeout=float(config.timeout))

    def _reset_state(self) -> None:
        """Reset all connection state without disconnecting (for cases where loop is unavailable)."""
        with self._mutation_lock:
            self._clients.clear()
            self._tools_by_server.clear()
            self._errors.clear()
            self._server_timeouts.clear()
            self._server_instructions.clear()
            self._initialized = False
            self._connect_task = None

    async def _close_client_transport(self, client: Client) -> None:  # type: ignore[type-arg]
        """Close the underlying transport when FastMCP exposes an async close hook."""
        transport = getattr(client, "transport", None)
        if transport is not None and hasattr(transport, "close"):
            await transport.close()

    async def shutdown(self) -> None:
        """Disconnect from all MCP servers."""
        # Cancel background connect task if still running
        if self._connect_task is not None and not self._connect_task.done():
            self._connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connect_task
        self._connect_task = None

        if not self._clients:
            return

        with LogSpan(span="proxy.shutdown", serverCount=len(self._clients)):
            for name, client in list(self._clients.items()):
                try:
                    await client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
                    # transport.close() terminates stdio subprocesses left alive by
                    # FastMCP keep_alive after __aexit__ exits the session.
                    await self._close_client_transport(client)
                    logger.debug(f"Disconnected from MCP server '{name}'")
                except (Exception, asyncio.CancelledError) as e:
                    logger.debug(f"Error disconnecting from '{name}': {e}")

            with self._mutation_lock:
                self._clients.clear()
                self._tools_by_server.clear()
                self._errors.clear()
                self._server_timeouts.clear()
                self._server_instructions.clear()
                self._initialized = False

    async def reconnect(self, configs: dict[str, McpServerConfig]) -> None:
        """Reconnect to all MCP servers.

        Shuts down existing connections and reconnects with fresh config.

        Args:
            configs: Dictionary of server name -> configuration.
        """
        await self.shutdown()
        await self.connect(configs)

    async def connect_additional(self, name: str, config: McpServerConfig) -> str:
        """Connect a single new server without disrupting existing connections.

        Args:
            name: Server name.
            config: Server configuration.

        Returns:
            Status string: "ok (N tools)", "already connected", "disabled", or "failed: <reason>".
        """
        with self._mutation_lock:
            if name in self._clients:
                return "already connected"
            if not config.enabled:
                return "disabled"
        try:
            await self._connect_server(name, config)
            with self._mutation_lock:
                self._errors.pop(name, None)
                tool_count = len(self._tools_by_server.get(name, []))
            return f"ok ({tool_count} tools)"
        except Exception as e:
            with self._mutation_lock:
                self._errors[name] = str(e)
            logger.warning(LogEntry(event="proxy.connect.failed", server=name).failure(e))
            return f"failed: {e}"

    def connect_additional_sync(self, name: str, config: McpServerConfig) -> str:
        """Synchronously connect a single new server without disrupting existing connections.

        Blocking wrapper around connect_additional.

        Args:
            name: Server name.
            config: Server configuration.

        Returns:
            Status string: "ok (N tools)", "already connected", "disabled", or "failed: <reason>".
        """
        if self._loop is None or not self._loop.is_running():
            return "failed: no running event loop"
        future = asyncio.run_coroutine_threadsafe(
            self.connect_additional(name, config),
            self._loop,
        )
        return future.result(timeout=120)

    async def disconnect_server(self, name: str) -> str:
        """Disconnect a single server without affecting other connections.

        Args:
            name: Server name to disconnect.

        Returns:
            Status string: "disconnected" or "not connected".
        """
        with self._mutation_lock:
            if name not in self._clients:
                return "not connected"
            client = self._clients.pop(name)
            self._tools_by_server.pop(name, None)
            self._errors.pop(name, None)
            self._server_instructions.pop(name, None)
            self._server_timeouts.pop(name, None)
        try:
            await client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
            await self._close_client_transport(client)
            logger.debug(f"Disconnected from MCP server '{name}'")
        except Exception as e:
            logger.debug(f"Error disconnecting from '{name}': {e}")
        return "disconnected"

    def disconnect_server_sync(self, name: str) -> str:
        """Synchronously disconnect a single server without affecting other connections.

        Blocking wrapper around disconnect_server.

        Args:
            name: Server name to disconnect.

        Returns:
            Status string: "disconnected" or "not connected".
        """
        if self._loop is None or not self._loop.is_running():
            with self._mutation_lock:
                if name not in self._clients:
                    return "not connected"
                self._clients.pop(name)
                self._tools_by_server.pop(name, None)
                self._errors.pop(name, None)
                self._server_instructions.pop(name, None)
                self._server_timeouts.pop(name, None)
                logger.warning(
                    f"Removed server '{name}' without async cleanup — "
                    "no running event loop; underlying transport may not be closed."
                )
                return "disconnected"
        future = asyncio.run_coroutine_threadsafe(
            self.disconnect_server(name),
            self._loop,
        )
        return future.result(timeout=30)

    def reconnect_sync(self, configs: dict[str, McpServerConfig]) -> None:
        """Synchronously reconnect to all MCP servers.

        Blocking wrapper for reconnect, suitable for calling from sync code.

        Args:
            configs: Dictionary of server name -> configuration.
        """
        loop = self._loop

        # Try to get running loop if we don't have one stored
        if loop is None:
            with contextlib.suppress(RuntimeError):
                loop = asyncio.get_running_loop()

        # Must have a running loop to schedule the coroutine
        # If loop exists but isn't running, we can't await the coroutine
        if loop is None or not loop.is_running():
            # No running event loop available - just reset state, connect will happen on next use
            self._reset_state()
            return

        with contextlib.suppress(RuntimeError):
            running_loop = asyncio.get_running_loop()
            if running_loop is loop:
                self._reset_state()
                self._connect_task = loop.create_task(self.connect(configs))
                return

        future = asyncio.run_coroutine_threadsafe(
            self.reconnect(configs),
            loop,
        )
        try:
            future.result(timeout=60)
        except Exception as e:
            logger.warning(
                LogEntry(
                    event="proxy.reconnect.failed",
                    serverCount=len(configs),
                    reconnectPath="threadsafe",
                ).failure(e)
            )


# Global proxy manager instance
_proxy_manager: ProxyManager | None = None


def get_proxy_manager() -> ProxyManager:
    """Get or create the global proxy manager instance.

    Returns:
        ProxyManager instance.
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager


def reset_proxy_manager() -> None:
    """Reset the global proxy manager (for testing)."""
    global _proxy_manager
    _proxy_manager = None


def reconnect_proxy_manager() -> None:
    """Reconnect the global proxy manager with fresh config.

    Loads server configs from the current configuration and reconnects
    all MCP proxy servers. Call this after modifying server config.
    """
    from ot.config.loader import get_config

    proxy = get_proxy_manager()
    cfg = get_config()

    enabled_servers = (
        {name: config for name, config in cfg.servers.items() if config.enabled}
        if cfg.servers
        else {}
    )
    if enabled_servers:
        proxy.reconnect_sync(enabled_servers)
    else:
        proxy._reset_state()
