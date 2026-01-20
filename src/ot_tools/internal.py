"""Consolidated OneTool internal tools.

Provides tool discovery and messaging under the unified `ot` namespace.
These are in-process tools with no external dependencies.

Functions:
    ot.tools() - List available tools
    ot.push(topic, msg) - Push message to topic file
    ot.config() - Show configuration
    ot.health() - Check system health
    ot.help(tool) - Get full documentation for a tool
    ot.instructions(ns) - Get usage instructions for a namespace
    ot.alias(name) - Show alias definition
    ot.snippet(name) - Show snippet definition
    ot.stats() - Get runtime statistics for OneTool usage
"""

from __future__ import annotations

# Namespace for dot notation: ot.tools(), ot.push(), etc.
namespace = "ot"

__all__ = [
    "alias",
    "config",
    "health",
    "help",
    "instructions",
    "push",
    "snippet",
    "stats",
    "tools",
]

import asyncio
import fnmatch
import inspect
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles
import yaml

from ot import __version__
from ot.config import get_config
from ot.executor.tool_loader import load_tool_registry
from ot.logging import LogSpan
from ot.paths import get_effective_cwd
from ot.proxy import get_proxy_manager
from ot.utils import format_result

# ============================================================================
# Tool Discovery Functions
# ============================================================================


def _parse_docstring(doc: str | None) -> dict[str, Any]:
    """Parse docstring using docstring-parser library.

    Args:
        doc: Function docstring

    Returns:
        Dict with 'short', 'args', 'returns', and 'example' keys
    """
    from docstring_parser import parse as parse_docstring

    if not doc:
        return {"short": "", "args": [], "returns": "", "example": ""}

    parsed = parse_docstring(doc)

    # Extract example from examples section
    example = ""
    if parsed.examples:
        example = "\n".join(
            ex.description or "" for ex in parsed.examples if ex.description
        )

    # Format args as "name: description" strings
    args = [
        f"{p.arg_name}: {p.description or '(no description)'}" for p in parsed.params
    ]

    return {
        "short": parsed.short_description or "",
        "args": args,
        "returns": parsed.returns.description if parsed.returns else "",
        "example": example,
    }


def tools(
    *,
    pattern: str = "",
    ns: str = "",
    compact: bool = False,
) -> str:
    """List all available tools with optional filtering.

    Lists registered local tools and proxied MCP server tools.
    Use pattern for name matching or ns to filter by namespace.

    Args:
        pattern: Filter tools by name pattern (case-insensitive substring match)
        ns: Filter tools by namespace (e.g., "brave", "ot")
        compact: If True, return only name and short description (default: False)

    Returns:
        JSON list of tools with name, signature, description, source

    Example:
        ot.tools()
        ot.tools(pattern="search")
        ot.tools(ns="brave")
        ot.tools(compact=True)
    """
    with LogSpan(
        span="ot.tools", pattern=pattern or None, ns=ns or None, compact=compact
    ) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        tools_list: list[dict[str, Any]] = []

        # Local tools from registry
        from ot.executor.worker_proxy import WorkerNamespaceProxy

        for ns_name, ns_funcs in runner_registry.namespaces.items():
            if ns and ns_name != ns:
                continue

            # Handle both dict and WorkerNamespaceProxy
            if isinstance(ns_funcs, WorkerNamespaceProxy):
                func_names = list(ns_funcs.functions)
                func_items = [(name, getattr(ns_funcs, name)) for name in func_names]
            else:
                func_items = list(ns_funcs.items())

            for func_name, func in func_items:
                full_name = f"{ns_name}.{func_name}"

                if pattern and pattern.lower() not in full_name.lower():
                    continue

                if func:
                    try:
                        sig = inspect.signature(func)
                        signature = f"{full_name}{sig}"
                    except (ValueError, TypeError):
                        signature = f"{full_name}(...)"
                    parsed = _parse_docstring(func.__doc__)
                    description = parsed["short"]
                else:
                    signature = f"{full_name}(...)"
                    description = ""
                    parsed = _parse_docstring(None)

                if compact:
                    tools_list.append({"name": full_name, "description": description})
                else:
                    tool_info: dict[str, Any] = {
                        "name": full_name,
                        "signature": signature,
                        "description": description,
                    }
                    if parsed["example"]:
                        tool_info["example"] = parsed["example"]
                    if parsed["returns"]:
                        tool_info["returns"] = parsed["returns"]
                    tool_info["source"] = "local"
                    tools_list.append(tool_info)

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            tool_name = f"{proxy_tool.server}.{proxy_tool.name}"
            tool_ns = proxy_tool.server

            if ns and tool_ns != ns:
                continue
            if pattern and pattern.lower() not in tool_name.lower():
                continue

            if compact:
                tools_list.append(
                    {
                        "name": tool_name,
                        "description": proxy_tool.description or "",
                    }
                )
            else:
                tools_list.append(
                    {
                        "name": tool_name,
                        "signature": f"{tool_name}(...)",
                        "description": proxy_tool.description or "",
                        "source": f"proxy:{proxy_tool.server}",
                    }
                )

        tools_list.sort(key=lambda t: t["name"])
        s.add("count", len(tools_list))
        return format_result(tools_list)


