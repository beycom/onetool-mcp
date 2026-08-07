"""FastMCP server implementation with a single 'run' tool.

The agent passes Python code to run(command=...):
  context7.search(query="next.js")
  context7.doc(library_key="vercel/next.js", topic="routing")

Or Python code blocks:
  ```python
  metals = ["Gold", "Silver", "Bronze"]
  results = {}
  for metal in metals:
      results[metal] = brave.web_search(query=f"{metal} price", count=3)
  return results
  ```

Supported explicit prefixes stripped from command text: __onetool, __ot.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from loguru import logger

from ot.config.loader import get_config
from ot.executor import SimpleExecutor, execute_command
from ot.executor.runner import prepare_command
from ot.logging import LogEntry, LogSpan, configure_logging
from ot.logging.mcp_logging import (
    map_mcp_logging_level,
    register_set_logging_level_handler,
)
from ot.prompts import get_prompts, get_tool_description, get_tool_examples
from ot.proxy import bind_proxy_request_context, get_proxy_manager
from ot.registry import get_registry
from ot.stats import (
    JsonlStatsWriter,
    get_client_name,
    set_stats_writer,
)
from ot.support import get_startup_message
from ot.utils import sanitize_output

_config = get_config()

# Initialize logging to serve.log
configure_logging(log_name="serve")

# Global stats writer (unified JSONL for both run and tool stats)
_stats_writer: JsonlStatsWriter | None = None
_direct_api_server: Any | None = None
_direct_api_thread: threading.Thread | None = None
_direct_api_port: int | None = None
_root_runtime: RootRuntime | None = None


@dataclass(frozen=True)
class RootRuntime:
    """Root MCP transport settings for lifecycle logs."""

    transport: str
    host: str | None = None
    port: int | None = None
    path: str | None = None

    @property
    def url(self) -> str | None:
        """Return the client URL for HTTP root mode."""
        if self.transport != "streamable-http":
            return None
        return f"http://{self.host}:{self.port}{self.path}"


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def validate_http_root_options(*, host: str, port: int, path: str) -> None:
    """Validate Streamable HTTP root options before server startup."""
    if not host or host.strip() != host:
        raise ValueError("--host must be a non-empty hostname or IP address")
    if port < 1 or port > 65535:
        raise ValueError("--port must be between 1 and 65535")
    if not path.startswith("/"):
        raise ValueError("--path must start with '/'")
    if "?" in path or "#" in path or any(ch.isspace() for ch in path):
        raise ValueError(
            "--path must be a URL path without whitespace, query, or fragment"
        )


def _direct_health_probe_once(host: str, port: int, timeout_secs: float = 0.2) -> bool:
    import urllib.request

    from ot.direct_auth import HEALTH_PATH, signed_headers, verify_response

    try:
        req = urllib.request.Request(
            f"http://{host}:{port}{HEALTH_PATH}",
            headers=signed_headers(method="GET", path=HEALTH_PATH, body=b""),
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
            body = resp.read()
            verify_response(
                path=HEALTH_PATH,
                body=body,
                headers=dict(resp.headers),
                status_code=resp.status,
            )
            payload: dict[str, Any] = json.loads(body.decode("utf-8"))
            healthy = payload.get("status") == "ok"
            logger.debug(
                LogEntry(event="direct.api.health_probe", port=port, healthy=healthy)
            )
            return healthy
    except Exception as e:
        logger.debug(
            LogEntry(event="direct.api.health_probe", port=port, healthy=False).failure(
                e
            )
        )
        return False


def _tcp_port_bound(host: str, port: int, timeout_secs: float = 0.1) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_secs):
            logger.debug(LogEntry(event="direct.api.port_bound", port=port, bound=True))
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        logger.debug(LogEntry(event="direct.api.port_bound", port=port, bound=False))
        return False


def _direct_candidate_ports() -> list[int]:
    start = _config.direct.host.port
    return list(range(start, 65536))


def _start_direct_api() -> tuple[Any, threading.Thread, int]:
    """Start the MCP-owned direct API in a background thread."""
    import uvicorn

    from ot.direct_api import create_app

    logger.debug(
        LogEntry(
            event="direct.api.start.begin",
            configuredPort=_config.direct.host.port,
            candidateCount=65536 - _config.direct.host.port,
        )
    )
    for port in _direct_candidate_ports():
        if _tcp_port_bound("127.0.0.1", port):
            logger.debug(LogEntry(event="direct.api.port.occupied_skipped", port=port))
            continue

        logger.debug(LogEntry(event="direct.api.candidate", port=port))
        config = uvicorn.Config(
            create_app(),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
            # F4: suppress uvicorn's default dictConfig, which installs a
            # StreamHandler(stdout) on uvicorn.access. This process shares fd 1 with
            # the stdio JSON-RPC stream; if the log level were ever lowered, access
            # lines on stdout would corrupt it. loguru's InterceptHandler already
            # covers uvicorn's loggers, so no records are lost.
            log_config=None,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(
            target=server.run, name=f"onetool-direct-{port}", daemon=True
        )
        thread.start()

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if server.started and _direct_health_probe_once("127.0.0.1", port):
                logger.info(
                    LogEntry(
                        event="direct.api.ready",
                        port=port,
                        baseUrl=f"http://127.0.0.1:{port}",
                    ).success()
                )
                return server, thread, port
            if not thread.is_alive():
                break
            time.sleep(0.05)

        server.should_exit = True
        thread.join(timeout=1.0)
        logger.error("direct.api.bind_failed | port={}", port)

    start_port = _config.direct.host.port
    logger.error("direct.api.failed | configuredPorts={}..65535", start_port)
    raise RuntimeError(
        f"Could not start MCP direct API in configured ports {start_port}..65535"
    )


def _stop_direct_api(server: Any, thread: threading.Thread, port: int) -> None:
    """Stop the embedded direct API listener."""
    logger.debug(LogEntry(event="direct.api.stop.begin", port=port))
    server.should_exit = True
    thread.join(timeout=5.0)
    logger.info(LogEntry(event="direct.api.stop.done", port=port).success())


def _get_instructions() -> str:
    """Return the connection-time MCP server instructions.

    Note: Tool descriptions are NOT included here - they come through
    the MCP tool definitions which the client converts to function calling format.
    The pack list is delivered by the ot-ref skill, not inlined here.
    """
    prompts = get_prompts(inline_prompts=_config.prompts)
    return prompts.instructions.strip()


def _log_startup_diagnostics(
    *,
    tool_count: int,
    proxy_count: int,
    direct_status: str,
    direct_port: int | None,
) -> None:
    """Log concise startup diagnostics for support and debugging."""
    from ot.config.loader import get_loaded_config_path
    from ot.meta._debug import _get_prompts_info

    cfg = _config
    config_path = get_loaded_config_path()
    prompts_info = _get_prompts_info()
    logger.info(
        LogEntry(
            event="mcp.startup.diagnostics",
            transport="stdio",
            configDir=cfg._config_dir,
            configFile=config_path,
            includeCount=len(cfg.include),
            logPath=cfg.get_log_dir_path() / "serve.log",
            statsEnabled=cfg.stats.enabled,
            statsPath=cfg.get_stats_file_path(),
            registryToolCount=tool_count,
            proxyConfigured=proxy_count,
            proxyBackground=bool(proxy_count),
            directConfigured=cfg.direct.host.enabled,
            directStatus=direct_status,
            directPort=direct_port,
            promptSource=prompts_info.get("source"),
            promptPath=prompts_info.get("path"),
            promptHash=prompts_info.get("sha256"),
            statusTool="ot.status",
        )
    )


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle - startup and shutdown."""
    global _stats_writer, _direct_api_server, _direct_api_thread, _direct_api_port

    runtime = _root_runtime or RootRuntime(transport="stdio")
    from ot.executor.admission import start_execution_admission

    start_execution_admission()

    with LogSpan(span="mcp.server.start", transport=runtime.transport) as start_span:
        start_time = time.monotonic()
        from ot.console.storage import initialize_console_storage
        from ot.runtime_meta import get_or_create_instance_id

        initialize_console_storage(instance_id=get_or_create_instance_id())
        if runtime.transport == "streamable-http":
            start_span.add(
                host=runtime.host,
                port=runtime.port,
                path=runtime.path,
                url=runtime.url,
            )
            if runtime.host and not _is_loopback_host(runtime.host):
                logger.warning(
                    "mcp.http_root.non_loopback_bind | host={} | port={} | path={} | url={}",
                    runtime.host,
                    runtime.port,
                    runtime.path,
                    runtime.url,
                )
        # Startup: connect to proxy MCP servers in the background so FastMCP
        # can begin handling MCP protocol messages immediately.
        proxy = get_proxy_manager()
        proxy.bind_runtime_loop()
        enabled_servers = {
            name: config for name, config in _config.servers.items() if config.enabled
        }
        if enabled_servers:
            proxy.connect_background(enabled_servers)
            start_span.add("proxyCount", len(enabled_servers))

        # Log tool count from registry
        registry = get_registry()
        start_span.add("toolCount", len(registry.tools))

        # Pre-warm tool registry so the first run() call is served from a warm cache
        from ot.executor.tool_loader import load_tool_registry

        load_tool_registry()

        # Direct API mode: bind one local HTTP listener owned by this MCP process.
        direct_status = "disabled"
        if _config.direct.host.enabled:
            from ot.direct_discovery import (
                sweep_stale_discovery_files,
                write_discovery_file,
            )
            from ot.runtime_meta import get_or_create_instance_id, set_direct_api

            sweep_stale_discovery_files()
            try:
                api_server, api_thread, api_port = _start_direct_api()
                _direct_api_server = api_server
                _direct_api_thread = api_thread
                _direct_api_port = api_port
                start_span.add("directApi", f"http://127.0.0.1:{api_port}")
                direct_status = "ready"

                base_url = f"http://127.0.0.1:{api_port}"
                set_direct_api(base_url=base_url, port=api_port)
                write_discovery_file(
                    instance_id=get_or_create_instance_id(), port=api_port
                )
            except Exception as e:
                logger.error(LogEntry(event="direct.api.degraded").failure(e))
                start_span.add("directApi", "degraded")
                start_span.add("directApiError", str(e))
                direct_status = "degraded"
        else:
            logger.debug(
                LogEntry(event="direct.api.disabled", rootTransport=runtime.transport)
            )

        # Fire anonymous startup telemetry (non-blocking daemon thread)
        from ot.telemetry import ping as _telemetry_ping

        _telemetry_ping()

        # Startup: initialize unified JSONL stats writer if enabled
        if _config.stats.enabled:
            stats_path = _config.get_stats_file_path()
            flush_interval = _config.stats.flush_interval_seconds

            _stats_writer = JsonlStatsWriter(
                path=stats_path,
                flush_interval=flush_interval,
            )
            await _stats_writer.start()
            set_stats_writer(_stats_writer)

            start_span.add("statsEnabled", True)
            start_span.add("statsPath", str(stats_path))

        _log_startup_diagnostics(
            tool_count=len(registry.tools),
            proxy_count=len(enabled_servers),
            direct_status=direct_status,
            direct_port=_direct_api_port,
        )

        # Log support message
        logger.info(
            LogEntry(event="mcp.support_message", message=get_startup_message())
        )

    yield

    with LogSpan(span="mcp.server.stop", transport=runtime.transport) as stop_span:
        stop_span.add(duration=round(time.monotonic() - start_time, 3))
        if (
            _direct_api_server is not None
            and _direct_api_thread is not None
            and _direct_api_port is not None
        ):
            _stop_direct_api(_direct_api_server, _direct_api_thread, _direct_api_port)
            stop_span.add("directApiStopped", f"127.0.0.1:{_direct_api_port}")

            from ot.direct_discovery import remove_discovery_file
            from ot.runtime_meta import get_or_create_instance_id

            remove_discovery_file(instance_id=get_or_create_instance_id())
        _direct_api_server = None
        _direct_api_thread = None
        _direct_api_port = None

        from ot.executor.admission import shutdown_execution_admission

        await shutdown_execution_admission()
        stop_span.add("executionAdmissionStopped", True)

        from ot.console.storage import cleanup_console_instance
        from ot.runtime_meta import get_or_create_instance_id

        cleanup_console_instance(instance_id=get_or_create_instance_id())

        # Shutdown: stop stats writer
        if _stats_writer is not None:
            await _stats_writer.stop()
            set_stats_writer(None)
            stop_span.add("statsStopped", True)

        # Shutdown: disconnect from proxy MCP servers (cancels background task if still running)
        if proxy.servers or proxy.is_connecting:
            count = len(proxy.servers)
            with LogSpan(span="server.shutdown.proxy", serverCount=count):
                await proxy.shutdown()
            stop_span.add("proxyCount", count)


