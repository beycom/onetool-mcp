"""FastMCP server implementation with a single 'run' tool.

The LLM generates function call syntax with __ot prefix:
  __ot context7.search(query="next.js")
  __ot context7.doc(library_key="vercel/next.js", topic="routing")
  __ot `demo.upper(text="hello")`

Or Python code blocks:
  __ot
  ```python
  metals = ["Gold", "Silver", "Bronze"]
  results = {}
  for metal in metals:
      results[metal] = brave.web_search(query=f"{metal} price", count=3)
  return results
  ```

Or direct MCP calls:
  mcp__onetool__run(command='brave.web_search(query="test")')

Supported prefixes: __ot, __ot__run, __onetool, __onetool__run, mcp__onetool__run
Note: mcp__ot__run is NOT valid.

V3: Host execution with namespaces, aliases, and snippets.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastmcp import FastMCP

from ot.config.loader import get_config
from ot.executor import SimpleExecutor, execute_command

# Import logging first to remove Loguru's default console handler
from ot.logging import LogSpan, configure_logging
from ot.prompts import get_prompts, get_tool_description, get_tool_examples
from ot.proxy import get_proxy_manager
from ot.registry import get_registry

_config = get_config()

# Initialize logging to serve.log
configure_logging(log_name="serve")


def _get_instructions() -> str:
    """Generate MCP server instructions.

    Note: Tool descriptions are NOT included here - they come through
    the MCP tool definitions which the client converts to function calling format.
    """
    # Load prompts from config (loaded via include: or inline prompts:)
    prompts = get_prompts(inline_prompts=_config.prompts)

    # Start with base instructions from prompts.yaml
    instructions = prompts.instructions.strip()

    # Add header
    instructions = f"OneTool MCP server (V3, host execution).\n\n{instructions}"

    return instructions


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle - startup and shutdown."""
    with LogSpan(span="mcp.server.start") as start_span:
        # Startup: connect to proxy MCP servers
        proxy = get_proxy_manager()
        if _config.servers:
            with LogSpan(span="server.startup.proxy", serverCount=len(_config.servers)):
                await proxy.connect(_config.servers)
            start_span.add("proxyCount", len(_config.servers))

        # Log tool count from registry
        registry = get_registry()
        start_span.add("toolCount", len(registry.tools))

    yield

    with LogSpan(span="mcp.server.stop") as stop_span:
        # Shutdown: disconnect from proxy MCP servers
        if proxy.servers:
            with LogSpan(span="server.shutdown.proxy", serverCount=len(proxy.servers)):
                await proxy.shutdown()
            stop_span.add("proxyCount", len(proxy.servers))


mcp = FastMCP(
    name="ot",
    instructions=_get_instructions(),
    lifespan=_lifespan,
)


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


@mcp.tool(
    annotations={
        "title": "Execute OneTool Command",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
)
async def run(command: str) -> str:
    """Execute Python code or function calls.

    Args:
        command: Python code or function call to execute

    Returns:
        The result from executing the command
    """

    # Get registry (cached, no rescan per request) and executor
    registry = get_registry()
    executor = _get_executor()

    # Execute through unified runner
    result = await execute_command(command, registry, executor)

    return result.result


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(show_banner=False)
