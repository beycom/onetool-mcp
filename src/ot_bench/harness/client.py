"""MCP client utilities for connecting to MCP servers via stdio and HTTP."""

from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from ot.logging import LogSpan
from ot.utils import flatten_exception_group

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openai.types.chat import ChatCompletionToolParam

    from ot_bench.harness.config import ServerConfig


# Default timeout for MCP operations (30 seconds)
DEFAULT_TIMEOUT = 30.0

# Known server error hints for better diagnostics
_SERVER_ERROR_HINTS: dict[str, str] = {
    "chunkhound": (
        "ChunkHound requires: 1) Valid OPENAI_API_KEY, "
        "2) Indexed codebase (run 'uvx chunkhound index <path>' first)"
    ),
    "github": (
        "GitHub Copilot MCP requires a token with 'Copilot Requests' permission "
        "from an account with active Copilot subscription"
    ),
}


def _enhance_error_message(server_name: str, error: str) -> str:
    """Add helpful context to known server errors."""
    hint = _SERVER_ERROR_HINTS.get(server_name)
    if hint and ("closed" in error.lower() or "401" in error or "unauthorized" in error.lower()):
        return f"{error}. Hint: {hint}"
    return error


@dataclass
class MCPConnection:
    """Represents an active MCP connection."""

    session: ClientSession
    tools: list[types.Tool]
    server_name: str = ""
    instructions: str | None = None
    prompts: list[types.Prompt] = field(default_factory=list)
    resources: list[types.Resource] = field(default_factory=list)


@dataclass
class ServerHealth:
    """Health check result for an MCP server."""

    name: str
    healthy: bool
    tool_count: int = 0
    error: str | None = None


@dataclass
class MultiServerConnection:
    """Represents connections to multiple MCP servers."""

    connections: dict[str, MCPConnection] = field(default_factory=dict)
    health: list[ServerHealth] = field(default_factory=list)

    @property
    def all_tools(self) -> list[types.Tool]:
        """Get all tools from all connected servers."""
        tools: list[types.Tool] = []
        for conn in self.connections.values():
            tools.extend(conn.tools)
        return tools

    @property
    def all_instructions(self) -> list[tuple[str, str]]:
        """Get instructions from all connected servers.

        Returns:
            List of (server_name, instructions) tuples for servers with instructions.
        """
        instructions: list[tuple[str, str]] = []
        for name, conn in self.connections.items():
            if conn.instructions:
                instructions.append((name, conn.instructions))
        return instructions

    @property
    def all_prompts(self) -> list[tuple[str, types.Prompt]]:
        """Get prompts from all connected servers.

        Returns:
            List of (server_name, prompt) tuples.
        """
        prompts: list[tuple[str, types.Prompt]] = []
        for name, conn in self.connections.items():
            for prompt in conn.prompts:
                prompts.append((name, prompt))
        return prompts

    @property
    def all_resources(self) -> list[tuple[str, types.Resource]]:
        """Get resources from all connected servers.

        Returns:
            List of (server_name, resource) tuples.
        """
        resources: list[tuple[str, types.Resource]] = []
        for name, conn in self.connections.items():
            for resource in conn.resources:
                resources.append((name, resource))
        return resources

    @property
    def healthy_count(self) -> int:
        """Count of healthy servers."""
        return sum(1 for h in self.health if h.healthy)

    @property
    def failed_count(self) -> int:
        """Count of failed servers."""
        return sum(1 for h in self.health if not h.healthy)

    def get_session_for_tool(self, tool_name: str) -> ClientSession | None:
        """Get the session that owns a specific tool."""
        for conn in self.connections.values():
            if any(t.name == tool_name for t in conn.tools):
                return conn.session
        return None