mcp = FastMCP(
    name="ot",
    instructions=_get_instructions(),
    lifespan=_lifespan,
)


# =============================================================================
# MCP Logging - Dynamic log level control
# =============================================================================


async def handle_set_logging_level(level: str) -> None:
    """Handle logging/setLevel requests from MCP clients.

    Allows clients to dynamically change the server's log level.
    """
    log_level = map_mcp_logging_level(level)
    logger.info(f"Log level change requested: {level} -> {log_level}")

    # Reconfigure logging with new level
    configure_logging(log_name="serve", level=log_level)
    logger.info(f"Logging reconfigured at level {log_level}")


register_set_logging_level_handler(mcp, handle_set_logging_level)


# =============================================================================
# MCP Resources - Tool discoverability
# =============================================================================


@mcp.resource("ot://tools")
def list_tools_resource() -> list[dict[str, str]]:
    """List all available tools with signatures and descriptions."""
    registry = get_registry()
    prompts = get_prompts(inline_prompts=_config.prompts)

    tools_list = []

    # Add local tools
    for tool in registry.tools.values():
        desc = get_tool_description(prompts, tool.name, tool.description)
        tools_list.append(
            {
                "name": tool.name,
                "signature": tool.signature,
                "description": desc,
            }
        )

    # Add proxied tools
    proxy = get_proxy_manager()
    for proxy_tool in proxy.list_tools():
        tools_list.append(
            {
                "name": f"{proxy_tool.server}.{proxy_tool.name}",
                "signature": f"{proxy_tool.server}.{proxy_tool.name}(...)",
                "description": f"[proxy] {proxy_tool.description}",
            }
        )

    return tools_list


