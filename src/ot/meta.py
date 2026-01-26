"""OneTool core introspection tools (ot pack).

Provides tool discovery and messaging under the unified `ot` pack.
These are core introspection functions, not external tools, so they
live in the core package rather than tools_dir.

Functions:
    ot.tools() - List or get tools with full documentation
    ot.packs() - List or get packs with instructions
    ot.aliases() - List or get alias definitions
    ot.snippets() - List or get snippet definitions
    ot.config() - Show configuration summary
    ot.health() - Check system health
    ot.stats() - Get runtime statistics
    ot.notify() - Publish message to topic
    ot.reload() - Force configuration reload
"""

from __future__ import annotations

import asyncio
import fnmatch
import inspect
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import aiofiles
import yaml

from ot import __version__
from ot.config import get_config
from ot.proxy import get_proxy_manager
from ot_sdk import log, resolve_cwd_path, resolve_ot_path

# Pack name for dot notation: ot.tools(), ot.packs(), etc.
PACK_NAME = "ot"

__all__ = [
    "PACK_NAME",
    "aliases",
    "config",
    "get_ot_pack_functions",
    "health",
    "notify",
    "packs",
    "reload",
    "snippets",
    "stats",
    "tools",
]


def get_ot_pack_functions() -> dict[str, Any]:
    """Get all ot pack functions for registration.

    Returns:
        Dict mapping function names to callables
    """
    return {
        "tools": tools,
        "packs": packs,
        "aliases": aliases,
        "snippets": snippets,
        "config": config,
        "health": health,
        "stats": stats,
        "notify": notify,
        "reload": reload,
    }


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


def _build_tool_info(
    full_name: str, func: Any, source: str, compact: bool
) -> dict[str, Any]:
    """Build tool info dict for a single tool.

    When compact=False, includes full documentation (args, returns, example).
    """
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
        return {"name": full_name, "description": description}

    tool_info: dict[str, Any] = {
        "name": full_name,
        "signature": signature,
        "description": description,
    }
    # Include full documentation for LLM context
    if parsed["args"]:
        tool_info["args"] = parsed["args"]
    if parsed["returns"]:
        tool_info["returns"] = parsed["returns"]
    if parsed["example"]:
        tool_info["example"] = parsed["example"]
    tool_info["source"] = source
    return tool_info


def _schema_to_signature(full_name: str, schema: dict[str, Any]) -> str:
    """Convert JSON Schema to Python-like signature string.

    Args:
        full_name: Full tool name (e.g., "github.search")
        schema: JSON Schema dict with 'properties' and 'required' keys

    Returns:
        Signature string like "github.search(query: str, repo: str = '...')"
    """
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    if not props:
        return f"{full_name}()"

    params: list[str] = []
    # Process required params first, then optional
    for prop_name in sorted(props.keys(), key=lambda k: (k not in required, k)):
        prop_def = props[prop_name]
        prop_type = prop_def.get("type", "Any")

        # Map JSON Schema types to Python-like types
        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
        }
        py_type = type_map.get(prop_type, prop_type)

        if prop_name in required:
            params.append(f"{prop_name}: {py_type}")
        else:
            default = prop_def.get("default")
            if default is not None:
                params.append(f"{prop_name}: {py_type} = {default!r}")
            else:
                params.append(f"{prop_name}: {py_type} = ...")

    return f"{full_name}({', '.join(params)})"


def _parse_input_schema(schema: dict[str, Any]) -> list[str]:
    """Extract argument descriptions from JSON Schema properties.

    Args:
        schema: JSON Schema dict with 'properties' key

    Returns:
        List of "param_name: description" strings matching local tool format
    """
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    args: list[str] = []
    # Process required params first, then optional
    for prop_name in sorted(props.keys(), key=lambda k: (k not in required, k)):
        prop_def = props[prop_name]
        description = prop_def.get("description", "(no description)")
        args.append(f"{prop_name}: {description}")

    return args


