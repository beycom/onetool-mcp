"""Help formatting utilities for ot.help()."""

from __future__ import annotations

from typing import Any

from ot.meta._constants import (
    DOC_BASE_URL,
    InfoLevel,
)
from ot.meta._constants import (
    safe_server_name as _safe_server_name,
)


def _get_doc_url(pack: str) -> str:
    """Get documentation URL for a pack.

    Args:
        pack: Pack name (e.g., "brave", "file")

    Returns:
        Documentation URL for the pack
    """
    try:
        from ot.executor.tool_loader import load_tool_registry

        slug = load_tool_registry().doc_slugs.get(pack, pack)
    except Exception:
        slug = pack
    return f"{DOC_BASE_URL}{slug}/"


def _fuzzy_match(query: str, candidates: list[str], threshold: float = 0.6) -> list[str]:
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

## First 60 Seconds
  ot.status()                   - Check runtime status
  ot.help(query="task")         - Find right tool for goal
  ot.servers()                  - Check MCP proxy server status
  ot_servers.enable(name="playwright") - Enable disconnected server
  ot.tool_info(name="pack.tool") - Confirm signature + args

## Discovery
  ot.tools()                    - List all tools
  ot.tools(pattern="webfetch")  - Filter by pattern
  ot.tool_info(name="brave.search") - Signature + args for a tool
  ot.packs()                    - List all packs (local + MCP)
  ot.pack_info(name="brave")    - Pack details + instructions
  ot.servers()                  - List MCP proxy servers
  ot_servers.enable(name="...") - Enable + connect a proxy server
  ot.snippets()                 - List all snippets
  ot.snippet_info(name="brv")   - Snippet details
  ot.aliases()                  - List all aliases
  ot.help(query="..")           - Search for help

## Info Levels
  info="min"     - Names only
  info="default" - Name + description (default)
  info="full"    - Full list view; use detail helpers for signatures

List commands stay compact. Use ot.tool_info(name="pack.tool") for signatures
and args, and ot.pack_info(name="pack") for pack instructions.

## Quick Examples
  brave.search(query="AI news")
  webfetch.fetch(url="https://...")
  :b_q q=search terms

## Tips
  - Use keyword args: func(arg=value)
  - Batch when possible: func(items=[...])"""


def _is_server_intent_query(query: str) -> bool:
    """Return True when query suggests proxy/server connectivity intent."""
    q = query.lower()
    keywords = (
        "proxy",
        "server",
        "mcp",
        "enable",
        "disable",
        "connect",
        "connection",
        "disconnected",
        "playwright",
        "chrome_devtools",
    )
    return any(k in q for k in keywords)


def _is_direct_run_query(query: str) -> bool:
    """Return True when query asks about direct OneTool run invocation."""
    q = query.lower().strip()
    exact_terms = {
        "__run",
        "__r",
        "__ot",
        "run",
        "mcp run",
        "run tool",
        "direct run",
        "direct command",
        "direct invocation",
        "onetool run",
        "snippet",
        "snippets",
    }
    if q in exact_terms:
        return True
    keywords = (
        "__run",
        "__r",
        "__ot",
        "mcp run",
        "direct onetool",
        "direct invocation",
        "direct command",
        "colon snippet",
        "snippet syntax",
    )
    return any(k in q for k in keywords)


def _format_direct_run_help() -> str:
    """Format deterministic help for direct OneTool run invocation."""
    return """# Direct OneTool Invocation

Use MCP `run(command='...')` for direct OneTool pack calls from a connected agent.
Use the `onetool direct` CLI only when you explicitly want the CLI workflow.

## Triggers
  __run <code>       - canonical user-facing trigger
  __r <code>         - short alias
  __ot <code>        - OneTool alias

## Call Shapes
  pack.tool(arg=value)     - direct tool call
  :snippet key=value       - snippet invocation

Use direct pack syntax such as `ground.search(q='price of gold')`, not `ot.ground.search(...)`.
Snippet values are plain strings until the template renders Python.