@mcp.resource("ot://tool/{name}")
def get_tool_resource(name: str) -> dict[str, Any]:
    """Get detailed information about a specific tool."""
    registry = get_registry()
    prompts = get_prompts(inline_prompts=_config.prompts)

    tool = registry.tools.get(name)
    if not tool:
        return {"error": f"Tool '{name}' not found"}

    desc = get_tool_description(prompts, tool.name, tool.description)
    examples = get_tool_examples(prompts, tool.name)

    return {
        "name": tool.name,
        "module": tool.module,
        "signature": tool.signature,
        "description": desc,
        "args": [
            {
                "name": arg.name,
                "type": arg.type,
                "default": arg.default,
                "description": arg.description,
            }
            for arg in tool.args
        ],
        "returns": tool.returns,
        "examples": examples or tool.examples,
        "tags": tool.tags,
        "enabled": tool.enabled,
        "deprecated": tool.deprecated,
        "deprecated_message": tool.deprecated_message,
    }


# Global executor instance
_executor: SimpleExecutor | None = None


def _get_executor() -> SimpleExecutor:
    """Get or create the executor."""
    global _executor

    if _executor is None:
        _executor = SimpleExecutor()

    return _executor


def _get_run_description() -> str:
    """Get run tool description from prompts config.

    Raises:
        ValueError: If run tool description not found in prompts.yaml
    """
    prompts = get_prompts(inline_prompts=_config.prompts)
    desc = get_tool_description(prompts, "run", "")
    if not desc:
        raise ValueError("Missing 'run' tool description in prompts.yaml")
    return desc


