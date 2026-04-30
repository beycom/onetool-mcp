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

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from loguru import logger

from ot.config.loader import get_config, get_loaded_config_path, get_loaded_secrets_path
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
_auto_direct_pid: int | None = None
_auto_direct_port: int | None = None
_auto_direct_owned: bool = False
_AUTO_DIRECT_BOUND_PORT_ENV = "ONETOOL_DIRECT_BOUND_PORT"


def _direct_pid_file(port: int) -> Path:
    return Path.home() / ".onetool" / f"direct-server-{port}.pid"


def _direct_log_file(port: int) -> Path:
    return Path.home() / ".onetool" / f"direct-server-{port}.log"


def _read_direct_pid_file(port: int) -> dict[str, Any] | None:
    try:
        parsed = json.loads(_direct_pid_file(port).read_text())
        if not isinstance(parsed, dict):
            return None
        return {str(k): v for k, v in parsed.items()}
    except Exception:
        return None


def _remove_direct_pid_file(port: int) -> None:
    with contextlib.suppress(FileNotFoundError):
        _direct_pid_file(port).unlink()


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.TerminateProcess(  # type: ignore[attr-defined]
            ctypes.windll.kernel32.OpenProcess(1, False, pid), 0  # type: ignore[attr-defined]
        )
    else:
        os.kill(pid, signal.SIGTERM)


def _tcp_probe_once(host: str, port: int, timeout_secs: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_secs):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _wait_for_direct_host_ready(
    *,
    pid: int,
    host: str,
    port: int,
    timeout_secs: float = 5.0,
    interval: float = 0.1,
) -> bool:
    """Wait for a spawned direct host to accept TCP, failing fast if it exits."""
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        if _tcp_probe_once(host, port):
            return True
        if not _is_process_alive(pid):
            return False
        time.sleep(interval)
    return _tcp_probe_once(host, port)


def _write_direct_pid_file(
    pid: int,
    port: int,
    config_path: Path | None,
    secrets_path: Path | str | None,
) -> None:
    path = _direct_pid_file(port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "pid": pid,
            "port": port,
            "config": str(config_path) if config_path is not None else None,
            "secrets": str(secrets_path) if secrets_path is not None else None,
            "started": time.time(),
            "log": str(_direct_log_file(port)),
        })
    )


def _spawn_direct_host(port: int) -> int:
    config_path = get_loaded_config_path()
    secrets_path = get_loaded_secrets_path()
    if config_path is None:
        raise RuntimeError("No loaded config path available for direct.host.enabled startup")

    log_path = _direct_log_file(port)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "onetool.cli_commands._direct_host_worker"]
    cmd += ["--config", str(config_path), "--port", str(port), "--host", "127.0.0.1"]
    if secrets_path is not None:
        cmd += ["--secrets", str(secrets_path)]

    with log_path.open("a") as log_fh:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=log_fh,
                stderr=log_fh,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=log_fh,
                stderr=log_fh,
            )

    _write_direct_pid_file(proc.pid, port, config_path, secrets_path)
    return proc.pid


def _direct_candidate_ports() -> list[int]:
    start = _config.direct.host.port
    return list(range(start, 65536))


def _start_auto_direct_host() -> tuple[int, int, bool]:
    candidates = _direct_candidate_ports()
    for port in candidates:
        pid_info = _read_direct_pid_file(port)
        if pid_info is not None:
            running_pid = pid_info.get("pid")
            if isinstance(running_pid, int) and _is_process_alive(running_pid):
                continue
            _remove_direct_pid_file(port)

        # Skip ports already in use by unrelated processes.
        if _tcp_probe_once("127.0.0.1", port):
            continue

        pid = _spawn_direct_host(port)
        if _wait_for_direct_host_ready(pid=pid, host="127.0.0.1", port=port):
            return pid, port, True

        with contextlib.suppress(Exception):
            if _is_process_alive(pid):
                _kill_pid(pid)
        _remove_direct_pid_file(port)

    start_port = _config.direct.host.port
    raise RuntimeError(f"Could not start direct host in configured ports {start_port}..65535")


def _stop_auto_direct_host(pid: int, port: int) -> None:
    with contextlib.suppress(Exception):
        if _is_process_alive(pid):
            _kill_pid(pid)
            time.sleep(0.2)

    pid_info = _read_direct_pid_file(port)
    if pid_info is not None and pid_info.get("pid") == pid:
        _remove_direct_pid_file(port)


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
    global _stats_writer, _auto_direct_pid, _auto_direct_port, _auto_direct_owned

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

        # Auto mode: spawn one local direct host bound to this MCP process.
        if _config.direct.host.enabled:
            try:
                auto_pid, auto_port, auto_owned = _start_auto_direct_host()
                _auto_direct_pid = auto_pid
                _auto_direct_port = auto_port
                _auto_direct_owned = auto_owned
                os.environ[_AUTO_DIRECT_BOUND_PORT_ENV] = str(auto_port)
                source = "spawned" if auto_owned else "reused"
                start_span.add("directAutoHost", f"127.0.0.1:{auto_port} ({source})")
            except Exception as e:
                raise RuntimeError(f"direct.host.enabled startup failed: {e}") from e

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
        if _auto_direct_owned and _auto_direct_pid is not None and _auto_direct_port is not None:
            _stop_auto_direct_host(_auto_direct_pid, _auto_direct_port)
            stop_span.add("directAutoHostStopped", f"127.0.0.1:{_auto_direct_port}")
        _auto_direct_pid = None
        _auto_direct_port = None
        _auto_direct_owned = False
        os.environ.pop(_AUTO_DIRECT_BOUND_PORT_ENV, None)

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
