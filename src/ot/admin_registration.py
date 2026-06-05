"""Best-effort registration from an MCP Direct API process to the Admin App."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ot.config import get_config
from ot.runtime_meta import get_runtime_meta

REGISTER_PATH = "/api/admin/register"


def registration_payload(*, base_url: str | None = None) -> dict[str, Any]:
    """Build the unsigned registration hint verified by the Admin App."""
    cfg = get_config()
    meta = get_runtime_meta()
    direct_base_url = base_url or meta.get("direct_base_url")
    if not isinstance(direct_base_url, str) or not direct_base_url:
        raise RuntimeError("Direct API is not bound")
    return {
        "base_url": direct_base_url,
        "heartbeat_seconds": cfg.direct.admin.heartbeat_seconds,
    }


def register_with_admin(
    *,
    admin_port: int | None = None,
    base_url: str | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Send one registration attempt to the local Admin App."""
    cfg = get_config()
    port = admin_port if admin_port is not None else cfg.direct.admin.port
    body = json.dumps(registration_payload(base_url=base_url), separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{REGISTER_PATH}",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            payload = json.loads(response_body) if response_body else {}
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "admin_url": f"http://127.0.0.1:{port}",
                "response": payload,
            }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status_code": e.code,
            "admin_url": f"http://127.0.0.1:{port}",
            "error": e.read().decode("utf-8", errors="replace"),
        }
    except OSError as e:
        return {
            "ok": False,
            "status_code": None,
            "admin_url": f"http://127.0.0.1:{port}",
            "error": str(e),
        }

