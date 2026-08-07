"""ProxyManager for connecting to external MCP servers using FastMCP Client.

Manages connections to external MCP servers and routes tool calls
through OneTool's single `run` tool interface.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import contextvars
import json
import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastmcp import Client, Context
from fastmcp.client.auth import BearerAuth, OAuth
from fastmcp.client.elicitation import (
    ElicitationHandler,
    ElicitRequestParams,
    ElicitResult,
)
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from loguru import logger
from mcp import types

from ot.config import expand_vars
from ot.logging import LogEntry, LogSpan
from ot.logging.redact import redact_secrets

if TYPE_CHECKING:
    from collections.abc import Coroutine, Iterator
    from concurrent.futures import Future

    from mcp.server.session import ServerSession

    from ot.config.models import McpServerConfig


_CONNECT_AUTH_RE = re.compile(
    r"(?P<label>\bauthorization\s*[:=]\s*(?:(?:bearer|basic)\s+)?"
    r"|\b(?:bearer|basic)\s+)(?P<secret>[^\s,;}\]]+)",
    re.IGNORECASE,
)
_CONNECT_SECRET_FIELD_RE = re.compile(
    r"(?P<label>[\"']?(?:access_token|refresh_token|id_token|client_secret|token|"
    r"api[-_ ]?key)[\"']?\s*[:=]\s*)(?P<quote>[\"']?)"
    r"(?P<secret>[^\"'\s,;}\]]+)(?P=quote)",
    re.IGNORECASE,
)


def _sanitize_connect_error(msg: str) -> str:
    """Redact credential-bearing substrings from a connect-error string.

    A decrypted secret can end up in a bearer/authorization header; if a connection
    failure echoes it, this keeps it out of ot.servers()/status output and logs while
    preserving enough context (exception type, non-credential text) to diagnose.

    Three layers, applied in order:
    1. Credential header/scheme redaction removes only the credential value, retaining
       safe error details that follow it.
    2. Credential field redaction handles JSON, form, and key/value token fields without
       treating diagnostic phrases such as ``Token exchange failed`` as credentials.
    3. ``redact_secrets()`` — the canonical, shape-based redactor (single source of
       truth, shared with logging/mem redaction) that catches raw secret literals
       (``sk-...``, ``ghp_...``, ``AKIA...``, connection strings, ...) regardless of
       whether a credential keyword precedes them.
    """
    msg = _CONNECT_AUTH_RE.sub(r"\g<label>[redacted]", msg)
    msg = _CONNECT_SECRET_FIELD_RE.sub(r"\g<label>[redacted]", msg)
    msg = redact_secrets(msg)
    return msg


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


@dataclass
class ProxyRequestContext:
    """Expiring ownership binding for proxy work started by one root request."""

    session: ServerSession
    request_id: types.RequestId
    _active: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def is_active(self) -> bool:
        """Return whether the originating root request is still active."""
        with self._lock:
            return self._active

    def expire(self) -> None:
        """Prevent future work from interacting through the root request."""
        with self._lock:
            self._active = False


@dataclass
class _ProxyCallContext:
    """State owned by exactly one serialized call to an upstream server."""

    request: ProxyRequestContext | None
    _active: bool = True
    _elicitation_unavailable_reason: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def is_active(self) -> bool:
        """Return whether the upstream call can still request interaction."""
        with self._lock:
            return self._active

    @property
    def elicitation_unavailable_reason(self) -> str | None:
        """Return why interactive input was unavailable for this call."""
        with self._lock:
            return self._elicitation_unavailable_reason

    def expire(self) -> None:
        """Prevent later callbacks from using this completed call."""
        with self._lock:
            self._active = False

    def record_elicitation_unavailable(self, reason: str) -> None:
        """Remember why this call could not provide accepted input."""
        with self._lock:
            self._elicitation_unavailable_reason = reason


_CURRENT_PROXY_REQUEST: contextvars.ContextVar[ProxyRequestContext | None] = (
    contextvars.ContextVar("ot_current_proxy_request", default=None)
)


@contextmanager
def bind_proxy_request_context(context: Context) -> Iterator[ProxyRequestContext]:
    """Bind one FastMCP request context to proxy work for its active lifetime."""
    request_context = context.request_context
    if request_context is None:
        raise RuntimeError("Proxy request binding requires an active MCP request")
    binding = ProxyRequestContext(
        session=request_context.session,
        request_id=request_context.request_id,
    )
    token = _CURRENT_PROXY_REQUEST.set(binding)
    try:
        yield binding
    finally:
        binding.expire()
        _CURRENT_PROXY_REQUEST.reset(token)


class ProxyManager:
    """Manages connections to external MCP servers using FastMCP Client.

    Connects to configured MCP servers at startup and provides
    a unified interface for calling their tools.
    """

    def __init__(self) -> None:
        """Initialize the proxy manager."""
        self._clients: dict[str, Client] = {}  # type: ignore[type-arg]
        self._call_locks: dict[str, asyncio.Lock] = {}
        self._active_calls: dict[str, _ProxyCallContext] = {}
        self._tools_by_server: dict[str, list[types.Tool]] = {}
        self._errors: dict[str, str] = {}  # server name -> last error message
        self._server_timeouts: dict[
            str, float
        ] = {}  # server name -> configured timeout
        self._server_instructions: dict[
            str, str
        ] = {}  # server name -> native instructions
        self._initialized = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connect_task: asyncio.Task[None] | None = None
        self._lifecycle_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._mutation_lock = threading.RLock()

    @property
    def servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._clients.keys())

    @property
    def is_connecting(self) -> bool:
        """True if a background connect or reconnect is still in progress."""
        return any(
            task is not None and not task.done()
            for task in (self._connect_task, self._lifecycle_task)
        )

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

    def readiness(
        self, configured_servers: list[str] | tuple[str, ...]
    ) -> dict[str, Any]:
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
        connected = sum(
            1 for state in servers.values() if state["status"] == "connected"
        )
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
        # D15: snapshot _tools_by_server under the mutation lock before iterating so
        # a background connect adding a server mid-scan cannot raise
        # "RuntimeError: dictionary changed size during iteration".
        if server:
            with self._mutation_lock:
                items = [(server, t) for t in self._tools_by_server.get(server, [])]
        else:
            with self._mutation_lock:
                snapshot = list(self._tools_by_server.items())
            items = [(srv, t) for srv, ts in snapshot for t in ts]
        return [
            ProxyToolInfo(
                server=srv,
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema,
            )
            for srv, t in items
        ]

    async def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
        request_context: ProxyRequestContext | None = None,
    ) -> str | dict[str, Any] | list[Any]:
        """Call a tool on a proxied MCP server.

        Args:
            server: Name of the server to call.
            tool: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            timeout: Timeout for the call in seconds.
            request_context: Captured owner of the active root request. Omit for
                detached calls that must not forward interactive input.

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
            call_context = _ProxyCallContext(request=request_context)
            call_lock = self._call_locks.setdefault(server, asyncio.Lock())
            try:
                async with call_lock:
                    self._active_calls[server] = call_context
                    result = await asyncio.wait_for(
                        client.call_tool(
                            tool,
                            arguments,
                            raise_on_error=False,
                        ),
                        timeout=timeout,
                    )
            except TimeoutError:
                logger.error(
                    LogEntry(
                        event="proxy.tool.timeout",
                        server=server,
                        tool=tool,
                        timeout=timeout,
                    ).failure(
                        error_type="TimeoutError",
                        error_message="proxy tool call timed out",
                    )
                )
                raise TimeoutError(
                    f"Tool {server}.{tool} timed out after {timeout}s"
                ) from None
            finally:
                call_context.expire()
                if self._active_calls.get(server) is call_context:
                    self._active_calls.pop(server, None)

            # Extract and auto-parse text from result
            text_parts: list[str] = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    text_parts.append(content.text)
                elif isinstance(content, types.EmbeddedResource):
                    # D12: surface embedded-resource payloads (common for
                    # document/file-oriented servers) instead of silently dropping
                    # them and reporting an empty response.
                    resource = content.resource
                    resource_text = getattr(resource, "text", None)
                    if resource_text is not None:
                        text_parts.append(resource_text)
                    else:
                        marker = (
                            getattr(resource, "uri", None) or type(resource).__name__
                        )
                        text_parts.append(f"[Binary resource: {marker}]")
                elif hasattr(content, "data"):
                    text_parts.append(f"[Binary content: {type(content).__name__}]")

            result_value: str | dict[str, Any] | list[Any]
            if not text_parts:
                # D12: fall back to a structured payload before declaring the
                # response empty.
                structured = getattr(result, "structured_content", None)
                if structured is None:
                    structured = getattr(result, "data", None)
                result_value = (
                    structured
                    if structured is not None
                    else "Tool returned empty response."
                )
            elif len(text_parts) == 1:
                # D13: only coerce text that structurally looks like JSON (an object
                # or array). A plain-string answer such as "007" or "true" must pass
                # through unchanged rather than being force-parsed to a different type.
                single = text_parts[0]
                if single.strip()[:1] in ("{", "["):
                    try:
                        result_value = json.loads(single)
                    except (json.JSONDecodeError, ValueError):
                        result_value = single
                else:
                    result_value = single
            else:
                # Multi-part: concatenate as string
                result_value = "\n".join(text_parts)

            if getattr(result, "is_error", False) is True:
                error_text = str(result_value)
                reason = call_context.elicitation_unavailable_reason
                if reason:
                    error_text = (
                        f"{error_text}\nInteractive input {reason}. "
                        "Retry with all required tool arguments explicitly."
                    )
                raise RuntimeError(error_text)

            span.add("resultLength", len(str(result_value)))
            return result_value

    async def _forward_elicitation(
        self,
        server: str,
        message: str,
        _response_type: type[Any] | None,
        params: ElicitRequestParams,
        _context: Any,
    ) -> ElicitResult[Any]:
        """Forward one upstream elicitation through its exact active proxy call."""
        call_context = self._active_calls.get(server)
        if call_context is None or not call_context.is_active:
            return ElicitResult(action="cancel")
        binding = call_context.request
        if binding is None:
            return ElicitResult(action="cancel")
        if not binding.is_active:
            call_context.record_elicitation_unavailable(
                "was requested after the originating request completed"
            )
            return ElicitResult(action="cancel")

        client_params = binding.session.client_params

        capabilities = client_params.capabilities if client_params is not None else None
        elicitation = capabilities.elicitation if capabilities is not None else None

        if isinstance(params, types.ElicitRequestFormParams):
            # The MCP compatibility rule treats an empty elicitation capability
            # as form support. A URL-only declaration does not imply form support.
            supported = elicitation is not None and (
                elicitation.form is not None or elicitation.url is None
            )
            mode = "form"
        else:
            supported = elicitation is not None and elicitation.url is not None
            mode = "URL"

        if not supported:
            call_context.record_elicitation_unavailable(
                f"could not be forwarded because the client does not support {mode} elicitation"
            )
            return ElicitResult(action="cancel")

        try:
            if isinstance(params, types.ElicitRequestFormParams):
                result = await binding.session.elicit_form(
                    message=message,
                    requestedSchema=params.requestedSchema,
                    related_request_id=binding.request_id,
                )
            else:
                result = await binding.session.elicit_url(
                    message=message,
                    url=str(params.url),
                    elicitation_id=params.elicitationId,
                    related_request_id=binding.request_id,
                )
        except Exception as exc:
            call_context.record_elicitation_unavailable(
                f"could not be forwarded: {type(exc).__name__}: {exc}"
            )
            return ElicitResult(action="cancel")

        if result.action != "accept":
            call_context.record_elicitation_unavailable(
                f"ended with a {result.action} response"
            )
        return ElicitResult(
            _meta=result.meta,
            action=result.action,
            content=result.content,
        )

    def _elicitation_handler_for(self, server: str) -> ElicitationHandler:
        """Create a handler permanently associated with one upstream server."""

        async def handler(
            message: str,
            response_type: type[Any] | None,
            params: ElicitRequestParams,
            context: Any,
        ) -> ElicitResult[Any]:
            return await self._forward_elicitation(
                server,
                message,
                response_type,
                params,
                context,
            )

        return handler

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
                self.call_tool(
                    server,
                    tool,
                    arguments,
                    timeout,
                    request_context=None,
                ),
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

        request_context = _CURRENT_PROXY_REQUEST.get()
        future = asyncio.run_coroutine_threadsafe(
            self.call_tool(
                server,
                tool,
                arguments,
                timeout,
                request_context=request_context,
            ),
            self._loop,
        )
        try:
            return future.result(timeout=timeout + 5)
        except concurrent.futures.TimeoutError:
            # D-c1: cancel the scheduled coroutine so it does not keep running on the
            # event loop after the caller has already received a timeout (leaked work).
            future.cancel()
            raise

    def list_resources_sync(
        self, server: str, timeout: float = 5.0
    ) -> list[dict[str, Any]]:
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
        future = asyncio.run_coroutine_threadsafe(
            self.list_resources(server), self._loop
        )
        return future.result(timeout=timeout)

    def list_prompts_sync(
        self, server: str, timeout: float = 5.0
    ) -> list[dict[str, Any]]:
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
            return [
                {"uri": r.uri, "name": r.name, "description": r.description or ""}
                for r in resources
            ]
        except (AttributeError, NotImplementedError):
            # Server doesn't support resources
            return []
        except Exception as e:
            # Check if error indicates unsupported feature
            error_msg = str(e).lower()
            if any(
                x in error_msg
                for x in ["not found", "not supported", "not implemented"]
            ):
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
            return [
                {"name": p.name, "description": p.description or ""} for p in prompts
            ]
        except (AttributeError, NotImplementedError):
            # Server doesn't support prompts
            return []
        except Exception as e:
            # Check if error indicates unsupported feature
            error_msg = str(e).lower()
            if any(
                x in error_msg
                for x in ["not found", "not supported", "not implemented"]
            ):
                return []
            raise

    async def get_prompt(
        self, server: str, name: str, arguments: dict[str, Any] | None = None
    ) -> str:
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
                        self._errors[name] = _sanitize_connect_error(str(e))
                        logger.warning(
                            LogEntry(event="proxy.connect.failed", server=name).failure(
                                e
                            )
                        )
                        return False

                connection_tasks = [
                    asyncio.create_task(connect_one(name, config))
                    for name, config in enabled_configs.items()
                ]
                try:
                    results = await asyncio.gather(*connection_tasks)
                except asyncio.CancelledError:
                    for task in connection_tasks:
                        task.cancel()
                    await asyncio.gather(*connection_tasks, return_exceptions=True)
                    raise
                connected = sum(1 for result in results if result)
                failed = len(results) - connected

                span.add("connected", connected)
                span.add("failed", failed)
                span.add("toolCount", self.tool_count)
        except asyncio.CancelledError:
            self._initialized = False
            raise
        else:
            self._initialized = True

    def connect_background(
        self, configs: dict[str, McpServerConfig]
    ) -> asyncio.Task[None]:
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
                from ot.proxy.oauth import create_oauth_token_storage

                auth = OAuth(
                    mcp_url=url,
                    scopes=config.auth.scopes or [],
                    client_name="OneTool",
                    token_storage=create_oauth_token_storage(),
                    additional_client_metadata={"token_endpoint_auth_method": "none"},
                )
                logger.debug(
                    f"Configured OAuth for {name} with scopes: {config.auth.scopes}"
                )
            else:  # bearer
                token = expand_vars(config.auth.token) if config.auth.token else ""
                auth = BearerAuth(token)
                logger.debug(f"Configured bearer auth for {name}")

        transport = StreamableHttpTransport(
            url=url, headers=headers if headers else None, auth=auth
        )
        return Client(
            transport,
            timeout=float(config.timeout),
            elicitation_handler=self._elicitation_handler_for(name),
        )

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

        return Client(
            transport,
            timeout=float(config.timeout),
            elicitation_handler=self._elicitation_handler_for(name),
        )

    def _reset_state(self) -> None:
        """Reset all connection state without disconnecting (for cases where loop is unavailable)."""
        with self._mutation_lock:
            self._clients.clear()
            self._call_locks.clear()
            self._active_calls.clear()
            self._tools_by_server.clear()
            self._errors.clear()
            self._server_timeouts.clear()
            self._server_instructions.clear()
            self._initialized = False
            self._connect_task = None
            self._lifecycle_task = None

    async def _close_client_transport(self, client: Client) -> None:  # type: ignore[type-arg]
        """Close the underlying transport when FastMCP exposes an async close hook."""
        transport = getattr(client, "transport", None)
        if transport is not None and hasattr(transport, "close"):
            await transport.close()

    async def _shutdown_unlocked(self) -> None:
        """Disconnect after the caller serializes the lifecycle transition."""
        # Cancel background connect task if still running
        connect_task = self._connect_task
        if connect_task is not None and not connect_task.done():
            connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connect_task
        if self._connect_task is connect_task:
            self._connect_task = None

        clients = list(self._clients.items())
        if clients:
            with LogSpan(span="proxy.shutdown", serverCount=len(clients)):
                for name, client in clients:
                    try:
                        await client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
                        # transport.close() terminates stdio subprocesses left alive
                        # by FastMCP keep_alive after __aexit__ exits the session.
                        await self._close_client_transport(client)
                        logger.debug(f"Disconnected from MCP server '{name}'")
                    except (Exception, asyncio.CancelledError) as e:
                        logger.debug(f"Error disconnecting from '{name}': {e}")

        with self._mutation_lock:
            self._clients.clear()
            self._call_locks.clear()
            self._active_calls.clear()
            self._tools_by_server.clear()
            self._errors.clear()
            self._server_timeouts.clear()
            self._server_instructions.clear()
            self._initialized = False

    async def shutdown(self) -> None:
        """Serialize shutdown and leave every connection state reconnectable."""
        async with self._lifecycle_lock:
            await self._shutdown_unlocked()

    def _finish_lifecycle_task(self, task: asyncio.Task[None]) -> None:
        """Observe background reconnect failures and clear readiness state."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(LogEntry(event="proxy.reconnect.failed").failure(e))
        finally:
            if self._lifecycle_task is task:
                self._lifecycle_task = None

    def _start_background_reconnect(
        self,
        loop: asyncio.AbstractEventLoop,
        configs: dict[str, McpServerConfig],
    ) -> None:
        """Schedule same-loop reconnect while preserving the immediate return."""
        task = loop.create_task(self.reconnect(configs))
        self._lifecycle_task = task
        task.add_done_callback(self._finish_lifecycle_task)

    def _evict_proxy_caches(self, name: str | None) -> None:
        """Evict per-server proxy resolution caches so a restart binds to the new schema.

        D14: both the pack-proxy namespace cache (accessor -> tool closures) and the
        MCP param-name cache key on server identity but are not otherwise invalidated
        on a disconnect/restart. ``name=None`` clears everything (full reconnect).

        The namespace-cache eviction below is deliberately global regardless of
        ``name``: the namespace cache is a single composite dict shared by packs for
        all servers, so a full rebuild is the only correct option and is cheap (D14,
        p12). Per-server eviction was considered and rejected for this cache; contrast
        with ``evict_mcp_param_cache`` above, which does real per-server eviction.
        """
        from ot.executor.pack_proxy import reset
        from ot.executor.param_resolver import evict_mcp_param_cache

        evict_mcp_param_cache(name)
        reset()

    async def reconnect(self, configs: dict[str, McpServerConfig]) -> None:
        """Serialize full cleanup before connecting a fresh configuration."""
        async with self._lifecycle_lock:
            await self._shutdown_unlocked()
            await self.connect(configs)
            # D14: schemas may have changed across the restart — drop all cached
            # proxy resolutions so later calls bind against the fresh tool lists.
            self._evict_proxy_caches(None)

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
            # D14: drop any stale cached resolutions for this server name (e.g. from a
            # prior connection whose schema differed) so calls bind to the new tools.
            self._evict_proxy_caches(name)
            return f"ok ({tool_count} tools)"
        except Exception as e:
            with self._mutation_lock:
                self._errors[name] = _sanitize_connect_error(str(e))
            logger.warning(
                LogEntry(event="proxy.connect.failed", server=name).failure(e)
            )
            return f"failed: {e}"

    def _schedule_or_wait(self, coro: Coroutine[Any, Any, str], timeout: float) -> str:
        """Run ``coro`` on the manager's loop, guarding against a same-loop deadlock.

        D3: if called from code already running on the manager's own loop, a blocking
        ``future.result()`` onto that same loop can never complete (the scheduled
        coroutine cannot run until this call returns) — a multi-second freeze. In that
        case, schedule fire-and-continue instead. Otherwise (called from another
        thread), hop onto the manager's loop via ``run_coroutine_threadsafe`` and
        block up to ``timeout`` seconds for the result.
        """
        with contextlib.suppress(RuntimeError):
            if asyncio.get_running_loop() is self._loop:
                self._loop.create_task(coro)
                return "scheduled"
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)  # type: ignore[arg-type]
        return future.result(timeout=timeout)

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
        return self._schedule_or_wait(
            self.connect_additional(name, config), timeout=120
        )

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
            self._call_locks.pop(name, None)
            self._active_calls.pop(name, None)
            self._tools_by_server.pop(name, None)
            self._errors.pop(name, None)
            self._server_instructions.pop(name, None)
            self._server_timeouts.pop(name, None)
        # D14: drop cached proxy/param resolutions for this server so a later reconnect
        # of the same name cannot serve stale pre-disconnect tool/param bindings.
        self._evict_proxy_caches(name)
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
                self._call_locks.pop(name, None)
                self._active_calls.pop(name, None)
                self._tools_by_server.pop(name, None)
                self._errors.pop(name, None)
                self._server_instructions.pop(name, None)
                self._server_timeouts.pop(name, None)
                logger.warning(
                    f"Removed server '{name}' without async cleanup — "
                    "no running event loop; underlying transport may not be closed."
                )
                return "disconnected"
        return self._schedule_or_wait(self.disconnect_server(name), timeout=30)

    def reconnect_sync(self, configs: dict[str, McpServerConfig]) -> None:
        """Synchronously reconnect to all MCP servers.

        Cross-thread callers block for completion. Same-loop callers retain the
        immediate reload contract while a serialized background reconnect drives
        readiness to its eventual connected or failed state.

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
                self._start_background_reconnect(loop, configs)
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
