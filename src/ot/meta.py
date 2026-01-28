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
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

import aiofiles
import yaml

from ot import __version__
from ot.config import get_config
from ot.proxy import get_proxy_manager
from ot_sdk import log, resolve_cwd_path, resolve_ot_path

# Info level type for discovery functions
InfoLevel = Literal["list", "min", "full"]

# Pack name for dot notation: ot.tools(), ot.packs(), etc.
PACK_NAME = "ot"

# Documentation URL mapping for packs with misaligned slugs
DOC_SLUGS: dict[str, str] = {
    "brave": "brave-search",
    "code": "code-search",
    "db": "database",
    "ground": "grounding-search",
    "llm": "transform",
    "web": "web-fetch",
}

DOC_BASE_URL = "https://onetool.beycom.online/reference/tools/"

__all__ = [
    "PACK_NAME",
    "aliases",
    "config",
    "get_ot_pack_functions",
    "health",
    "help",
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
        "help": help,
        "stats": stats,
        "notify": notify,
        "reload": reload,
    }


# ============================================================================
# Help Function Utilities
# ============================================================================


def _get_doc_url(pack: str) -> str:
    """Get documentation URL for a pack.

    Args:
        pack: Pack name (e.g., "brave", "firecrawl")

    Returns:
        Documentation URL for the pack
    """
    slug = DOC_SLUGS.get(pack, pack)
    return f"{DOC_BASE_URL}{slug}/"


def _fuzzy_match(query: str, candidates: list[str], threshold: float = 0.4) -> list[str]:
    """Return candidates that fuzzy match query, sorted by score.

    Args:
        query: Search query string
        candidates: List of candidate strings to match against
        threshold: Minimum similarity ratio (0.0 to 1.0) for fuzzy matches

    Returns:
        List of matching candidates, sorted by match score (best first)
    """
    from difflib import SequenceMatcher

    query_lower = query.lower()
    scored: list[tuple[str, float]] = []

    for candidate in candidates:
        candidate_lower = candidate.lower()
        # Substring match gets high score
        if query_lower in candidate_lower:
            scored.append((candidate, 1.0))
        else:
            ratio = SequenceMatcher(None, query_lower, candidate_lower).ratio()
            if ratio >= threshold:
                scored.append((candidate, ratio))

    return [c for c, _ in sorted(scored, key=lambda x: -x[1])]


def _format_general_help() -> str:
    """Format general help overview shown when no query is provided.

    Returns:
        Formatted help text with discovery commands, info levels, and examples
    """
    return """# OneTool Help

## Discovery
  ot.tools()              - List all tools
  ot.tools(pattern="web") - Filter by pattern
  ot.packs()              - List all packs
  ot.snippets()           - List all snippets
  ot.aliases()            - List all aliases
  ot.help(query="..")     - Search for help

## Info Levels
  info="list" - Names only
  info="min"  - Name + description (default)
  info="full" - Everything

## Quick Examples
  brave.search(query="AI news")
  web.fetch(url="https://...")
  $b_q q=search terms

## Tips
  - Use keyword args: func(arg=value)
  - Batch when possible: func(items=[...])"""


def _format_tool_help(tool_info: dict[str, Any], pack: str) -> str:
    """Format detailed help for a single tool.

    Args:
        tool_info: Tool info dict from _build_tool_info with info="full"
        pack: Pack name for documentation URL

    Returns:
        Formatted tool help text
    """
    lines = [f"# {tool_info['name']}", ""]

    if tool_info.get("description"):
        lines.append(tool_info["description"])
        lines.append("")

    if tool_info.get("signature"):
        lines.append("## Signature")
        lines.append(tool_info["signature"])
        lines.append("")

    if tool_info.get("args"):
        lines.append("## Arguments")
        for arg in tool_info["args"]:
            lines.append(f"- {arg}")
        lines.append("")

    if tool_info.get("returns"):
        lines.append("## Returns")
        lines.append(tool_info["returns"])
        lines.append("")

    if tool_info.get("example"):
        lines.append("## Example")
        lines.append(tool_info["example"])
        lines.append("")

    lines.append("## Docs")
    lines.append(_get_doc_url(pack))

    return "\n".join(lines)


