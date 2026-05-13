"""FastMCP server implementation with a single 'run' tool.

The agent generates function call syntax with >>> prefix:
  >>> context7.search(query="next.js")
  >>> context7.doc(library_key="vercel/next.js", topic="routing")

Or Python code blocks:
  >>>
  ```python
  metals = ["Gold", "Silver", "Bronze"]
  results = {}
  for metal in metals:
      results[metal] = brave.web_search(query=f"{metal} price", count=3)
  return results
  ```

Or direct MCP calls:
  mcp__onetool__run(command='brave.web_search(query="test")')

Supported prefixes: >>>, __run, mcp__onetool__run
Legacy (backward compat, not advertised): __ot, __ot__run, __onetool, __onetool__run
Note: mcp__ot__run is NOT valid.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from loguru import logger

from ot.config.loader import get_config
from ot.executor import SimpleExecutor, execute_command
from ot.executor.runner import prepare_command
from ot.logging import LogSpan, configure_logging
from ot.logging.mcp_logging import (
    map_mcp_logging_level,
    register_set_logging_level_handler,
)
from ot.prompts import get_prompts, get_tool_description, get_tool_examples
from ot.proxy import get_proxy_manager
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
            logger.info("direct.api.health_probe | port={} | healthy={}", port, healthy)
            return healthy
    except Exception as e:
        logger.info("direct.api.health_probe | port={} | healthy=False | error={}", port, e)
        return False


def _tcp_port_bound(host: str, port: int, timeout_secs: float = 0.1) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_secs):
            logger.info("direct.api.port_bound | port={} | bound=True", port)
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        logger.info("direct.api.port_bound | port={} | bound=False", port)
        return False


def _direct_candidate_ports() -> list[int]:
    start = _config.direct.host.port
    return list(range(start, 65536))


def _start_direct_api() -> tuple[Any, threading.Thread, int]:
    """Start the MCP-owned direct API in a background thread."""
    import uvicorn

    from ot.direct_api import create_app

    logger.info(
        "direct.api.start.begin | configuredPort={} | candidateCount={}",
        _config.direct.host.port,
        65536 - _config.direct.host.port,
    )
    for port in _direct_candidate_ports():
        if _tcp_port_bound("127.0.0.1", port):
            logger.info("direct.api.port.occupied_skipped | port={}", port)
            continue

        logger.info("direct.api.candidate | port={}", port)
        config = uvicorn.Config(
            create_app(),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name=f"onetool-direct-{port}", daemon=True)
        thread.start()

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if server.started and _direct_health_probe_once("127.0.0.1", port):
                logger.info(
                    "direct.api.ready | port={} | baseUrl=http://127.0.0.1:{}",
                    port,
                    port,
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
    raise RuntimeError(f"Could not start MCP direct API in configured ports {start_port}..65535")


def _stop_direct_api(server: Any, thread: threading.Thread, port: int) -> None:
    """Stop the embedded direct API listener."""
    logger.info("direct.api.stop.begin | port={}", port)
    server.should_exit = True
    thread.join(timeout=5.0)
    logger.info("direct.api.stop.done | port={}", port)


def _build_pack_summary() -> str:
    """Build a pack summary string from installed packs for injection into instructions."""
    try:
        from ot.meta._discovery import packs as _packs
        pack_list = _packs(info="default")
        lines = []
        for pack in pack_list:
            if isinstance(pack, dict):
                name = pack.get("name", "")
                desc = pack.get("description", "")
                if desc and desc != "(no description)":
                    lines.append(f"- **{name}**: {desc}")
                else:
                    lines.append(f"- **{name}**")
        return "\n".join(lines)
    except Exception:
        return "(pack list unavailable)"


def _get_instructions() -> str:
    """Generate MCP server instructions with dynamic pack summary.

    Note: Tool descriptions are NOT included here - they come through
    the MCP tool definitions which the client converts to function calling format.
    """
    prompts = get_prompts(inline_prompts=_config.prompts)
    instructions = prompts.instructions
    if "{pack_summary}" in instructions:
        pack_summary = _build_pack_summary()
        instructions = instructions.replace("{pack_summary}", pack_summary)
    return instructions.strip()


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle - startup and shutdown."""
    global _stats_writer, _direct_api_server, _direct_api_thread, _direct_api_port

    with LogSpan(span="mcp.server.start") as start_span:
        # Startup: connect to proxy MCP servers in the background so FastMCP
        # can begin handling MCP protocol messages immediately.
        proxy = get_proxy_manager()
        if _config.servers:
            proxy.connect_background(_config.servers)
            start_span.add("proxyCount", len(_config.servers))

        # Log tool count from registry
        registry = get_registry()
        start_span.add("toolCount", len(registry.tools))

        # Pre-warm tool registry so the first run() call is served from a warm cache
        from ot.executor.tool_loader import load_tool_registry
        load_tool_registry()

        # Direct API mode: bind one local HTTP listener owned by this MCP process.
        if _config.direct.host.enabled:
            try:
                api_server, api_thread, api_port = _start_direct_api()
                _direct_api_server = api_server
                _direct_api_thread = api_thread
                _direct_api_port = api_port
                start_span.add("directApi", f"http://127.0.0.1:{api_port}")
            except Exception as e:
                logger.error("direct.api.degraded | error={}", e)
                start_span.add("directApi", "degraded")
                start_span.add("directApiError", str(e))
        else:
            logger.info("direct.api.disabled")

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

        # Log support message
        logger.info(get_startup_message())

    yield

    with LogSpan(span="mcp.server.stop") as stop_span:
        if (
            _direct_api_server is not None
            and _direct_api_thread is not None
            and _direct_api_port is not None
        ):
            _stop_direct_api(_direct_api_server, _direct_api_thread, _direct_api_port)
            stop_span.add("directApiStopped", f"127.0.0.1:{_direct_api_port}")
        _direct_api_server = None
        _direct_api_thread = None
        _direct_api_port = None

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
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def run(command: str, ctx: Context) -> ToolResult:  # noqa: ARG001
    # Record start time for stats
    start_time = time.monotonic()

    # Step 1: Prepare and validate command
    prepared = prepare_command(command)

    if prepared.error:
        return ToolResult(content=f"Error: {prepared.error}")

    # Step 2: Execute through unified runner (skip validation since already done)
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
    return ToolResult(content=text)


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(show_banner=False)