async def call_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Call an MCP tool and return the text result.

    Args:
        session: Active MCP client session.
        tool_name: Name of the tool to call.
        arguments: Arguments to pass to the tool.
        timeout: Timeout for the call in seconds.

    Returns:
        Text content from the tool response.

    Raises:
        TimeoutError: If the call times out.
        RuntimeError: If the tool returns an error or no text content.
    """
    try:
        result = await asyncio.wait_for(
            session.call_tool(tool_name, arguments),
            timeout=timeout,
        )
    except TimeoutError:
        logger.error(
            f"Tool call timeout | tool={tool_name} | timeout={timeout}s | "
            f"args={str(arguments)[:100]}"
        )
        raise TimeoutError(f"Tool {tool_name} timed out after {timeout}s") from None

    if result.isError:
        error_text = ""
        for content in result.content:
            if isinstance(content, types.TextContent):
                error_text += content.text
        # Log structured error details
        logger.warning(
            f"Tool returned error | tool={tool_name} | "
            f"error={error_text[:200]} | args={str(arguments)[:100]}"
        )
        # "No results" type errors are not fatal - return as message
        error_lower = error_text.lower()
        if any(
            phrase in error_lower
            for phrase in ["no web results", "no results", "no matches", "not found"]
        ):
            return "Search returned no results for this query."
        raise RuntimeError(f"Tool {tool_name} returned error: {error_text}")

    text_parts: list[str] = []
    for content in result.content:
        if isinstance(content, types.TextContent):
            text_parts.append(content.text)
        elif hasattr(content, "data"):
            # Handle binary/image content
            text_parts.append(f"[Binary content: {type(content).__name__}]")

    if not text_parts:
        logger.warning(
            f"Tool returned empty content | tool={tool_name} | "
            f"content_types={[type(c).__name__ for c in result.content]}"
        )
        return "Tool returned empty response."

    return "\n".join(text_parts)




def mcp_tools_to_openai(
    tools: list[types.Tool],
    duplicate: int = 1,
) -> list[ChatCompletionToolParam]:
    """Convert MCP tools to OpenAI ChatCompletionToolParam format.

    Args:
        tools: List of MCP Tool objects from MCPConnection.tools.
        duplicate: Number of times to duplicate each tool (simulates many MCP servers).
                   Each duplicate gets a suffix like _2, _3, etc.

    Returns:
        List of tool definitions in OpenAI function calling format.
    """
    openai_tools: list[ChatCompletionToolParam] = []

    for copy_num in range(duplicate):
        suffix = "" if copy_num == 0 else f"_{copy_num + 1}"
        for tool in tools:
            parameters = tool.inputSchema

            openai_tool: ChatCompletionToolParam = {
                "type": "function",
                "function": {
                    "name": f"{tool.name}{suffix}",
                    "description": tool.description or "",
                    "parameters": parameters,
                },
            }
            openai_tools.append(openai_tool)

    return openai_tools


def multi_server_tools_to_openai(
    multi: MultiServerConnection,
) -> tuple[list[ChatCompletionToolParam], dict[str, tuple[str, str]]]:
    """Convert tools from multiple MCP servers to OpenAI format with prefixed names.

    When multiple servers are connected, tool names are prefixed with the server name
    to avoid collisions (e.g., github and supabase both having 'create_branch').

    Args:
        multi: MultiServerConnection with connected servers.

    Returns:
        Tuple of:
        - List of tool definitions in OpenAI function calling format
        - Mapping from prefixed tool name to (server_name, original_tool_name)
    """
    openai_tools: list[ChatCompletionToolParam] = []
    tool_mapping: dict[str, tuple[str, str]] = {}

    # Only prefix if multiple servers are connected
    use_prefix = len(multi.connections) > 1

    for server_name, conn in multi.connections.items():
        for tool in conn.tools:
            # Create prefixed name for multi-server, original name for single-server
            prefixed_name = f"{server_name}__{tool.name}" if use_prefix else tool.name

            parameters = tool.inputSchema

            # Build description with server context for multi-server
            description = tool.description or ""
            if use_prefix:
                description = f"[{server_name}] {description}"

            openai_tool: ChatCompletionToolParam = {
                "type": "function",
                "function": {
                    "name": prefixed_name,
                    "description": description,
                    "parameters": parameters,
                },
            }
            openai_tools.append(openai_tool)
            tool_mapping[prefixed_name] = (server_name, tool.name)

    return openai_tools, tool_mapping


@asynccontextmanager
async def connect_to_server(
    name: str,
    config: ServerConfig,
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncIterator[MCPConnection]:
    """Connect to any MCP server based on its configuration.

    Args:
        name: Server name for identification.
        config: Server configuration.
        timeout: Timeout for operations in seconds.

    Yields:
        MCPConnection with active session and available tools.

    Raises:
        RuntimeError: If connection fails or required config is missing.
    """
    if config.type == "http":
        if not config.url:
            raise RuntimeError(f"Server {name}: HTTP server requires url")

        # Headers should be fully expanded by config loader - error if not
        headers = {}
        for key, value in config.headers.items():
            # Check if value still contains unexpanded ${VAR} pattern
            if "${" in value and "}" in value:
                match = re.search(r"\$\{([^}]+)\}", value)
                if match:
                    var_name = match.group(1)
                    raise RuntimeError(
                        f"Server {name}: Unexpanded variable ${{{var_name}}} in header. "
                        f"Add {var_name} to .onetool/config/bench-secrets.yaml"
                    )
            headers[key] = value

        import httpx

        # Create httpx client with headers and timeout
        http_client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(timeout, read=timeout * 10),
        )

        try:
            async with (
                streamable_http_client(
                    url=config.url,
                    http_client=http_client,
                ) as (read, write, _get_session_id),
                ClientSession(read, write) as session,
            ):
                init_result = await asyncio.wait_for(
                    session.initialize(), timeout=timeout
                )
                # Fetch all server capabilities in parallel
                tools_result, prompts_result, resources_result = await asyncio.gather(
                    asyncio.wait_for(session.list_tools(), timeout=timeout),
                    asyncio.wait_for(session.list_prompts(), timeout=timeout),
                    asyncio.wait_for(session.list_resources(), timeout=timeout),
                    return_exceptions=True,
                )
                # Handle potential errors (some servers may not support all features)
                tools = (
                    tools_result.tools
                    if not isinstance(tools_result, Exception)
                    else []
                )
                prompts = (
                    prompts_result.prompts
                    if not isinstance(prompts_result, Exception)
                    else []
                )
                resources = (
                    resources_result.resources
                    if not isinstance(resources_result, Exception)
                    else []
                )

                yield MCPConnection(
                    session=session,
                    tools=tools,
                    server_name=name,
                    instructions=init_result.instructions,
                    prompts=prompts,
                    resources=resources,
                )
        except asyncio.CancelledError:
            # Connection was cancelled (e.g., server closed while waiting)
            logger.debug(f"HTTP connection cancelled | name={name}")
        except BaseExceptionGroup as eg:
            # Handle race condition where server tries to send response
            # after client has closed the connection.
            from anyio import BrokenResourceError, ClosedResourceError

            leaf_exceptions = flatten_exception_group(eg)
            connection_errors = [
                e
                for e in leaf_exceptions
                if isinstance(
                    e,
                    (
                        ClosedResourceError,
                        BrokenResourceError,
                        asyncio.CancelledError,
                    ),
                )
            ]
            if len(connection_errors) == len(leaf_exceptions):
                logger.debug(
                    f"HTTP connection closed during cleanup | name={name} | "
                    f"errors={len(connection_errors)}"
                )
            else:
                raise
        finally:
            await http_client.aclose()

    elif config.type == "stdio":
        if not config.command:
            raise RuntimeError(f"Server {name}: stdio server requires command")

        # Build environment: PATH only + explicit config.env
        from ot_bench.harness.config import expand_subprocess_env

        env = {"PATH": os.environ.get("PATH", "")}
        for key, value in config.env.items():
            env[key] = expand_subprocess_env(value)

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=env,
        )

        logger.debug(
            f"Starting stdio server | name={name} | "
            f"command={config.command} {' '.join(config.args[:3])}... | timeout={timeout}s"
        )

        try:
            # Timeout applies to entire case execution (connection + tool calls)
            async with asyncio.timeout(timeout):
                async with (
                    stdio_client(server_params) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    init_result = await session.initialize()
                    # Fetch all server capabilities in parallel
                    (
                        tools_result,
                        prompts_result,
                        resources_result,
                    ) = await asyncio.gather(
                        session.list_tools(),
                        session.list_prompts(),
                        session.list_resources(),
                        return_exceptions=True,
                    )
                    # Handle potential errors (some servers may not support all features)
                    tools = (
                        tools_result.tools
                        if not isinstance(tools_result, Exception)
                        else []
                    )
                    prompts = (
                        prompts_result.prompts
                        if not isinstance(prompts_result, Exception)
                        else []
                    )
                    resources = (
                        resources_result.resources
                        if not isinstance(resources_result, Exception)
                        else []
                    )

                    logger.debug(
                        f"Server ready | name={name} | tools={len(tools)} | "
                        f"prompts={len(prompts)} | resources={len(resources)}"
                    )
                    yield MCPConnection(
                        session=session,
                        tools=tools,
                        server_name=name,
                        instructions=init_result.instructions,
                        prompts=prompts,
                        resources=resources,
                    )
        except asyncio.CancelledError:
            # Connection was cancelled (e.g., server closed while client waiting)
            logger.debug(f"Connection cancelled | name={name}")
        except BaseExceptionGroup as eg:
            # Handle race condition where server tries to send response
            # after client has closed the connection. Extract leaf errors
            # and check if they're all connection-related.
            from anyio import BrokenResourceError, ClosedResourceError

            leaf_exceptions = flatten_exception_group(eg)
            connection_errors = [
                e
                for e in leaf_exceptions
                if isinstance(
                    e,
                    (
                        ClosedResourceError,
                        BrokenResourceError,
                        asyncio.CancelledError,
                    ),
                )
            ]
            if len(connection_errors) == len(leaf_exceptions):
                # All errors are connection-related, suppress them
                logger.debug(
                    f"Connection closed during cleanup | name={name} | "
                    f"errors={len(connection_errors)}"
                )
            else:
                # Some errors are not connection-related, re-raise
                raise
        except TimeoutError:
            logger.error(
                f"Server connection timeout | name={name} | timeout={timeout}s | "
                f"command={config.command}"
            )
            raise TimeoutError(
                f"Server {name} connection timed out after {timeout}s"
            ) from None
    else:
        raise RuntimeError(f"Server {name}: Unknown server type {config.type}")


class ServerConnectionCallback:
    """Callback for server connection progress."""

    def on_connecting(self, name: str) -> None:
        """Called when starting to connect to a server."""

    def on_connected(self, name: str, tool_count: int) -> None:
        """Called when successfully connected to a server."""

    def on_failed(self, name: str, error: str) -> None:
        """Called when connection to a server fails."""


class MultiServerContextManager:
    """Context manager for connecting to multiple servers."""

    def __init__(
        self,
        servers: dict[str, ServerConfig],
        server_names: list[str],
        timeout: float = DEFAULT_TIMEOUT,
        on_progress: ServerConnectionCallback | None = None,
    ) -> None:
        """Initialize multi-server connection.

        Args:
            servers: All available server configs.
            server_names: Names of servers to connect to.
            timeout: Timeout for each server connection.
            on_progress: Optional callback for connection progress.
        """
        self.servers = servers
        self.server_names = server_names
        self.timeout = timeout
        self.on_progress = on_progress
        self._contexts: list[Any] = []
        self._result: MultiServerConnection | None = None

    async def __aenter__(self) -> MultiServerConnection:
        """Connect to all servers in parallel and return combined connection."""
        result = MultiServerConnection()

        # Separate valid and invalid server names
        valid_servers: list[tuple[str, ServerConfig]] = []
        for name in self.server_names:
            if name not in self.servers:
                error_msg = f"Server '{name}' not found in config"
                result.health.append(
                    ServerHealth(name=name, healthy=False, error=error_msg)
                )
                logger.warning(error_msg)
                if self.on_progress:
                    self.on_progress.on_failed(name, error_msg)
            else:
                valid_servers.append((name, self.servers[name]))
                if self.on_progress:
                    self.on_progress.on_connecting(name)

        if not valid_servers:
            self._result = result
            return result

        async def connect_one(
            name: str, config: ServerConfig
        ) -> tuple[str, MCPConnection | Exception]:
            """Connect to a single server, returning result or exception."""
            try:
                ctx = connect_to_server(name, config, timeout=self.timeout)
                conn = await ctx.__aenter__()
                self._contexts.append(ctx)
                return (name, conn)
            except BaseExceptionGroup as eg:
                leaf_errors: list[str] = []
                for exc in eg.exceptions:
                    if isinstance(exc, BaseExceptionGroup):
                        for inner in exc.exceptions:
                            leaf_errors.append(str(inner))
                    else:
                        leaf_errors.append(str(exc))
                return (
                    name,
                    Exception("; ".join(leaf_errors) if leaf_errors else str(eg)),
                )
            except Exception as e:
                return (name, e)

        # Connect to all servers in parallel
        with LogSpan(span="bench.servers.connect", count=len(valid_servers)):
            results = await asyncio.gather(
                *[connect_one(name, config) for name, config in valid_servers]
            )

        # Process results
        for name, conn_or_error in results:
            if isinstance(conn_or_error, Exception):
                error_msg = _enhance_error_message(name, str(conn_or_error))
                result.health.append(
                    ServerHealth(name=name, healthy=False, error=error_msg)
                )
                logger.error(f"  ✗ {name}: {error_msg}")
                if self.on_progress:
                    self.on_progress.on_failed(name, error_msg)
            else:
                result.connections[name] = conn_or_error
                result.health.append(
                    ServerHealth(
                        name=name, healthy=True, tool_count=len(conn_or_error.tools)
                    )
                )
                if self.on_progress:
                    self.on_progress.on_connected(name, len(conn_or_error.tools))

        self._result = result
        return result

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close all server connections."""
        for ctx in reversed(self._contexts):
            try:
                await ctx.__aexit__(exc_type, exc_val, exc_tb)
            except BaseExceptionGroup as eg:
                # Extract leaf errors from nested TaskGroups
                leaf_errors: list[str] = []
                for exc in eg.exceptions:
                    if isinstance(exc, BaseExceptionGroup):
                        for inner in exc.exceptions:
                            leaf_errors.append(str(inner))
                    else:
                        leaf_errors.append(str(exc))
                error_msg = "; ".join(leaf_errors) if leaf_errors else str(eg)
                logger.debug(f"Connection cleanup: {error_msg}")
            except Exception as e:
                logger.debug(f"Connection cleanup: {e}")


def connect_to_servers(
    servers: dict[str, ServerConfig],
    server_names: list[str],
    timeout: float = DEFAULT_TIMEOUT,
    on_progress: ServerConnectionCallback | None = None,
) -> MultiServerContextManager:
    """Connect to multiple MCP servers.

    Args:
        servers: All available server configs from harness config.
        server_names: Names of servers to connect to.
        timeout: Timeout for each server connection.
        on_progress: Optional callback for connection progress.

    Returns:
        Context manager that yields MultiServerConnection.

    Example:
        async with connect_to_servers(config.servers, ["context7", "github"]) as multi:
            print(f"Connected to {multi.healthy_count} servers")
            for health in multi.health:
                if not health.healthy:
                    print(f"Failed: {health.name}: {health.error}")
    """
    return MultiServerContextManager(servers, server_names, timeout, on_progress)