def _build_proxy_tool_info(
    full_name: str,
    description: str,
    input_schema: dict[str, Any],
    source: str,
    compact: bool,
) -> dict[str, Any]:
    """Build tool info dict for a proxy tool using its input schema.

    Args:
        full_name: Full tool name (e.g., "github.search")
        description: Tool description from MCP server
        input_schema: JSON Schema for tool input
        source: Source identifier (e.g., "proxy:github")
        compact: If True, return only name and description

    Returns:
        Tool info dict matching local tool format
    """
    if compact:
        return {"name": full_name, "description": description}

    tool_info: dict[str, Any] = {
        "name": full_name,
        "signature": _schema_to_signature(full_name, input_schema),
        "description": description,
    }

    # Include args if schema has properties with descriptions
    args = _parse_input_schema(input_schema)
    if args:
        tool_info["args"] = args

    tool_info["source"] = source
    return tool_info


def tools(
    *,
    name: str = "",
    pattern: str = "",
    pack: str = "",
    compact: bool = False,
) -> list[dict[str, Any]] | dict[str, Any] | str:
    """List all available tools with optional filtering, or get a specific tool.

    Lists registered local tools and proxied MCP server tools.
    Use name for exact match, pattern for substring filtering, or pack to filter by pack.

    Args:
        name: Get specific tool by exact name (e.g., "brave.search")
        pattern: Filter tools by name pattern (case-insensitive substring match)
        pack: Filter tools by pack (e.g., "brave", "ot")
        compact: If True, return only name and short description (default: False)

    Returns:
        Single tool dict if name specified, otherwise list of tool dicts

    Example:
        ot.tools()
        ot.tools(name="brave.search")
        ot.tools(pattern="search")
        ot.tools(pack="brave")
        ot.tools(compact=True)
    """
    from ot.executor.tool_loader import load_tool_registry

    with log(
        "ot.tools", toolName=name or None, pattern=pattern or None, pack=pack or None, compact=compact
    ) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # If specific name requested, find and return just that tool
        if name:
            from ot.executor.worker_proxy import WorkerPackProxy

            if "." not in name:
                s.add("error", "invalid_format")
                return f"Error: Use pack.function format (e.g., brave.search). Got: {name}"

            pack_name, func_name = name.rsplit(".", 1)

            # Check local registry
            if pack_name in runner_registry.packs:
                pack_funcs = runner_registry.packs[pack_name]
                if isinstance(pack_funcs, WorkerPackProxy):
                    if func_name in pack_funcs.functions:
                        func = getattr(pack_funcs, func_name)
                        s.add("found", True)
                        s.add("source", "local")
                        return _build_tool_info(f"{pack_name}.{func_name}", func, "local", compact)
                elif func_name in pack_funcs:
                    func = pack_funcs[func_name]
                    s.add("found", True)
                    s.add("source", "local")
                    return _build_tool_info(f"{pack_name}.{func_name}", func, "local", compact)

            # Check proxy tools
            for proxy_tool in proxy.list_tools(server=pack_name):
                if proxy_tool.name == func_name:
                    s.add("found", True)
                    s.add("source", f"proxy:{pack_name}")
                    return _build_proxy_tool_info(
                        name,
                        proxy_tool.description or "",
                        proxy_tool.input_schema,
                        f"proxy:{pack_name}",
                        compact,
                    )

            # Not found
            local_packs = set(runner_registry.packs.keys())
            proxy_packs = set(proxy.servers)
            all_packs = sorted(local_packs | proxy_packs)
            s.add("error", "not_found")
            return f"Error: Tool '{name}' not found. Available packs: {', '.join(all_packs)}"

        tools_list: list[dict[str, Any]] = []

        # Local tools from registry
        from ot.executor.worker_proxy import WorkerPackProxy

        for pack_name, pack_funcs in runner_registry.packs.items():
            if pack and pack_name != pack:
                continue

            # Handle both dict and WorkerPackProxy
            if isinstance(pack_funcs, WorkerPackProxy):
                func_names = list(pack_funcs.functions)
                func_items = [(n, getattr(pack_funcs, n)) for n in func_names]
            else:
                func_items = list(pack_funcs.items())

            for func_name, func in func_items:
                full_name = f"{pack_name}.{func_name}"

                if pattern and pattern.lower() not in full_name.lower():
                    continue

                tools_list.append(_build_tool_info(full_name, func, "local", compact))

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            tool_name = f"{proxy_tool.server}.{proxy_tool.name}"
            tool_pack = proxy_tool.server

            if pack and tool_pack != pack:
                continue
            if pattern and pattern.lower() not in tool_name.lower():
                continue

            tools_list.append(
                _build_proxy_tool_info(
                    tool_name,
                    proxy_tool.description or "",
                    proxy_tool.input_schema,
                    f"proxy:{proxy_tool.server}",
                    compact,
                )
            )

        tools_list.sort(key=lambda t: t["name"])
        s.add("count", len(tools_list))
        return tools_list


