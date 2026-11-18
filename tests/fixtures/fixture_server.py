"""Owned MCP fixtures. Run with --transport stdio or --transport http --port N."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.tools import Tool, ToolResult
from mcp.types import ImageContent, TextContent


def build_server(events: Path | None = None, catalog_delay: float = 0) -> FastMCP:
    server = FastMCP("gateway-fixture", instructions="Fixture native usage instructions")
    count = 0

    def record(event: str) -> None:
        if events:
            with events.open("a") as stream:
                stream.write(
                    json.dumps({"event": event, "pid": os.getpid(), "time": time.time()}) + "\n"
                )

    class CatalogProbe(Middleware):
        async def on_list_tools(self, context, call_next):
            record("list-tools")
            if catalog_delay:
                await asyncio.sleep(catalog_delay)
            return await call_next(context)

    server.add_middleware(CatalogProbe())
    record("start")

    class FreeFormTool(Tool):
        async def run(self, arguments: dict[str, Any]) -> ToolResult:
            record("freeform")
            return ToolResult(content=json.dumps(arguments), structured_content=arguments)

    server.add_tool(
        FreeFormTool(name="freeform", parameters={"type": "object", "additionalProperties": True})
    )

    @server.tool
    def add(a: int, b: int) -> dict:
        """Add two integers."""
        record("add")
        return {"value": a + b}

    @server.tool
    def beta_add(a: int, b: int) -> dict:
        """Provide a deliberate cross-namespace collision for alpha/alpha_beta."""
        return {"value": a + b}

    @server.tool
    def echo(value: str) -> ToolResult:
        """Return literal text without a schema."""
        return ToolResult(content=[TextContent(type="text", text=value)])

    @server.tool(name="_hidden")
    def underscore(value: str) -> dict:
        record("underscore")
        return {"value": value}

    @server.tool(name="odd-tool")
    def odd_tool(value: str) -> dict:
        """An exact non-identifier tool name, with no synthesized alias."""
        return {"value": value}

    @server.tool
    def counter() -> dict:
        """Increment process-local state and report the PID."""
        nonlocal count
        record("counter")
        count += 1
        return {"count": count, "pid": os.getpid()}

    @server.tool
    def image() -> ToolResult:
        """Return one tiny PNG image."""
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
            "x8AAwMCAO+jBakAAAAASUVORK5CYII="
        )
        return ToolResult(content=[ImageContent(type="image", data=png, mimeType="image/png")])

    @server.tool
    def fail() -> None:
        """Deliberately fail."""
        raise ToolError("fixture deliberate error")

    @server.tool
    async def delay(seconds: float = 30) -> str:
        """Block until completed or cancelled; record both outcomes."""
        record("delay-start")
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            record("delay-cancelled")
            raise
        record("delay-complete")
        return "completed"

    @server.tool
    async def progress(token: str, ctx: Context) -> dict:
        """Send caller-specific progress before and after an overlap point."""
        await ctx.report_progress(0, 1, token)
        await asyncio.sleep(0.1)
        await ctx.report_progress(1, 1, token)
        return {"token": token}

    @server.tool
    def large(size: int = 1024) -> ToolResult:
        """Return exactly size ASCII characters."""
        return ToolResult(content=[TextContent(type="text", text="x" * size)])

    @server.tool
    def append_once() -> dict:
        """Record one non-idempotent side effect."""
        record("append")
        return {"appended": True}

    @server.tool
    def append_result(size: int, error: bool = False) -> ToolResult:
        """Append once, then return a large success or error."""
        record("append")
        return ToolResult(content=[TextContent(type="text", text="x" * size)], is_error=error)

    @server.tool
    async def append_wait(seconds: float = 30) -> dict:
        """Perform one side effect, then wait so a control can interrupt the outcome."""
        record("append-wait")
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            record("append-wait-cancelled")
            raise
        return {"appended": True}

    @server.tool
    def interrupt() -> None:
        """Append once then lose the connection after dispatch."""
        record("append-interrupt")
        os._exit(17)

    @server.tool
    def fail_secret() -> None:
        """Return a configured sentinel in an error for redaction checks."""
        raise ToolError(os.environ.get("ONETOOL_FIXTURE_SECRET", "no-secret"))

    @server.tool
    def header() -> str:
        """Return only the owned HTTP header for transport wiring proof."""
        from fastmcp.server.dependencies import get_http_request

        return get_http_request().headers.get("X-Fixture-Token", "absent")

    @server.tool
    def env_digests(keys: list[str]) -> dict:
        """Prove environment delivery without returning credential values."""
        import hashlib

        return {key: hashlib.sha256(os.environ.get(key, "").encode()).hexdigest() for key in keys}

    @server.tool
    def environment() -> dict:
        """Report environment key names and presence of the owned test sentinel."""
        return {"names": sorted(os.environ), "sentinel": "ONETOOL_TEST_PARENT_SECRET" in os.environ}

    @server.tool
    async def change_catalog(enabled: bool) -> str:
        """Add or remove a tool using public FastMCP registration APIs."""
        if enabled:
            server.add_tool(Tool.from_function(lambda: "dynamic", name="dynamic"))
        else:
            server.local_provider.remove_tool("dynamic")
        return "changed"

    @server.resource("fixture://value")
    def resource() -> str:
        return "fixture resource"

    @server.prompt
    def greeting(name: str) -> str:
        return f"Hello {name}"

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--stderr-text")
    parser.add_argument("--catalog-delay", type=float, default=0)
    args = parser.parse_args()
    if args.stderr_text:
        import sys

        print(args.stderr_text, file=sys.stderr)
    server = build_server(args.events, args.catalog_delay)
    if args.transport == "stdio":
        server.run(show_banner=False)
    else:
        server.run(transport="http", host="127.0.0.1", port=args.port, show_banner=False)


if __name__ == "__main__":
    main()
