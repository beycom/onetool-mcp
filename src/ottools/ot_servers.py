"""Runtime proxy server control tools.

Use this pack for state-changing server operations. Discovery remains in
`ot.servers()` and `ot.packs()`.
"""

from __future__ import annotations

from ot.logging import LogSpan
from ottools.server import disable as _disable
from ottools.server import enable as _enable
from ottools.server import restart as _restart
from ottools.server import status as _status

pack = "ot_servers"

__all__ = ["disable", "enable", "restart", "status"]


def enable(*, name: str) -> str:
    """Enable a disabled proxy server and connect it.

    Args:
        name: Configured server name

    Returns:
        Confirmation with connection status
    """
    with LogSpan(span="ot_servers.enable", name=name):
        return _enable(name=name)


def disable(*, name: str) -> str:
    """Disable an enabled proxy server and disconnect it.

    Args:
        name: Configured server name

    Returns:
        Confirmation string
    """
    with LogSpan(span="ot_servers.disable", name=name):
        return _disable(name=name)


def restart(*, name: str) -> str:
    """Reconnect a proxy server.

    Args:
        name: Configured server name

    Returns:
        Confirmation with connection status
    """
    with LogSpan(span="ot_servers.restart", name=name):
        return _restart(name=name)


def status(*, name: str) -> str:
    """Show detailed status for one proxy server.

    Args:
        name: Configured server name

    Returns:
        Server status details
    """
    with LogSpan(span="ot_servers.status", name=name):
        return _status(name=name)