def packs(
    *,
    name: str = "",
    pattern: str = "",
) -> list[dict[str, Any]] | str:
    """List all packs or get detailed pack info with instructions.

    With no arguments, lists all available packs (local and proxy).
    Use name to get detailed pack info including instructions.
    Use pattern for substring filtering.

    Args:
        name: Get specific pack by exact name (e.g., "brave")
        pattern: Filter packs by name pattern (case-insensitive substring)

    Returns:
        List of pack summaries, or detailed pack info with instructions

    Example:
        ot.packs()
        ot.packs(name="brave")
        ot.packs(pattern="search")
    """
    from ot.executor.tool_loader import load_tool_registry
    from ot.prompts import PromptsError, get_pack_instructions, get_prompts

    with log("ot.packs", packName=name or None, pattern=pattern or None) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Collect all packs
        local_packs = set(runner_registry.packs.keys())
        proxy_packs = set(proxy.servers)
        all_pack_names = sorted(local_packs | proxy_packs)

        # Get specific pack by name
        if name:
            if name not in (local_packs | proxy_packs):
                s.add("error", "not_found")
                return f"Error: Pack '{name}' not found. Available: {', '.join(all_pack_names)}"

            s.add("found", True)
            is_local = name in local_packs
            s.add("source", "local" if is_local else "proxy")

            # Build detailed pack info
            lines = [f"# {name} pack", ""]

            # Get instructions
            try:
                prompts_config = get_prompts()
                configured = get_pack_instructions(prompts_config, name)
                if configured:
                    lines.append(configured)
                    lines.append("")
            except PromptsError:
                pass

            # List tools in this pack
            lines.append("## Tools")
            lines.append("")

            if is_local:
                from ot.executor.worker_proxy import WorkerPackProxy

                pack_funcs = runner_registry.packs[name]
                if isinstance(pack_funcs, WorkerPackProxy):
                    func_items = [(n, getattr(pack_funcs, n)) for n in pack_funcs.functions]
                else:
                    func_items = list(pack_funcs.items())

                for func_name, func in sorted(func_items):
                    doc = func.__doc__ or "(no description)"
                    first_line = doc.split("\n")[0].strip()
                    lines.append(f"- **{name}.{func_name}**: {first_line}")
            else:
                proxy_tools = proxy.list_tools(server=name)
                for tool in sorted(proxy_tools, key=lambda t: t.name):
                    desc = tool.description or "(no description)"
                    first_line = desc.split("\n")[0].strip()
                    lines.append(f"- **{name}.{tool.name}**: {first_line}")

            return "\n".join(lines)

        # List all packs (with optional pattern filter)
        packs_list: list[dict[str, Any]] = []

        for pack_name in all_pack_names:
            if pattern and pattern.lower() not in pack_name.lower():
                continue

            is_local = pack_name in local_packs
            source = "local" if is_local else "proxy"

            # Count tools in pack
            if is_local:
                from ot.executor.worker_proxy import WorkerPackProxy

                pack_funcs = runner_registry.packs[pack_name]
                if isinstance(pack_funcs, WorkerPackProxy):
                    tool_count = len(pack_funcs.functions)
                else:
                    tool_count = len(pack_funcs)
            else:
                tool_count = len(proxy.list_tools(server=pack_name))

            packs_list.append({
                "name": pack_name,
                "source": source,
                "tool_count": tool_count,
            })

        s.add("count", len(packs_list))
        return packs_list


# ============================================================================
# Messaging Functions
# ============================================================================

_background_tasks: set[asyncio.Task[None]] = set()


def _resolve_path(path: str) -> Path:
    """Resolve a topic file path relative to OT_DIR (.onetool/).

    Uses SDK resolve_ot_path() for consistent path resolution.

    Path resolution for topic files follows OT_DIR conventions:
        - Relative paths: resolved relative to OT_DIR (.onetool/)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory
        - Prefixed paths (CWD/, GLOBAL/, OT_DIR/): resolved to respective dirs

    Note: ${VAR} patterns are NOT expanded here. Use ~/path instead of
    ${HOME}/path. Secrets (e.g., ${API_KEY}) are expanded during config
    loading, not path resolution.

    Args:
        path: Path string from topic config.

    Returns:
        Resolved absolute Path.
    """
    return resolve_ot_path(path)