## Discovery
  ot.tool_info(name='pack.tool') - confirm exact signature and arguments
  ot.help(query='topic')         - search tools, packs, snippets, aliases, and servers
  ot.servers()                   - check proxy server status

Do not guess tool names, argument names, or allowed values. If they are unknown, inspect first.
For a known disconnected proxy server, run `ot_servers.enable(name='playwright')` then retry once."""


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


def _format_pack_help(pack_name: str, pack_info: dict[str, Any]) -> str:
    """Format detailed help for a pack.

    Args:
        pack_name: Name of the pack
        pack_info: Pack info dict from pack_info()

    Returns:
        Formatted pack help text
    """
    lines = [f"# {pack_name} pack", ""]

    source = pack_info.get("source", "local")
    lines.append(f"**Type:** {'Local' if source == 'local' else 'MCP Proxy Server'}")
    lines.append("")

    description = pack_info.get("description", "")
    if description and description != "(no description)":
        lines.append(description)
        lines.append("")

    instructions = pack_info.get("instructions", "")
    if instructions:
        lines.append("## Instructions")
        lines.append("")
        lines.append(instructions.strip())
        lines.append("")

    tool_names = pack_info.get("tool_names", [])
    if tool_names:
        lines.append("## Tools")
        lines.append("")
        for tn in tool_names:
            lines.append(f"- {tn}")
        lines.append("")

    lines.append("## Docs")
    lines.append(_get_doc_url(pack_name))

    return "\n".join(lines)


def _format_snippet_help(snippet_info: dict[str, Any]) -> str:
    """Format detailed help for a snippet.

    Args:
        snippet_info: Snippet info dict from snippet_info()

    Returns:
        Formatted snippet help text
    """
    name = snippet_info.get("name", "")
    lines = [f"# Snippet: {name}", ""]

    desc = snippet_info.get("description", "")
    if desc and desc != "(no description)":
        lines.append(desc)
        lines.append("")

    params = snippet_info.get("params", {})
    if params:
        lines.append("## Parameters")
        lines.append("")
        for param_name, param_def in params.items():
            if isinstance(param_def, dict):
                default = param_def.get("default")
                desc_p = param_def.get("description", "")
                param_str = f"- `{param_name}`"
                if default is not None:
                    param_str += f" (default: {default!r})"
                if desc_p:
                    param_str += f" — {desc_p}"
                lines.append(param_str)
            else:
                lines.append(f"- `{param_name}`")
        lines.append("")

    body = snippet_info.get("body", "")
    if body:
        lines.append("## Body")
        lines.append("```python")
        lines.append(body.rstrip())
        lines.append("```")
        lines.append("")

    example = snippet_info.get("example", "")
    if example:
        lines.append("## Example")
        lines.append(f"`{example}`")

    return "\n".join(lines)


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


def _format_server_help(
    server_name: str,
    server_cfg: Any,
    status: str,
    tools: list[Any],
    native_instructions: str = "",
) -> str:
    """Format detailed help for an MCP proxy server.

    Args:
        server_name: Config key for the server (e.g. 'chrome_devtools').
        server_cfg: McpServerConfig for this server.
        status: 'connected' or 'disconnected'.
        tools: List of ProxyToolInfo objects (from proxy.list_tools).
        native_instructions: Instructions from the server's InitializeResult.

    Returns:
        Formatted server help markdown.
    """
    safe_name = _safe_server_name(server_name)
    tool_count = len(tools)
    lines = [f"# {server_name} server", ""]

    if safe_name != server_name:
        lines.append(f"**Call as:** `{safe_name}`")
    lines.append(
        f"**Status:** {status}" + (f" ({tool_count} tools)" if tool_count else "")
    )
    source = getattr(server_cfg, "source", None)
    if source:
        lines.append(f"**Source:** {source}")
    lines.append("")

    # Layer instructions: native MCP first, then servers.yaml additions
    yaml_instructions = (getattr(server_cfg, "instructions", None) or "").strip()
    combined = "\n\n".join(filter(None, [native_instructions.strip(), yaml_instructions]))
    if combined:
        lines.append("## Instructions")
        lines.append("")
        lines.append(combined)
        lines.append("")

    if tools:
        lines.append(f"## Tools ({tool_count})")
        lines.append("")
        for tool in sorted(tools, key=lambda t: t.name):
            desc = tool.description or "(no description)"
            first_line = desc.split("\n")[0].strip()
            lines.append(f"- **{safe_name}.{tool.name}**: {first_line}")

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
        return item in matched_names
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
        return item in matched_names
    return item.get("name") in matched_names


def _format_search_results(
    query: str,
    tools_results: list[dict[str, Any] | str],
    packs_results: list[dict[str, Any] | str],
    snippets_results: list[dict[str, Any] | str],
    aliases_results: list[dict[str, Any] | str],
    info: InfoLevel,
    servers_results: list[str] | None = None,
) -> str:
    """Format search results grouped by type.

    Args:
        query: Original search query
        tools_results: Matching tools
        packs_results: Matching packs
        snippets_results: Matching snippets
        aliases_results: Matching aliases
        info: Output verbosity level
        servers_results: Matching server names (optional)

    Returns:
        Formatted search results text
    """
    lines = [f'# Search results for "{query}"', ""]

    if tools_results:
        lines.append("## Tools")
        for tool in tools_results:
            if isinstance(tool, str):
                lines.append(f"- {tool}")
            elif info == "default":
                lines.append(f"- {tool['name']}: {tool.get('description', '')}")
            else:
                lines.append(f"- {tool['name']}")
        lines.append("")

    if packs_results:
        lines.append("## Packs")
        for pack in packs_results:
            if isinstance(pack, str):
                lines.append(f"- {pack}")
            elif info == "default":
                desc = pack.get("description", "")
                if desc and desc != "(no description)":
                    lines.append(f"- {pack['name']}: {desc}")
                else:
                    lines.append(f"- {pack['name']}")
            else:
                lines.append(f"- {pack['name']}")
        lines.append("")

    if snippets_results:
        lines.append("## Snippets")
        for snippet in snippets_results:
            if isinstance(snippet, str):
                lines.append(f"- :{snippet}")
            elif isinstance(snippet, dict):
                name = snippet.get("name", "")
                desc = snippet.get("description", "")
                if desc and desc != "(no description)" and info == "default":
                    lines.append(f"- :{name}: {desc}")
                else:
                    lines.append(f"- :{name}")
        lines.append("")

    if aliases_results:
        lines.append("## Aliases")
        for alias in aliases_results:
            if isinstance(alias, str):
                lines.append(f"- {alias}")
            else:
                lines.append(f"- {alias['name']} -> {alias['target']}")
        lines.append("")

    if servers_results:
        lines.append("## Servers")
        for server in servers_results:
            lines.append(f"- {server}")
        lines.append("")

    if not any([tools_results, packs_results, snippets_results, aliases_results, servers_results]):
        lines.append("No matches found.")
        lines.append("")
        if _is_server_intent_query(query):
            lines.append("Try proxy recovery:")
            lines.append("  ot_servers.enable(name=\"playwright\")  - Enable + connect known server")
            lines.append("  ot.servers()                       - Use only if server name/status unknown")
            lines.append("  ot.help(query=\"playwright\")  - See server tools + guidance")
            lines.append("")
        lines.append("Try browsing with:")
        lines.append("  ot.tools()    - List all tools")
        lines.append("  ot.packs()    - List all packs (local + MCP)")
        lines.append("  ot.servers()  - List MCP proxy servers")
        lines.append("  ot.snippets() - List all snippets")
        lines.append("  ot.aliases()  - List all aliases")

    return "\n".join(lines).rstrip()
