"""Local Starlette server for the OneTool admin dashboard."""

from __future__ import annotations

from threading import Lock, Thread
from time import monotonic, sleep
from typing import cast

import uvicorn

from ot.admin.app import create_app

HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 5.0

_server: uvicorn.Server | None = None
_thread: Thread | None = None
_base_url: str | None = None
_lock = Lock()


def ensure_server() -> str:
    """Start the local admin server if needed and return its base URL."""
    global _base_url, _server, _thread
    with _lock:
        if _server is None:
            config = uvicorn.Config(
                create_app(),
                host=HOST,
                port=0,
                log_level="critical",
                access_log=False,
                lifespan="off",
            )
            _server = uvicorn.Server(config)
            _thread = Thread(target=_server.run, daemon=True)
            _thread.start()
            deadline = monotonic() + STARTUP_TIMEOUT_SECONDS
            while not _server.started:
                if _server.should_exit:
                    raise RuntimeError("admin server failed to start")
                if monotonic() >= deadline:
                    _server.should_exit = True
                    raise RuntimeError("admin server did not start within 5 seconds")
                sleep(0.001)
            sockets = _server.servers[0].sockets
            host, port = cast("tuple[str, int]", sockets[0].getsockname()[:2])
            _base_url = f"http://{host}:{port}"
        if _base_url is None:
            raise RuntimeError("admin server base URL is unavailable")
        return _base_url