def _match_topic_to_file(topic: str) -> Path | None:
    """Match topic to file path using first matching pattern.

    Paths in topic config are resolved relative to OT_DIR (.onetool/).
    See _resolve_path() for full path resolution behaviour.

    Args:
        topic: Topic string to match (e.g., "status:scan").

    Returns:
        Resolved file path for matching topic, or None if no match.
    """
    cfg = get_config()
    msg_config = cfg.tools.msg

    for topic_config in msg_config.topics:
        topic_pattern = topic_config.pattern
        file_path = topic_config.file

        if fnmatch.fnmatch(topic, topic_pattern):
            return _resolve_path(file_path)

    return None


async def _write_to_file(file_path: Path, doc: dict) -> None:
    """Write message document to file asynchronously."""
    with log("ot.write", file=str(file_path), topic=doc.get("topic")) as s:
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


def notify(*, topic: str, message: str) -> str:
    """Publish a message to the matching topic file.

    Routes the message to a YAML file based on topic pattern matching
    configured in ot-serve.yaml. The write happens asynchronously.

    Args:
        topic: Topic string for routing (e.g., "status:scan", "notes")
        message: Message content (text, can be multiline)

    Returns:
        "OK: <topic> -> <file>" if routed, "OK: no matching topic" if no match

    Example:
        ot.notify(topic="notes", message="Remember to review PR #123")
    """
    with log("ot.notify", topic=topic) as s:
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


def config() -> dict[str, Any]:
    """Show key configuration values.

    Returns aliases, snippets, and server names.

    Returns:
        Dict with configuration summary

    Example:
        ot.config()
    """
    with log("ot.config") as s:
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

        return result


def health() -> dict[str, Any]:
    """Check health of OneTool components.

    Returns:
        Dict with component status for registry and proxy

    Example:
        ot.health()
    """
    from ot.executor.tool_loader import load_tool_registry

    with log("ot.health") as s:
        from ot.executor.worker_proxy import WorkerPackProxy

        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()
        cfg = get_config()

        # Count functions, handling both dict and WorkerPackProxy
        tool_count = 0
        for funcs in runner_registry.packs.values():
            if isinstance(funcs, WorkerPackProxy):
                tool_count += len(funcs.functions)
            else:
                tool_count += len(funcs)
        registry_status = {
            "status": "ok",
            "tool_count": tool_count,
        }

        server_statuses: dict[str, str] = {}
        for server_name in cfg.servers:
            conn = proxy.get_connection(server_name)
            server_statuses[server_name] = "connected" if conn else "disconnected"

        proxy_status: dict[str, Any] = {
            "status": "ok"
            if all(status == "connected" for status in server_statuses.values())
            or not server_statuses
            else "degraded",
            "server_count": len(cfg.servers),
        }
        if server_statuses:
            proxy_status["servers"] = server_statuses

        result = {
            "version": __version__,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "cwd": str(resolve_cwd_path(".")),
            "registry": registry_status,
            "proxy": proxy_status,
        }

        s.add("registryOk", registry_status["status"] == "ok")
        s.add("proxyOk", proxy_status["status"] == "ok")

        return result


def reload() -> str:
    """Force reload of all configuration.

    Clears cached configuration and reloads from disk.
    Use after modifying config files during a session.

    Returns:
        Status message confirming reload

    Example:
        ot.reload()
    """
    with log("ot.reload") as s:
        import ot.config.loader
        import ot.prompts

        # Clear config cache
        ot.config.loader._config = None

        # Clear prompts cache
        ot.prompts._prompts = None

        # Reload to validate
        cfg = get_config()
        s.add("aliasCount", len(cfg.alias) if cfg.alias else 0)
        s.add("snippetCount", len(cfg.snippets) if cfg.snippets else 0)
        s.add("serverCount", len(cfg.servers) if cfg.servers else 0)

        return "OK: Configuration reloaded"