def _format_pack_help(pack_name: str, pack_info: str) -> str:
    """Format detailed help for a pack.

    Args:
        pack_name: Name of the pack
        pack_info: Pack info string from packs(info="full")

    Returns:
        Formatted pack help text with doc URL appended
    """
    lines = [pack_info, "", "## Docs", _get_doc_url(pack_name)]
    return "\n".join(lines)


def _format_snippet_help(snippet_info: str) -> str:
    """Format detailed help for a snippet.

    Args:
        snippet_info: Snippet info string from snippets(info="full")

    Returns:
        Formatted snippet help text
    """
    return f"# Snippet\n\n{snippet_info}"


def _format_alias_help(alias_name: str, target: str) -> str:
    """Format detailed help for an alias.

    Args:
        alias_name: Name of the alias
        target: Target function the alias maps to

    Returns:
        Formatted alias help text
    """
    lines = [
        f"# Alias: {alias_name}",
        "",
        f"Maps to: `{target}`",
        "",
        "Use this alias as a shorthand for the target function.",
    ]
    return "\n".join(lines)


def _item_matches(item: dict[str, Any] | str, matched_names: list[str], key: str = "name") -> bool:
    """Check if item name is in matched_names list.

    Args:
        item: Either a string name or dict with name key
        matched_names: List of matched name strings
        key: Dict key to extract name from (default: "name")

    Returns:
        True if item's name is in matched_names
    """
    if isinstance(item, str):
        # For "name: desc" or "name -> target" formats, extract the name part
        if ": " in item:
            name = item.split(":")[0]
        elif " ->" in item:
            name = item.split(" ->")[0]
        else:
            name = item
        return name in matched_names
    return item.get(key) in matched_names


def _snippet_matches(item: dict[str, Any] | str, matched_names: list[str]) -> bool:
    """Check if snippet item matches any of the matched names.

    Args:
        item: Either a string or dict snippet item
        matched_names: List of matched snippet name strings

    Returns:
        True if snippet matches
    """
    if not matched_names:
        return False
    if isinstance(item, str):
        name = item.split(":")[0]
        if name in matched_names:
            return True
        return any(item == m or item.startswith(m + ":") for m in matched_names)
    return item.get("name") in matched_names


