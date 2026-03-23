"""aiohttp companion server for the panel pack.

Provides:
- WebSocket broadcast endpoint (/ws) for pushing content to connected clients
- Static file server (/) serving the pre-built React app dist/
- File proxy (/file?path=) for serving local files within allowed roots

All functions are called from panel.py via the shared daemon asyncio loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import mimetypes
from importlib import resources
from pathlib import Path

from aiohttp import web

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_ws_clients: set[web.WebSocketResponse] = set()
_runner: web.AppRunner | None = None
_loop: asyncio.AbstractEventLoop | None = None
_allowed_roots: list[Path] = []


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------


async def _ws_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle a WebSocket connection — add to client set, serve until close."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _ws_clients.add(ws)
    try:
        async for _ in ws:
            pass  # Panel is one-way push; ignore any incoming messages
    finally:
        _ws_clients.discard(ws)
    return ws


async def _ws_broadcast(msg: str) -> None:
    """Broadcast a message string to all connected WebSocket clients."""
    if not _ws_clients:
        return
    dead: set[web.WebSocketResponse] = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_str(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


def broadcast(msg: str) -> None:
    """Thread-safe broadcast to all connected WebSocket clients.

    Called from the synchronous MCP tool thread; dispatches to the daemon loop.
    No-op if the loop is not running.
    """
    if _loop is None or _loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_ws_broadcast(msg), _loop)


# ---------------------------------------------------------------------------
# File proxy handler
# ---------------------------------------------------------------------------


async def _file_handler(request: web.Request) -> web.Response:
    """Serve a local file if its resolved path is within an allowed root.

    Returns HTTP 403 if the path is outside all allowed roots or if path
    traversal is detected after resolution.
    """
    path_str = request.rel_url.query.get("path", "")
    if not path_str:
        raise web.HTTPBadRequest(text="Missing path parameter")

    try:
        resolved = Path(path_str).resolve()
    except Exception:
        raise web.HTTPForbidden(text="Forbidden") from None

    # Check against each allowed root — allow if relative_to succeeds
    allowed = False
    for root in _allowed_roots:
        try:
            resolved.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue

    if not allowed:
        raise web.HTTPForbidden(text="Forbidden")

    if not resolved.is_file():
        raise web.HTTPNotFound(text="Not found")

    content_type, _ = mimetypes.guess_type(str(resolved))
    content = resolved.read_bytes()
    return web.Response(
        body=content,
        content_type=content_type or "application/octet-stream",
    )


# ---------------------------------------------------------------------------
# App factory and lifecycle
# ---------------------------------------------------------------------------


def _get_dist_dir() -> Path:
    """Return the path to the pre-built React app dist/ directory."""
    return Path(str(resources.files("ottools._panel").joinpath("dist")))


def _make_app() -> web.Application:
    """Build the aiohttp application with all routes."""
    app = web.Application()
    app.router.add_get("/ws", _ws_handler)
    app.router.add_get("/file", _file_handler)

    dist_dir = _get_dist_dir()
    if dist_dir.exists():
        index_html = dist_dir / "index.html"

        async def _index_handler(_request: web.Request) -> web.FileResponse:
            return web.FileResponse(index_html)

        app.router.add_get("/", _index_handler)
        app.router.add_get("/index.html", _index_handler)
        app.router.add_static("/assets", dist_dir / "assets", name="static")

    return app


async def _start_server_async(port: int, roots: list[Path]) -> None:
    """Coroutine: start the aiohttp server on the given port."""
    global _runner, _allowed_roots
    _allowed_roots = list(roots)

    app = _make_app()
    _runner = web.AppRunner(app)
    await _runner.setup()

    site = web.TCPSite(_runner, "127.0.0.1", port, reuse_address=True)
    try:
        await site.start()
    except OSError as e:
        await _runner.cleanup()
        _runner = None
        raise OSError(f"Port {port} is already in use: {e}") from e


async def _stop_server_async() -> None:
    """Coroutine: stop the aiohttp server."""
    global _runner
    if _runner is not None:
        r, _runner = _runner, None
        await r.cleanup()
    _ws_clients.clear()


def start_server(
    port: int,
    allowed_roots: list[Path],
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Start the aiohttp server on the shared daemon loop.

    Must be called from the MCP tool thread (synchronous context).

    Args:
        port: TCP port to bind on 127.0.0.1.
        allowed_roots: Directories whose contents may be served via /file.
        loop: The daemon asyncio event loop shared with pydoll.

    Raises:
        OSError: If the port is already in use.
    """
    global _loop
    _loop = loop
    future = asyncio.run_coroutine_threadsafe(
        _start_server_async(port, allowed_roots), loop
    )
    future.result(timeout=10)  # Propagates OSError on port conflict


def stop_server(loop: asyncio.AbstractEventLoop) -> None:
    """Stop the aiohttp server on the daemon loop. Tolerates already-stopped state."""
    future = asyncio.run_coroutine_threadsafe(_stop_server_async(), loop)
    with contextlib.suppress(Exception):
        future.result(timeout=10)
