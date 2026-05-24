"""Private handoff child OneTool setup helpers."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path as PathType

from ot.direct_api import PROTOCOL_VERSION
from ot.direct_auth import RUN_PATH, signed_headers, verify_response
from ot.logging import LogSpan


@dataclass(frozen=True)
class ChildProxy:
    """Private child OneTool connection details."""

    url: str
    env: dict[str, str]
    mcp_config: dict[str, Any]


def current_direct_url() -> str | None:
    """Return the root process direct API URL when available."""
    try:
        from ot import server

        port = getattr(server, "_direct_api_port", None)
    except Exception:
        port = None
    if isinstance(port, int):
        return f"http://127.0.0.1:{port}"
    return None


def current_parent_ot_dir() -> str:
    """Return the current root process OneTool directory."""
    from ot.meta import resolve_ot_path

    return str(resolve_ot_path("."))


def current_onetool_command() -> str:
    """Return the absolute OneTool executable paired with this Python runtime."""
    script = Path(sys.executable).with_name("onetool")
    if script.exists():
        return str(script)
    return "onetool"


def build_child_proxy(*, direct_url: str, parent_ot_dir: str | None = None) -> ChildProxy:
    """Build child OneTool MCP config for a delegated worker."""
    ot_dir = parent_ot_dir or current_parent_ot_dir()
    mcp_config = {
        "mcpServers": {
            "onetool": {
                "command": current_onetool_command(),
                "args": ["child", "--url", direct_url, "--ot-dir", ot_dir],
                "allowed_tools": ["run"],
            }
        }
    }
    return ChildProxy(url=direct_url, env={}, mcp_config=mcp_config)


def ensure_child_proxy() -> ChildProxy:
    """Return private child OneTool settings or raise a clear error."""
    direct_url = current_direct_url()
    if not direct_url:
        raise RuntimeError(
            "handoff child unavailable: direct.host must be enabled in the root OneTool MCP process"
        )
    return build_child_proxy(direct_url=direct_url)


async def forward_run(
    *,
    command: str,
    direct_url: str,
    fmt: str = "json_h",
    sanitize: bool = False,
    base_dir: PathType | None = None,
) -> dict[str, Any]:
    """Forward one child run request to the root direct API."""
    import httpx

    start = time.monotonic()
    parsed_url = urlparse(direct_url)
    body = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "operation": "run",
            "command": command,
            "format": fmt,
            "sanitize": sanitize,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    with LogSpan(
        span="child.forward.run",
        parentHost=parsed_url.hostname or "",
        parentPort=parsed_url.port or "",
    ) as span:
        headers = signed_headers(method="POST", path=RUN_PATH, body=body, base_dir=base_dir)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{direct_url}{RUN_PATH}", content=body, headers=headers
                )
            verify_response(
                path=RUN_PATH,
                body=response.content,
                headers=dict(response.headers),
                status_code=response.status_code,
                base_dir=base_dir,
            )
        except Exception as e:
            span.add(
                success=False,
                durationMs=int((time.monotonic() - start) * 1000),
                errorClass=type(e).__name__,
            )
            raise
        span.add(
            success=True,
            durationMs=int((time.monotonic() - start) * 1000),
            statusCode=response.status_code,
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("invalid direct API response")
    return payload
