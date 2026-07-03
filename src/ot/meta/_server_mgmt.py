"""Server management and security functions."""

from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

log = LogSpan


def security(*, check: str = "") -> dict[str, Any]:
    """Check security rules for code validation.

    OneTool uses an allowlist-based security model: everything is blocked
    by default, and only explicitly allowed builtins, imports, and calls
    are permitted. Tool namespaces (ot.*, brave.*, etc.) are auto-allowed.

    Args:
        check: Pattern to check (e.g., "os", "json.loads", "pickle.*").
               If empty, returns a summary of all security rules.

    Returns:
        If check is provided: Dict with 'pattern', 'status' (allowed/blocked/warned),
            'category', and 'reason' explaining why.
        If check is empty: Dict with summary of all security categories
            (builtins, imports, calls, dunders, tool_namespaces).

    Example:
        ot.security()                      # Show all rules
        ot.security(check="os")            # "blocked: import"
        ot.security(check="json")          # "allowed: import"
        ot.security(check="json.loads")    # "allowed: module in imports"
        ot.security(check="pickle.load")   # "blocked: calls"
        ot.security(check="brave.search")  # "allowed: tool namespace"
    """
    from ot.executor.validator import get_security_status, get_security_summary

    with log(span="ot.security", check=check or None) as s:
        if check:
            result = get_security_status(check)
            s.add("status", result["status"])
            s.add("category", result["category"])
            return result
        else:
            summary = get_security_summary()
            s.add("status", summary.get("status", "unknown"))
            return summary


def server(
    *,
    status: str | None = None,
) -> str:
    """List or inspect runtime proxy server state.

    Without arguments, lists all configured servers with their status.
    For state changes, use `ot_servers.enable/disable/restart`.

    Args:
        status: Show detailed status for a named server

    Returns:
        Status report

    Example:
        ot.server()                           # list all servers
        ot.server(status="devtools")          # show status for devtools
        ot_servers.enable(name="playwright")  # enable + connect a server
        ot_servers.disable(name="playwright") # disable + disconnect
        ot_servers.restart(name="playwright") # reconnect server
    """
    from ot.meta._server_services import server as _server

    return _server(status=status)
