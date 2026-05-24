"""Smoke coverage for Streamable HTTP root MCP mode."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastmcp import Client


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_http_root(url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with Client(url) as client:
                await client.ping()
                return
        except Exception as e:
            last_error = e
            await asyncio.sleep(0.2)
    raise TimeoutError(f"HTTP root MCP server did not become ready: {last_error}")


@pytest.mark.smoke
@pytest.mark.serve
def test_streamable_http_root_lists_and_calls_run(tmp_path: Path) -> None:
    """HTTP root mode supports MCP run calls and proxy state."""
    config = tmp_path / "onetool.yaml"
    missing_command = tmp_path / "missing-mcp-server"
    config.write_text(
        "\n".join(
            [
                "version: 2",
                "tools_dir:",
                f"  - {Path.cwd() / 'src/ottools/*.py'}",
                "security:",
                "  sanitize:",
                "    enabled: false",
                "servers:",
                "  broken_proxy:",
                "    type: stdio",
                f"    command: {missing_command}",
                "    enabled: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    port = _free_port()
    url = f"http://127.0.0.1:{port}/mcp"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "onetool.cli",
            "serve",
            "--config",
            str(config),
            "--transport",
            "http",
            "--port",
            str(port),
            "--path",
            "/mcp",
        ],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        asyncio.run(_wait_for_http_root(url))

        async def _exercise_http_root() -> None:
            async with Client(url) as client:
                tools = await client.list_tools()
                assert any(tool.name == "run" for tool in tools)

                version = await client.call_tool("run", {"command": "ot.version()"})
                assert "2.2.2" in str(version.content[0].text)

                servers = await client.call_tool("run", {"command": "ot.servers()"})
                assert "broken_proxy" in str(servers.content[0].text)
                assert "disconnected" in str(servers.content[0].text)

                status = await client.call_tool(
                    "run", {"command": 'ot_servers.status(name="broken_proxy")'}
                )
                assert "Server: broken_proxy" in str(status.content[0].text)

                disable = await client.call_tool(
                    "run", {"command": 'ot_servers.disable(name="broken_proxy")'}
                )
                assert "disabled" in str(disable.content[0].text)

                after_failure = await client.call_tool(
                    "run", {"command": "ot.version()"}
                )
                assert "2.2.2" in str(after_failure.content[0].text)

        asyncio.run(_exercise_http_root())

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
