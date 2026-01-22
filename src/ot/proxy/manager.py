"""ProxyManager for connecting to external MCP servers using FastMCP Client.

Manages connections to external MCP servers and routes tool calls
through OneTool's single `run` tool interface.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from loguru import logger
from mcp import types

from ot.config.mcp import McpServerConfig, expand_secrets, expand_subprocess_env
from ot.logging import LogSpan


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
        self._initialized = False
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._clients.keys())

    @property
    def tool_count(self) -> int:
        """Total number of proxied tools across all servers."""
        return sum(len(tools) for tools in self._tools_by_server.values())

    def get_connection(self, server: str) -> Client | None:  # type: ignore[type-arg]
        """Get a client by server name."""
        return self._clients.get(server)

    def list_tools(self, server: str | None = None) -> list[ProxyToolInfo]:
        """List available tools from proxied servers.

        Args:
            server: Optional server name to filter by. If None, returns all tools.

        Returns:
            List of ProxyToolInfo for available tools.
        """
        tools: list[ProxyToolInfo] = []

        if server:
            if server in self._tools_by_server:
                for tool in self._tools_by_server[server]:
                    tools.append(
                        ProxyToolInfo(
                            server=server,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema,
                        )
                    )
        else:
            for srv_name, srv_tools in self._tools_by_server.items():
                for tool in srv_tools:
                    tools.append(
                        ProxyToolInfo(
                            server=srv_name,
                            name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema,
                        )
                    )

        return tools

    async def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str:
        """Call a tool on a proxied MCP server.

        Args:
            server: Name of the server to call.
            tool: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            timeout: Timeout for the call in seconds.

        Returns:
            Text result from the tool.

        Raises:
            ValueError: If server is not connected.
            RuntimeError: If the tool returns an error.
            TimeoutError: If the call times out.
        """
        client = self._clients.get(server)
        if not client:
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
                    f"Proxy tool timeout | server={server} | tool={tool} | timeout={timeout}s"
                )
                raise TimeoutError(
                    f"Tool {server}.{tool} timed out after {timeout}s"
                ) from None

            # Extract text from result
            text_parts: list[str] = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    text_parts.append(content.text)
                elif hasattr(content, "data"):
                    text_parts.append(f"[Binary content: {type(content).__name__}]")

            result_text = (
                "\n".join(text_parts) if text_parts else "Tool returned empty response."
            )
            span.add("resultLength", len(result_text))
            return result_text

    def call_tool_sync(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> str:
        """Synchronously call a tool on a proxied MCP server.

        This is a blocking wrapper around the async call_tool method,
        suitable for use from sync code (like executed Python code).

        Args:
            server: Name of the server to call.
            tool: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            timeout: Timeout for the call in seconds.

        Returns:
            Text result from the tool.
        """
        if self._loop is None:
            raise RuntimeError(
                "Proxy manager not initialized - no event loop available"
            )

        future = asyncio.run_coroutine_threadsafe(
            self.call_tool(server, tool, arguments, timeout),
            self._loop,
        )
        return future.result(timeout=timeout + 5)

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

        with LogSpan(span="proxy.init", serverCount=len(enabled_configs)) as span:
            connected = 0
            failed = 0

            for name, config in enabled_configs.items():
                try:
                    await self._connect_server(name, config)
                    connected += 1
                except Exception as e:
                    failed += 1
                    logger.warning(f"Failed to connect to MCP server '{name}': {e}")

            span.add("connected", connected)
            span.add("failed", failed)
            span.add("toolCount", self.tool_count)

        self._initialized = True

    async def _connect_server(self, name: str, config: McpServerConfig) -> None:
        """Connect to a single MCP server using FastMCP Client."""
        with LogSpan(span="proxy.connect", server=name, type=config.type) as span:
            client = self._create_client(name, config)

            # Enter the client context manager for persistent connection
            await client.__aenter__()  # type: ignore[no-untyped-call]

            try:
                # List tools to verify connection and cache tool info
                tools = await client.list_tools()

                self._clients[name] = client
                self._tools_by_server[name] = tools

                span.add("toolCount", len(tools))
                logger.info(
                    f"Connected to {config.type} MCP server '{name}' with {len(tools)} tools"
                )

            except Exception:
                # Clean up on failure
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
        """Create an HTTP/SSE client."""
        if not config.url:
            raise RuntimeError(f"Server {name}: HTTP server requires url")

        # Auto-upgrade http:// to https://
        url = config.url
        if url.startswith("http://"):
            url = "https://" + url[7:]
            logger.debug(f"Upgraded {name} URL to HTTPS: {url}")

        # Expand secrets in headers
        headers = {}
        for key, value in config.headers.items():
            if "${" in value:
                headers[key] = expand_secrets(value)
            else:
                headers[key] = value

        return Client(url, headers=headers, timeout=float(config.timeout))

    def _create_stdio_client(self, name: str, config: McpServerConfig) -> Client:  # type: ignore[type-arg]
        """Create a stdio client."""
        if not config.command:
            raise RuntimeError(f"Server {name}: stdio server requires command")

        # Build environment: PATH only + explicit config.env
        env = {"PATH": os.environ.get("PATH", "")}
        for key, value in config.env.items():
            env[key] = expand_subprocess_env(value)

        transport = StdioTransport(
            command=config.command,
            args=config.args,
            env=env,
        )

        return Client(transport, timeout=float(config.timeout))

    async def shutdown(self) -> None:
        """Disconnect from all MCP servers."""
        if not self._clients:
            return

        with LogSpan(span="proxy.shutdown", serverCount=len(self._clients)):
            for name, client in list(self._clients.items()):
                try:
                    await client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
                    logger.debug(f"Disconnected from MCP server '{name}'")
                except (Exception, asyncio.CancelledError) as e:
                    logger.debug(f"Error disconnecting from '{name}': {e}")

            self._clients.clear()
            self._tools_by_server.clear()
            self._initialized = False


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