# ============================================================================
# Messaging Functions
# ============================================================================

_background_tasks: set[asyncio.Task[None]] = set()


def _resolve_path(path: str) -> Path:
    """Resolve a topic file path relative to project directory.

    Path resolution for topic files follows project conventions:
        - Relative paths: resolved relative to project directory (OT_CWD)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory

    Note: ${VAR} patterns are NOT expanded here. Use ~/path instead of
    ${HOME}/path. Secrets (e.g., ${API_KEY}) are expanded during config
    loading, not path resolution.

    Args:
        path: Path string from topic config.

    Returns:
        Resolved absolute Path.
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return (get_effective_cwd() / p).resolve()


def _match_topic_to_file(topic: str) -> Path | None:
    """Match topic to file path using first matching pattern.

    Paths in topic config are resolved relative to project directory (OT_CWD).
    See _resolve_path() for full path resolution behaviour.

    Args:
        topic: Topic string to match (e.g., "status:scan").

    Returns:
        Resolved file path for matching topic, or None if no match.
    """
    cfg = get_config()
    msg_config = cfg.tools.msg

    for topic_config in msg_config.topics:
        pattern = topic_config.pattern
        file_path = topic_config.file

        if fnmatch.fnmatch(topic, pattern):
            return _resolve_path(file_path)

    return None


async def _write_to_file(file_path: Path, doc: dict) -> None:
    """Write message document to file asynchronously."""
    with LogSpan(span="ot.write", file=str(file_path), topic=doc.get("topic")) as s:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "a") as f:
                await f.write("---\n")
                await f.write(
                    yaml.safe_dump(doc, default_flow_style=False, allow_unicode=True)
                )
            s.add("written", True)
        except Exception as e:
            s.add("error", str(e))


def push(*, topic: str, message: str) -> str:
    """Publish a message to the matching topic file.

    Routes the message to a YAML file based on topic pattern matching
    configured in ot-serve.yaml. The write happens asynchronously.

    Args:
        topic: Topic string for routing (e.g., "status:scan", "doc:api")
        message: Message content (text, can be multiline)

    Returns:
        "OK: <topic> -> <file>" if routed, "OK: no matching topic" if no match

    Example:
        ot.push(topic="status:scan", message="Scanning src/ directory")
    """
    with LogSpan(span="ot.push", topic=topic) as s:
        file_path = _match_topic_to_file(topic)

        if file_path is None:
            s.add("matched", False)
            return "OK: no matching topic"

        doc = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "topic": topic,
            "message": message,
        }

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_write_to_file(file_path, doc))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            asyncio.run(_write_to_file(file_path, doc))

        s.add("matched", True)
        s.add("file", str(file_path))
        return f"OK: {topic} -> {file_path}"


# ============================================================================
# Configuration & Health Functions
# ============================================================================


def config() -> str:
    """Show key configuration values.

    Returns aliases, snippets, and server names.

    Returns:
        JSON with configuration summary

    Example:
        ot.config()
    """
    with LogSpan(span="ot.config") as s:
        cfg = get_config()

        result: dict[str, Any] = {
            "aliases": dict(cfg.alias) if cfg.alias else {},
            "snippets": {
                name: {"description": snippet.description}
                for name, snippet in cfg.snippets.items()
            }
            if cfg.snippets
            else {},
            "servers": list(cfg.servers.keys()) if cfg.servers else [],
        }

        s.add("aliasCount", len(result["aliases"]))
        s.add("snippetCount", len(result["snippets"]))
        s.add("serverCount", len(result["servers"]))

        return format_result(result, compact=False)


def health() -> str:
    """Check health of OneTool components.

    Returns:
        JSON with component status for registry and proxy

    Example:
        ot.health()
    """
    with LogSpan(span="ot.health") as s:
        from ot.executor.worker_proxy import WorkerNamespaceProxy

        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        cfg = get_config()

        # Count functions, handling both dict and WorkerNamespaceProxy
        tool_count = 0
        for funcs in runner_registry.namespaces.values():
            if isinstance(funcs, WorkerNamespaceProxy):
                tool_count += len(funcs.functions)
            else:
                tool_count += len(funcs)
        registry_status = {
            "status": "ok",
            "tool_count": tool_count,
        }

        server_statuses: dict[str, str] = {}
        for name in cfg.servers:
            conn = proxy.get_connection(name)
            server_statuses[name] = "connected" if conn else "disconnected"

        proxy_status: dict[str, Any] = {
            "status": "ok"
            if all(s == "connected" for s in server_statuses.values())
            or not server_statuses
            else "degraded",
            "server_count": len(cfg.servers),
        }
        if server_statuses:
            proxy_status["servers"] = server_statuses

        result = {
            "version": __version__,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "cwd": str(get_effective_cwd()),
            "registry": registry_status,
            "proxy": proxy_status,
        }

        s.add("registryOk", registry_status["status"] == "ok")
        s.add("proxyOk", proxy_status["status"] == "ok")

        return format_result(result, compact=False)


def stats(
    *,
    period: str = "all",
    tool: str = "",
    output: str = "",
) -> str:
    """Get runtime statistics for OneTool usage.

    Returns aggregated statistics including call counts, success rates,
    durations, and estimated context/time savings from tool consolidation.

    Args:
        period: Time period to filter - "day", "week", "month", or "all" (default: "all")
        tool: Filter by tool name (e.g., "brave.search"). Empty for all tools.
        output: Path to write HTML report. Empty for JSON output only.

    Returns:
        JSON with aggregated statistics including:
        - total_calls: Total number of tool calls
        - success_rate: Percentage of successful calls
        - context_saved: Estimated context tokens saved
        - time_saved_ms: Estimated time saved in milliseconds
        - tools: Per-tool breakdown

    Example:
        ot.stats()
        ot.stats(period="day")
        ot.stats(period="week", tool="brave.search")
        ot.stats(output="stats_report.html")
    """
    from ot.stats import Period, StatsReader
    from ot.support import get_support_dict

    with LogSpan(span="ot.stats", period=period, tool=tool or None) as s:
        cfg = get_config()

        # Validate period
        valid_periods: list[Period] = ["day", "week", "month", "all"]
        if period not in valid_periods:
            s.add("error", "invalid_period")
            return f"Error: Invalid period '{period}'. Use: {', '.join(valid_periods)}"

        # Check if stats are enabled
        if not cfg.tools.stats.enabled:
            s.add("error", "stats_disabled")
            return "Error: Statistics collection is disabled in configuration"

        # Read stats
        stats_path = cfg.get_stats_file_path()
        reader = StatsReader(
            path=stats_path,
            context_per_call=cfg.tools.stats.context_per_call,
            time_overhead_per_call_ms=cfg.tools.stats.time_overhead_per_call_ms,
            model=cfg.tools.stats.model,
            cost_per_million_input_tokens=cfg.tools.stats.cost_per_million_input_tokens,
            cost_per_million_output_tokens=cfg.tools.stats.cost_per_million_output_tokens,
            chars_per_token=cfg.tools.stats.chars_per_token,
        )

        aggregated = reader.read(
            period=period,  # type: ignore[arg-type]
            tool=tool if tool else None,
        )

        result = aggregated.to_dict()
        result["support"] = get_support_dict()
        s.add("totalCalls", result["total_calls"])
        s.add("toolCount", len(result["tools"]))

        # Generate HTML report if output path specified
        if output:
            from ot.stats.html import generate_html_report

            # Resolve output path relative to log directory (alongside stats.jsonl)
            output_path = cfg.get_log_dir_path() / output
            html_content = generate_html_report(aggregated)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content)
            result["html_report"] = str(output_path)
            s.add("htmlReport", str(output_path))

        return format_result(result, compact=False)


# ============================================================================
# Introspection Functions
# ============================================================================


def help(*, tool: str) -> str:
    """Get full documentation for a tool.

    Returns the complete docstring with signature, arguments,
    returns, and examples. Works for both local tools and proxy tools.

    Args:
        tool: Tool name in namespace.function format (e.g., "brave.search")

    Returns:
        Formatted documentation with signature, args, returns, and examples

    Example:
        ot.help(tool="ot.tools")
        ot.help(tool="github.create_issue")
    """
    with LogSpan(span="ot.help", tool=tool) as s:
        # Validate format
        if "." not in tool:
            s.add("error", "invalid_format")
            return f"Error: Use namespace.function format (e.g., brave.search). Got: {tool}"

        ns_name, func_name = tool.rsplit(".", 1)
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Check local registry first
        if ns_name in runner_registry.namespaces:
            ns_funcs = runner_registry.namespaces[ns_name]

            # Handle both dict and WorkerNamespaceProxy
            from ot.executor.worker_proxy import WorkerNamespaceProxy

            if isinstance(ns_funcs, WorkerNamespaceProxy):
                if func_name not in ns_funcs.functions:
                    available = ", ".join(sorted(ns_funcs.functions))
                    s.add("error", "function_not_found")
                    return (
                        f"Error: '{func_name}' not in {ns_name}. Available: {available}"
                    )
                func = getattr(ns_funcs, func_name)
            else:
                if func_name not in ns_funcs:
                    available = ", ".join(sorted(ns_funcs.keys()))
                    s.add("error", "function_not_found")
                    return (
                        f"Error: '{func_name}' not in {ns_name}. Available: {available}"
                    )
                func = ns_funcs[func_name]

            s.add("found", True)
            s.add("source", "local")
            return _format_local_help(tool, func)

        # Check proxy tools
        proxy_tools = proxy.list_tools(server=ns_name)
        if proxy_tools:
            for proxy_tool in proxy_tools:
                if proxy_tool.name == func_name:
                    s.add("found", True)
                    s.add("source", f"proxy:{ns_name}")
                    return _format_proxy_help(tool, proxy_tool)

            # Tool not found in this proxy server
            available = ", ".join(sorted(t.name for t in proxy_tools))
            s.add("error", "function_not_found")
            return f"Error: '{func_name}' not in {ns_name}. Available: {available}"

        # Namespace not found in local or proxy
        local_ns = set(runner_registry.namespaces.keys())
        proxy_ns = set(proxy.servers)
        all_ns = sorted(local_ns | proxy_ns)
        s.add("error", "namespace_not_found")
        return f"Error: Namespace '{ns_name}' not found. Available: {', '.join(all_ns)}"


def _format_local_help(tool: str, func: Any) -> str:
    """Format help output for a local tool."""
    from ot.prompts import (
        PromptsError,
        get_prompts,
        get_tool_description,
        get_tool_examples,
    )

    lines = [f"## {tool}", ""]

    # Parse docstring
    parsed = _parse_docstring(func.__doc__)
    first_line = parsed["short"] or "(no description)"

    # Check prompts.yaml for description override
    try:
        prompts_config = get_prompts()
        description = get_tool_description(prompts_config, tool, first_line)
        config_examples = get_tool_examples(prompts_config, tool)
    except PromptsError:
        description = first_line
        config_examples = []

    lines.append(description)
    lines.append("")

    # Signature
    try:
        sig = inspect.signature(func)
        lines.append(f"**Signature**: {tool}{sig}")
    except (ValueError, TypeError):
        lines.append(f"**Signature**: {tool}(...)")
    lines.append("")

    if parsed["args"]:
        lines.append("**Args**:")
        for arg_line in parsed["args"]:
            lines.append(f"- {arg_line}")
        lines.append("")

    if parsed["returns"]:
        lines.append(f"**Returns**: {parsed['returns']}")
        lines.append("")

    # Use config examples if available, otherwise docstring examples
    if config_examples:
        lines.append("**Examples**:")
        lines.append("```python")
        for example in config_examples:
            lines.append(example)
        lines.append("```")
    elif parsed["example"]:
        lines.append("**Example**:")
        lines.append("```python")
        lines.append(parsed["example"])
        lines.append("```")

    return "\n".join(lines)


def _format_proxy_help(tool: str, proxy_tool: Any) -> str:
    """Format help output for a proxy tool from MCP schema."""
    from ot.prompts import (
        PromptsError,
        get_prompts,
        get_tool_description,
        get_tool_examples,
    )

    lines = [f"## {tool}", ""]

    # Get default description from proxy tool
    default_desc = proxy_tool.description or "(no description)"

    # Check prompts.yaml for description override
    try:
        prompts_config = get_prompts()
        description = get_tool_description(prompts_config, tool, default_desc)
        config_examples = get_tool_examples(prompts_config, tool)
    except PromptsError:
        description = default_desc
        config_examples = []

    lines.append(description)
    lines.append("")

    # Parameters from input schema
    schema = proxy_tool.input_schema
    if schema and "properties" in schema:
        required = set(schema.get("required", []))
        lines.append("**Parameters**:")
        for param_name, param_info in schema["properties"].items():
            param_type = param_info.get("type", "any")
            param_desc = param_info.get("description", "")
            required_marker = " (required)" if param_name in required else ""
            if param_desc:
                lines.append(f"- {param_name}: {param_desc}{required_marker}")
            else:
                lines.append(f"- {param_name}: ({param_type}){required_marker}")
        lines.append("")

    # Show examples if configured
    if config_examples:
        lines.append("**Examples**:")
        lines.append("```python")
        for example in config_examples:
            lines.append(example)
        lines.append("```")
        lines.append("")

    # Source
    lines.append(f"**Source**: proxy:{proxy_tool.server}")

    return "\n".join(lines)


def instructions(*, ns: str) -> str:
    """Get usage instructions for a namespace.

    Returns instructions from prompts.yaml if configured, otherwise
    generates instructions from tool docstrings (local) or tool list (proxy).

    Args:
        ns: Namespace name (e.g., "brave", "github", "excel")

    Returns:
        Instructions text for the namespace

    Example:
        ot.instructions(ns="brave")
        ot.instructions(ns="github")
    """
    from ot.prompts import PromptsError, get_namespace_instructions, get_prompts

    with LogSpan(span="ot.instructions", ns=ns) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Collect available namespaces
        local_ns = set(runner_registry.namespaces.keys())
        proxy_ns = set(proxy.servers)
        all_ns = local_ns | proxy_ns

        # Check if namespace exists
        if ns not in all_ns:
            s.add("error", "namespace_not_found")
            return f"Error: Namespace '{ns}' not found. Available: {', '.join(sorted(all_ns))}"

        # Try to get configured instructions from prompts.yaml
        try:
            prompts_config = get_prompts()
            configured = get_namespace_instructions(prompts_config, ns)
            if configured:
                s.add("source", "config")
                return configured
        except PromptsError:
            # No prompts.yaml or loading failed - continue to fallback
            pass

        # Fallback: generate instructions
        if ns in local_ns:
            s.add("source", "local_docstrings")
            return _generate_local_instructions(ns, runner_registry)
        else:
            s.add("source", "proxy_tools")
            return _generate_proxy_instructions(ns, proxy)


def _generate_local_instructions(ns: str, registry: Any) -> str:
    """Generate instructions from local tool docstrings."""
    from ot.executor.worker_proxy import WorkerNamespaceProxy

    ns_funcs = registry.namespaces[ns]

    lines = [f"# {ns} namespace", ""]

    # Handle both dict and WorkerNamespaceProxy
    if isinstance(ns_funcs, WorkerNamespaceProxy):
        func_items = [(name, getattr(ns_funcs, name)) for name in ns_funcs.functions]
    else:
        func_items = list(ns_funcs.items())

    for func_name, func in sorted(func_items):
        doc = func.__doc__ or "(no description)"
        first_line = doc.split("\n")[0].strip()
        lines.append(f"- **{ns}.{func_name}**: {first_line}")

    return "\n".join(lines)


def _generate_proxy_instructions(ns: str, proxy: Any) -> str:
    """Generate instructions from proxy tool list."""
    tools = proxy.list_tools(server=ns)

    lines = [f"# {ns} namespace (proxy)", ""]
    lines.append(f"Tools available from the {ns} MCP server:")
    lines.append("")

    for tool in sorted(tools, key=lambda t: t.name):
        desc = tool.description or "(no description)"
        first_line = desc.split("\n")[0].strip()
        lines.append(f"- **{ns}.{tool.name}**: {first_line}")

    return "\n".join(lines)


def alias(*, name: str) -> str:
    """Show alias definition.

    Returns what an alias expands to, or lists all aliases if name is "*".

    Args:
        name: Alias name, or "*" to list all aliases

    Returns:
        Alias mapping (alias -> target) or list of all aliases

    Example:
        ot.alias(name="ws")
        ot.alias(name="*")
    """
    with LogSpan(span="ot.alias", name=name) as s:
        cfg = get_config()

        if name == "*":
            if not cfg.alias:
                s.add("count", 0)
                return "No aliases configured"

            lines = [f"{k} -> {v}" for k, v in sorted(cfg.alias.items())]
            s.add("count", len(lines))
            return "\n".join(lines)

        if name not in cfg.alias:
            available = ", ".join(sorted(cfg.alias.keys())) or "(none)"
            s.add("error", "not_found")
            return f"Error: Alias '{name}' not found. Available: {available}"

        s.add("found", True)
        return f"{name} -> {cfg.alias[name]}"


def snippet(*, name: str) -> str:
    """Show snippet definition and preview.

    Returns the snippet's description, parameters, and body template.
    If name is "*", lists all snippets with descriptions.

    Args:
        name: Snippet name, or "*" to list all snippets

    Returns:
        Snippet definition with example expansion, or list of snippets

    Example:
        ot.snippet(name="brv_research")
        ot.snippet(name="*")
    """
    with LogSpan(span="ot.snippet", name=name) as s:
        cfg = get_config()

        if name == "*":
            if not cfg.snippets:
                s.add("count", 0)
                return "No snippets configured"

            lines = [
                f"{k}: {v.description or '(no description)'}"
                for k, v in sorted(cfg.snippets.items())
            ]
            s.add("count", len(lines))
            return "\n".join(lines)

        if name not in cfg.snippets:
            available = ", ".join(sorted(cfg.snippets.keys())) or "(none)"
            s.add("error", "not_found")
            return f"Error: Snippet '{name}' not found. Available: {available}"

        snippet_def = cfg.snippets[name]

        # Format output as YAML-like
        lines = [f"name: {name}"]

        if snippet_def.description:
            lines.append(f"description: {snippet_def.description}")

        if snippet_def.params:
            lines.append("params:")
            for param_name, param_def in snippet_def.params.items():
                param_parts = []
                if param_def.default is not None:
                    param_parts.append(f"default: {param_def.default}")
                if param_def.description:
                    param_parts.append(f'description: "{param_def.description}"')
                lines.append(f"  {param_name}: {{{', '.join(param_parts)}}}")

        lines.append("body: |")
        for body_line in snippet_def.body.rstrip().split("\n"):
            lines.append(f"  {body_line}")

        # Add example invocation
        lines.append("")
        lines.append("# Example:")

        # Build example with defaults
        example_args = []
        for param_name, param_def in snippet_def.params.items():
            if param_def.default is not None:
                continue  # Skip params with defaults in example
            example_args.append(f'{param_name}="..."')

        if example_args:
            lines.append(f"# ${name} {' '.join(example_args)}")
        else:
            lines.append(f"# ${name}")

        s.add("found", True)
        return "\n".join(lines)
