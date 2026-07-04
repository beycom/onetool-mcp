#!/usr/bin/env python3
"""Zero-dependency macOS narrator MCP server for OneTool demos.

Wraps the macOS `say` command as a single MCP tool, proxied through OneTool.
Demonstrates the proxy story documented in docs/learn/mcp-proxy.md: any stdio
MCP server, including this one, becomes a callable Python namespace with no
OneTool-side code changes — register it under `servers:` and call
`narrator.speak(text=...)`.

macOS only. `say` ships with the OS; no extra dependency beyond the `fastmcp`
client library, already a OneTool dependency (pyproject.toml `fastmcp>=3.1.1,<4`).
"""

from __future__ import annotations

import subprocess
import sys

from fastmcp import FastMCP

mcp = FastMCP("narrator")


@mcp.tool()
def speak(text: str, voice: str = "Samantha") -> str:
    """Speak `text` aloud using the macOS `say` command.

    Args:
        text: The line to narrate.
        voice: macOS voice name (see `say -v ?` for the installed list).

    Returns:
        Confirmation string once `say` exits.
    """
    if sys.platform != "darwin":
        return "narrator.speak is macOS-only (say not available on this platform)"
    subprocess.run(["say", "-v", voice, text], check=True)
    return f"spoke: {text!r}"


if __name__ == "__main__":
    mcp.run()