def stats(
    *,
    period: str = "all",
    tool: str = "",
    output: str = "",
) -> dict[str, Any] | str:
    """Get runtime statistics for OneTool usage.

    Returns aggregated statistics including call counts, success rates,
    durations, and estimated context/time savings from tool consolidation.

    Args:
        period: Time period to filter - "day", "week", "month", or "all" (default: "all")
        tool: Filter by tool name (e.g., "brave.search"). Empty for all tools.
        output: Path to write HTML report. Empty for JSON output only.

    Returns:
        Dict with aggregated statistics including:
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

    with log("ot.stats", period=period, tool=tool or None) as s:
        cfg = get_config()

        # Validate period
        valid_periods: list[Period] = ["day", "week", "month", "all"]
        if period not in valid_periods:
            s.add("error", "invalid_period")
            return f"Error: Invalid period '{period}'. Use: {', '.join(valid_periods)}"

        # Check if stats are enabled
        if not cfg.stats.enabled:
            s.add("error", "stats_disabled")
            return "Error: Statistics collection is disabled in configuration"

        # Read stats
        stats_path = cfg.get_stats_file_path()
        reader = StatsReader(
            path=stats_path,
            context_per_call=cfg.stats.context_per_call,
            time_overhead_per_call_ms=cfg.stats.time_overhead_per_call_ms,
            model=cfg.stats.model,
            cost_per_million_input_tokens=cfg.stats.cost_per_million_input_tokens,
            cost_per_million_output_tokens=cfg.stats.cost_per_million_output_tokens,
            chars_per_token=cfg.stats.chars_per_token,
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

        return result


# ============================================================================
# Introspection Functions
# ============================================================================


def aliases(
    *,
    name: str = "",
    pattern: str = "",
) -> str:
    """List aliases or get a specific alias definition.

    With no arguments, lists all aliases.
    Use name for exact match, or pattern for substring filtering.

    Args:
        name: Get specific alias by exact name (e.g., "ws")
        pattern: Filter aliases by name pattern (case-insensitive substring)

    Returns:
        Single alias mapping, filtered list, or all aliases

    Example:
        ot.aliases()
        ot.aliases(name="ws")
        ot.aliases(pattern="search")
    """
    with log("ot.aliases", aliasName=name or None, pattern=pattern or None) as s:
        cfg = get_config()

        if not cfg.alias:
            s.add("count", 0)
            return "No aliases configured"

        # Get specific alias by name
        if name:
            if name not in cfg.alias:
                available = ", ".join(sorted(cfg.alias.keys()))
                s.add("error", "not_found")
                return f"Error: Alias '{name}' not found. Available: {available}"
            s.add("found", True)
            return f"{name} -> {cfg.alias[name]}"

        # Filter by pattern or list all
        items = sorted(cfg.alias.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [(k, v) for k, v in items if pattern_lower in k.lower() or pattern_lower in v.lower()]

        if not items:
            s.add("count", 0)
            return f"No aliases matching pattern '{pattern}'"

        lines = [f"{k} -> {v}" for k, v in items]
        s.add("count", len(lines))
        return "\n".join(lines)


def snippets(
    *,
    name: str = "",
    pattern: str = "",
) -> str:
    """List snippets or get a specific snippet definition.

    With no arguments, lists all snippets with descriptions.
    Use name for exact match (returns full definition), or pattern for filtering.

    Args:
        name: Get specific snippet by exact name (e.g., "pkg_pypi")
        pattern: Filter snippets by name/description pattern (case-insensitive substring)

    Returns:
        Single snippet definition, filtered list, or all snippets

    Example:
        ot.snippets()
        ot.snippets(name="pkg_pypi")
        ot.snippets(pattern="search")
    """
    with log("ot.snippets", snippetName=name or None, pattern=pattern or None) as s:
        cfg = get_config()

        if not cfg.snippets:
            s.add("count", 0)
            return "No snippets configured"

        # Get specific snippet by name
        if name:
            if name not in cfg.snippets:
                available = ", ".join(sorted(cfg.snippets.keys()))
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

        # Filter by pattern or list all
        items = sorted(cfg.snippets.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [
                (k, v) for k, v in items
                if pattern_lower in k.lower() or pattern_lower in (v.description or "").lower()
            ]

        if not items:
            s.add("count", 0)
            return f"No snippets matching pattern '{pattern}'"

        lines = [f"{k}: {v.description or '(no description)'}" for k, v in items]
        s.add("count", len(lines))
        return "\n".join(lines)