@mcp.tool(
    description=_get_run_description(),
    annotations={
        "title": "🧿",
        "readOnlyHint": False,
        # A single meta-tool surface that can call file.delete (and anything else in
        # the catalog) is, conservatively, destructive-capable. A client gating a
        # confirmation on this hint must not skip it.
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def run(command: str, ctx: Context) -> ToolResult:
    # Record start time for stats
    start_time = time.monotonic()

    # Step 1: Prepare and validate command. D1: any unanticipated exception during
    # preparation becomes a clean ToolError instead of escaping the tool handler
    # uncaught; D2: a validation error surfaces as isError:true.
    try:
        prepared = prepare_command(command)
    except Exception as e:
        raise ToolError(
            f"Error: command preparation failed: {type(e).__name__}: {e}"
        ) from e

    if prepared.error:
        return ToolResult(content=f"Error: {prepared.error}", is_error=True)

    # Step 2: Execute through unified runner (skip validation since already done)
    with bind_proxy_request_context(ctx):
        result = await execute_command(
            command,
            prepared_code=prepared.code,
            skip_validation=True,
        )

    # Record run-level stats if enabled
    if _stats_writer is not None:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        _stats_writer.record_run(
            client=get_client_name(),
            chars_in=len(command),
            chars_out=len(result.result),
            duration_ms=duration_ms,
            success=result.success,
            error_type=result.error_type,
        )

    # Return ToolResult with content only — prevents FastMCP from auto-generating
    # structuredContent (which Claude Code prefers over content text)
    text = sanitize_output(
        result.result, enabled=result.should_sanitize, fmt=result.format
    )
    return ToolResult(content=text, is_error=not result.success)


def main() -> None:
    """Run the MCP server over stdio transport."""
    run_root_server()


def run_root_server(
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8767,
    path: str = "/mcp",
) -> None:
    """Run the shared root MCP server over stdio or Streamable HTTP."""
    global _root_runtime

    if transport == "stdio":
        _root_runtime = RootRuntime(transport="stdio")
        mcp.run(transport="stdio", show_banner=False)
        return

    if transport == "streamable-http":
        validate_http_root_options(host=host, port=port, path=path)
        _root_runtime = RootRuntime(
            transport="streamable-http",
            host=host,
            port=port,
            path=path,
        )
        logger.info(
            LogEntry(
                event="mcp.http_root.start",
                host=host,
                port=port,
                path=path,
                url=f"http://{host}:{port}{path}",
            )
        )
        mcp.run(
            transport="streamable-http",
            show_banner=False,
            host=host,
            port=port,
            path=path,
        )
        return

    raise ValueError(f"Unsupported root MCP transport: {transport}")
