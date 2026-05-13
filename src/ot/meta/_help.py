"""Unified help entry point."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Literal

from ot.config import get_config
from ot.logging import LogSpan
from ot.meta._discovery import _resolve_pack_alias, packs, servers, tools
from ot.meta._help_formatting import (
    _format_alias_help,
    _format_general_help,
    _format_pack_help,
    _format_search_results,
    _format_server_help,
    _format_snippet_help,
    _format_tool_help,
    _fuzzy_match,
    _item_matches,
    _snippet_matches,
)
from ot.meta._introspection import aliases, snippets

log = LogSpan

_VALID_HELP_INFO = {"min", "default", "full"}
HelpInfoLevel = Literal["min", "default", "full"]


def _score_candidate(query: str, candidate: str) -> float:
    """Score candidate text against a query."""
    query_l = query.lower().strip()
    cand_l = candidate.lower().strip()
    if not query_l or not cand_l:
        return 0.0
    if query_l in cand_l:
        return 1.0
    return SequenceMatcher(None, query_l, cand_l).ratio()


def _score_named_result(query: str, name: str, description: str = "") -> float:
    """Score a named item using both name and description."""
    name_score = _score_candidate(query, name)
    desc_score = _score_candidate(query, description)

    # Description matches should surface, but names remain strongest.
    best = max(name_score, desc_score * 0.95)

    # Token coverage gives partial credit for multi-word intent queries.
    query_terms = [t for t in query.lower().split() if t]
    if query_terms:
        haystack = f"{name} {description}".lower()
        covered = sum(1 for term in query_terms if term in haystack)
        if covered:
            coverage = covered / len(query_terms)
            best = max(best, 0.65 + (0.25 * coverage))

    return best


def _rank_named_items(
    query: str, items: list[dict[str, Any] | str], *, desc_key: str = "description", threshold: float = 0.6
) -> list[str]:
    """Return matched item names sorted by score (best first)."""
    scored: list[tuple[str, float]] = []
    for item in items:
        if isinstance(item, str):
            name = item
            description = ""
        else:
            name = str(item.get("name", ""))
            description = str(item.get(desc_key, "") or "")
        score = _score_named_result(query, name, description)
        if score >= threshold:
            scored.append((name, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored]


def help(*, query: str = "", info: HelpInfoLevel = "default") -> str:
    """Get help on OneTool commands, tools, packs, snippets, or aliases.

    Provides a unified entry point for discovering and getting help on
    any OneTool component. With no arguments, shows a general overview.
    With a query, searches across all types and returns detailed help.

    Args:
        query: Tool name, pack name, snippet, alias, or search term.
               Empty string shows general help overview.
        info: Detail level - "min" (names only), "default" (name + description,
              default), "full" (everything).

    Returns:
        Formatted help text

    Example:
        ot.help()
        ot.help(query="brave.search")
        ot.help(query="brave")
        ot.help(query="$b_q")
        ot.help(query="web fetch", info="min")
    """
    if info not in _VALID_HELP_INFO:
        raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

    with log(span="ot.help", query=query or None, info=info) as s:
        # No query - show general help
        if not query:
            s.add("type", "general")
            return _format_general_help()

        cfg = get_config()

        # Check for exact tool match (contains "."); resolve short alias prefix
        if "." in query:
            from ot.meta._discovery import tool_info as _tool_info
            pack_prefix, _, tool_suffix = query.partition(".")
            from ot.executor.tool_loader import load_tool_registry

            resolved_pack = _resolve_pack_alias(pack_prefix, load_tool_registry())
            resolved_tool_query = f"{resolved_pack}.{tool_suffix}"
            detail = _tool_info(name=resolved_tool_query, info="full")
            if detail:
                assert isinstance(detail, dict)
                pack = resolved_tool_query.split(".")[0]
                s.add("type", "tool")
                s.add("match", resolved_tool_query)
                return _format_tool_help(detail, pack)

        # Check for exact server match (MCP proxy servers).
        # Try exact, then normalize hyphens→underscores (canonical form),
        # then underscores→hyphens (backward compat for old user configs).
        query_as_server = next(
            (q for q in [query, query.replace("-", "_"), query.replace("_", "-")]
             if q in cfg.servers),
            None,
        )
        if query_as_server is not None:
            from ot.proxy import get_proxy_manager as _get_proxy_mgr
            _proxy = _get_proxy_mgr()
            server_cfg = cfg.servers[query_as_server]
            conn = _proxy.get_connection(query_as_server)
            status = "connected" if conn else "disconnected"
            proxy_tools = _proxy.list_tools(server=query_as_server) if conn else []
            native_instructions = _proxy.get_server_instructions(query_as_server)
            s.add("type", "server")
            s.add("match", query_as_server)
            return _format_server_help(
                query_as_server, server_cfg, status, proxy_tools, native_instructions
            )

        # Check for exact pack match (also resolves short aliases like "img" → "ot_image")
        from ot.executor.tool_loader import load_tool_registry

        resolved_query = _resolve_pack_alias(query, load_tool_registry())

        pack_names = packs(info="min")
        if resolved_query in pack_names:
            from ot.meta._discovery import pack_info as _pack_info
            pi = _pack_info(name=resolved_query, info="default")
            if pi and "error" not in pi:
                s.add("type", "pack")
                s.add("match", resolved_query)
                return _format_pack_help(resolved_query, pi)

        # Check for snippet match (starts with "$")
        if query.startswith("$"):
            snippet_name = query[1:]  # Remove "$"
            from ot.meta._introspection import snippet_info as _snippet_info
            si = _snippet_info(name=snippet_name, info="full")
            if "error" not in si:
                assert isinstance(si, dict)
                s.add("type", "snippet")
                s.add("match", query)
                return _format_snippet_help(si)

        # Check for exact alias match
        if cfg.alias and query in cfg.alias:
            target = cfg.alias[query]
            s.add("type", "alias")
            s.add("match", query)
            return _format_alias_help(query, target)

        # Fuzzy search across all types
        s.add("type", "search")

        # Fetch once at default level — used for both name extraction and display
        all_tools = tools()
        all_packs = packs()
        all_snippets = snippets()
        all_aliases = aliases()
        all_server_names: list[str] = servers(info="min")  # type: ignore[assignment]

        # Fuzzy match across types (name + description where available)
        matched_tools = _rank_named_items(query, all_tools)
        matched_packs = _rank_named_items(query, all_packs)
        matched_snippets = _rank_named_items(query, all_snippets)
        matched_aliases = _rank_named_items(query, all_aliases, desc_key="target")
        matched_servers = _fuzzy_match(query, all_server_names)

        total_matches = (
            len(matched_tools) + len(matched_packs) + len(matched_snippets)
            + len(matched_aliases) + len(matched_servers)
        )
        s.add("matches", total_matches)

        # Filter from already-fetched results — no additional discovery calls
        tools_results = [t for t in all_tools if _item_matches(t, matched_tools)]
        packs_results = [p for p in all_packs if _item_matches(p, matched_packs)]
        snippets_results = [sn for sn in all_snippets if _snippet_matches(sn, matched_snippets)]
        aliases_results = [a for a in all_aliases if _item_matches(a, matched_aliases)]
        servers_results = [n for n in all_server_names if n in matched_servers]

        return _format_search_results(
            query=query,
            tools_results=tools_results,
            packs_results=packs_results,
            snippets_results=snippets_results,
            aliases_results=aliases_results,
            info=info,
            servers_results=servers_results,
        )