def _format_search_results(
    query: str,
    tools_results: list[dict[str, Any] | str],
    packs_results: list[dict[str, Any] | str],
    snippets_results: list[dict[str, Any] | str],
    aliases_results: list[dict[str, Any] | str],
    info: InfoLevel,
) -> str:
    """Format search results grouped by type.

    Args:
        query: Original search query
        tools_results: Matching tools
        packs_results: Matching packs
        snippets_results: Matching snippets
        aliases_results: Matching aliases
        info: Output verbosity level

    Returns:
        Formatted search results text
    """
    lines = [f'# Search results for "{query}"', ""]

    if tools_results:
        lines.append("## Tools")
        for tool in tools_results:
            if isinstance(tool, str):
                lines.append(f"- {tool}")
            elif info == "min":
                lines.append(f"- {tool['name']}: {tool.get('description', '')}")
            else:
                lines.append(f"- {tool['name']}")
        lines.append("")

    if packs_results:
        lines.append("## Packs")
        for pack in packs_results:
            if isinstance(pack, str):
                lines.append(f"- {pack}")
            elif info == "min":
                lines.append(f"- {pack['name']} ({pack.get('tool_count', 0)} tools)")
            else:
                lines.append(f"- {pack['name']}")
        lines.append("")

    if snippets_results:
        lines.append("## Snippets")
        for snippet in snippets_results:
            if isinstance(snippet, str):
                # For info="min", format is "name: description"
                lines.append(f"- ${snippet.split(':')[0]}" if ":" not in snippet else f"- ${snippet}")
            else:
                lines.append(f"- ${snippet}")
        lines.append("")

    if aliases_results:
        lines.append("## Aliases")
        for alias in aliases_results:
            if isinstance(alias, str):
                lines.append(f"- {alias}")
            else:
                lines.append(f"- {alias['name']} -> {alias['target']}")
        lines.append("")

    if not any([tools_results, packs_results, snippets_results, aliases_results]):
        lines.append("No matches found.")
        lines.append("")
        lines.append("Try browsing with:")
        lines.append("  ot.tools()    - List all tools")
        lines.append("  ot.packs()    - List all packs")
        lines.append("  ot.snippets() - List all snippets")
        lines.append("  ot.aliases()  - List all aliases")

    return "\n".join(lines).rstrip()


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
    full_name: str, func: Any, source: str, info: InfoLevel
) -> dict[str, Any] | str:
    """Build tool info dict for a single tool.

    Args:
        full_name: Full tool name (e.g., "brave.search")
        func: The function object
        source: Source identifier (e.g., "local", "proxy:github")
        info: Output verbosity level ("list", "min", "full")

    Returns:
        Tool name string if info="list", otherwise dict with tool info
    """
    if info == "list":
        return full_name

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

    if info == "min":
        return {"name": full_name, "description": description}

    # info == "full"
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
    info: InfoLevel,
) -> dict[str, Any] | str:
    """Build tool info dict for a proxy tool using its input schema.

    Args:
        full_name: Full tool name (e.g., "github.search")
        description: Tool description from MCP server
        input_schema: JSON Schema for tool input
        source: Source identifier (e.g., "proxy:github")
        info: Output verbosity level ("list", "min", "full")

    Returns:
        Tool name string if info="list", otherwise dict with tool info
    """
    if info == "list":
        return full_name

    if info == "min":
        return {"name": full_name, "description": description}

    # info == "full"
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
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List all available tools with optional filtering.

    Lists registered local tools and proxied MCP server tools.
    Use pattern for substring filtering.

    Args:
        pattern: Filter tools by name pattern (case-insensitive substring match)
        info: Output verbosity level - "list" (names only), "min" (name + description),
              or "full" (complete details including args, returns, example)

    Returns:
        List of tool names (info="list") or tool dicts (info="min"/"full")

    Example:
        ot.tools()
        ot.tools(pattern="search")
        ot.tools(pattern="brave.")
        ot.tools(info="list")
        ot.tools(pattern="brave.search", info="full")
    """
    from ot.executor.tool_loader import load_tool_registry

    with log("ot.tools", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        tools_list: list[dict[str, Any] | str] = []

        # Local tools from registry
        from ot.executor.worker_proxy import WorkerPackProxy

        for pack_name, pack_funcs in runner_registry.packs.items():
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

                tools_list.append(_build_tool_info(full_name, func, "local", info))

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            tool_name = f"{proxy_tool.server}.{proxy_tool.name}"

            if pattern and pattern.lower() not in tool_name.lower():
                continue

            tools_list.append(
                _build_proxy_tool_info(
                    tool_name,
                    proxy_tool.description or "",
                    proxy_tool.input_schema,
                    f"proxy:{proxy_tool.server}",
                    info,
                )
            )

        # Sort by name (handle both str and dict)
        tools_list.sort(key=lambda t: t if isinstance(t, str) else t["name"])
        s.add("count", len(tools_list))
        return tools_list


def packs(
    *,
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List all packs with optional filtering.

    Lists all available packs (local and proxy).
    Use pattern for substring filtering.

    Args:
        pattern: Filter packs by name pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name + source + tool_count),
              or "full" (detailed info with instructions and tool list)

    Returns:
        List of pack names (info="list") or pack dicts/strings (info="min"/"full")

    Example:
        ot.packs()
        ot.packs(pattern="brav")
        ot.packs(info="list")
        ot.packs(pattern="brave", info="full")
    """
    from ot.executor.tool_loader import load_tool_registry
    from ot.prompts import PromptsError, get_pack_instructions, get_prompts

    with log("ot.packs", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Collect all packs
        local_packs = set(runner_registry.packs.keys())
        proxy_packs = set(proxy.servers)
        all_pack_names = sorted(local_packs | proxy_packs)

        # Filter by pattern
        if pattern:
            all_pack_names = [p for p in all_pack_names if pattern.lower() in p.lower()]

        # info="list" - just names
        if info == "list":
            s.add("count", len(all_pack_names))
            return all_pack_names  # type: ignore[return-value]

        # info="full" - detailed info for each matching pack
        if info == "full":
            results: list[dict[str, Any] | str] = []
            for pack_name in all_pack_names:
                is_local = pack_name in local_packs

                # Build detailed pack info
                lines = [f"# {pack_name} pack", ""]

                # Get instructions
                try:
                    prompts_config = get_prompts()
                    configured = get_pack_instructions(prompts_config, pack_name)
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

                    pack_funcs = runner_registry.packs[pack_name]
                    if isinstance(pack_funcs, WorkerPackProxy):
                        func_items = [(n, getattr(pack_funcs, n)) for n in pack_funcs.functions]
                    else:
                        func_items = list(pack_funcs.items())

                    for func_name, func in sorted(func_items):
                        doc = func.__doc__ or "(no description)"
                        first_line = doc.split("\n")[0].strip()
                        lines.append(f"- **{pack_name}.{func_name}**: {first_line}")
                else:
                    proxy_tools = proxy.list_tools(server=pack_name)
                    for tool in sorted(proxy_tools, key=lambda t: t.name):
                        desc = tool.description or "(no description)"
                        first_line = desc.split("\n")[0].strip()
                        lines.append(f"- **{pack_name}.{tool.name}**: {first_line}")

                results.append("\n".join(lines))

            s.add("count", len(results))
            return results

        # info="min" (default) - summary for each pack
        packs_list: list[dict[str, Any] | str] = []

        for pack_name in all_pack_names:
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
        import ot.config.secrets
        import ot.prompts
        import ot.registry

        # Clear config cache
        ot.config.loader._config = None

        # Clear prompts cache
        ot.prompts._prompts = None

        # Clear secrets cache
        ot.config.secrets._secrets = None
        ot.config.secrets._early_secrets = None

        # Clear tool registry cache (will rescan on next access)
        ot.registry._registry = None

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
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List aliases with optional filtering.

    Lists all configured aliases.
    Use pattern for substring filtering.

    Args:
        pattern: Filter aliases by name or target pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name -> target),
              or "full" (structured dict with name and target)

    Returns:
        List of alias names, strings, or dicts depending on info level

    Example:
        ot.aliases()
        ot.aliases(pattern="search")
        ot.aliases(info="list")
        ot.aliases(pattern="ws", info="full")
    """
    with log("ot.aliases", pattern=pattern or None, info=info) as s:
        cfg = get_config()

        if not cfg.alias:
            s.add("count", 0)
            return []

        # Filter by pattern or list all
        items = sorted(cfg.alias.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [(k, v) for k, v in items if pattern_lower in k.lower() or pattern_lower in v.lower()]

        s.add("count", len(items))

        # info="list" - just names
        if info == "list":
            return [k for k, v in items]

        # info="full" - structured dicts
        if info == "full":
            return [{"name": k, "target": v} for k, v in items]

        # info="min" (default) - "name -> target" strings
        return [f"{k} -> {v}" for k, v in items]


def snippets(
    *,
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List snippets with optional filtering.

    Lists all configured snippets.
    Use pattern for substring filtering.

    Args:
        pattern: Filter snippets by name/description pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name: description),
              or "full" (complete definition with params, body, example)

    Returns:
        List of snippet names, strings, or dicts depending on info level

    Example:
        ot.snippets()
        ot.snippets(pattern="pkg")
        ot.snippets(info="list")
        ot.snippets(pattern="brv_research", info="full")
    """
    with log("ot.snippets", pattern=pattern or None, info=info) as s:
        cfg = get_config()

        if not cfg.snippets:
            s.add("count", 0)
            return []

        # Filter by pattern or list all
        items = sorted(cfg.snippets.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [
                (k, v) for k, v in items
                if pattern_lower in k.lower() or pattern_lower in (v.description or "").lower()
            ]

        s.add("count", len(items))

        # info="list" - just names
        if info == "list":
            return [k for k, v in items]

        # info="full" - complete definition for each snippet
        if info == "full":
            results: list[dict[str, Any] | str] = []
            for snippet_name, snippet_def in items:
                # Format output as YAML-like
                lines = [f"name: {snippet_name}"]

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
                    lines.append(f"# ${snippet_name} {' '.join(example_args)}")
                else:
                    lines.append(f"# ${snippet_name}")

                results.append("\n".join(lines))

            return results

        # info="min" (default) - "name: description" strings
        return [f"{k}: {v.description or '(no description)'}" for k, v in items]


# ============================================================================
# Help Function
# ============================================================================


def help(*, query: str = "", info: InfoLevel = "min") -> str:
    """Get help on OneTool commands, tools, packs, snippets, or aliases.

    Provides a unified entry point for discovering and getting help on
    any OneTool component. With no arguments, shows a general overview.
    With a query, searches across all types and returns detailed help.

    Args:
        query: Tool name, pack name, snippet, alias, or search term.
               Empty string shows general help overview.
        info: Detail level - "list" (names only), "min" (name + description),
              "full" (everything). Default is "min".

    Returns:
        Formatted help text

    Example:
        ot.help()
        ot.help(query="brave.search")
        ot.help(query="firecrawl")
        ot.help(query="$b_q")
        ot.help(query="web fetch", info="list")
    """
    with log("ot.help", query=query or None, info=info) as s:
        # No query - show general help
        if not query:
            s.add("type", "general")
            return _format_general_help()

        cfg = get_config()

        # Check for exact tool match (contains ".")
        if "." in query:
            tool_results = tools(pattern=query, info="full")
            # Look for exact match
            for tool in tool_results:
                if isinstance(tool, dict) and tool.get("name") == query:
                    pack = query.split(".")[0]
                    s.add("type", "tool")
                    s.add("match", query)
                    return _format_tool_help(tool, pack)

        # Check for exact pack match
        pack_names = packs(info="list")
        if query in pack_names:
            pack_results = packs(pattern=query, info="full")
            if pack_results:
                s.add("type", "pack")
                s.add("match", query)
                return _format_pack_help(query, str(pack_results[0]))

        # Check for snippet match (starts with "$")
        if query.startswith("$"):
            snippet_name = query[1:]  # Remove "$"
            snippet_results = snippets(pattern=snippet_name, info="full")
            # Look for exact match
            for snippet in snippet_results:
                if isinstance(snippet, str) and snippet.startswith(f"name: {snippet_name}"):
                    s.add("type", "snippet")
                    s.add("match", query)
                    return _format_snippet_help(snippet)

        # Check for exact alias match
        if cfg.alias and query in cfg.alias:
            target = cfg.alias[query]
            s.add("type", "alias")
            s.add("match", query)
            return _format_alias_help(query, target)

        # Fuzzy search across all types
        s.add("type", "search")

        # Get all candidates for fuzzy matching
        all_tool_names = tools(info="list")
        all_pack_names = pack_names  # Already have this
        all_snippet_names = snippets(info="list")
        all_alias_names = aliases(info="list")

        # Fuzzy match across types
        matched_tools = _fuzzy_match(query, [str(t) for t in all_tool_names])
        matched_packs = _fuzzy_match(query, [str(p) for p in all_pack_names])
        matched_snippets = _fuzzy_match(query, [str(sn) for sn in all_snippet_names])
        matched_aliases = _fuzzy_match(query, [str(a) for a in all_alias_names])

        total_matches = len(matched_tools) + len(matched_packs) + len(matched_snippets) + len(matched_aliases)
        s.add("matches", total_matches)

        # Show search results - info parameter controls detail level
        tools_results = [t for t in tools(info=info) if _item_matches(t, matched_tools)]
        packs_results = [p for p in packs(info=info) if _item_matches(p, matched_packs)]
        snippets_results = [sn for sn in snippets(info=info) if _snippet_matches(sn, matched_snippets)]
        aliases_results = [a for a in aliases(info=info) if _item_matches(a, matched_aliases)]

        return _format_search_results(
            query=query,
            tools_results=tools_results,
            packs_results=packs_results,
            snippets_results=snippets_results,
            aliases_results=aliases_results,
            info=info,
        )
