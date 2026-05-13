"""HMAC helpers for the MCP-owned direct API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from otpack import (
    HmacAuthError,
    NonceCache,
    ensure_hmac_key,
    sign_http_message,
    verify_http_message,
)

AUTH_NAMESPACE = "mcp-direct"
RUN_PATH = "/run"
HEALTH_PATH = "/health"
READY_PATH = "/ready"
_request_nonces = NonceCache()


def direct_auth_key(*, base_dir: Path | None = None) -> bytes:
    """Return the MCP direct API shared HMAC key."""
    if base_dir is None:
        from ot.meta import resolve_ot_path

        base_dir = resolve_ot_path(".")

    return ensure_hmac_key(AUTH_NAMESPACE, base_dir=base_dir)


def signed_headers(
    *,
    method: str,
    path: str,
    body: bytes,
    base_dir: Path | None = None,
) -> dict[str, str]:
    """Return signed request headers for the MCP direct API."""
    return sign_http_message(
        key=direct_auth_key(base_dir=base_dir),
        method=method,
        path=path,
        body=body,
    )


def verify_request(*, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
    """Verify a signed MCP direct API request."""
    verify_http_message(
        key=direct_auth_key(),
        method=method,
        path=path,
        body=body,
        headers=headers,
        nonce_cache=_request_nonces,
    )


def sign_response(*, path: str, body: bytes, status_code: int) -> dict[str, str]:
    """Return signed MCP direct API response headers."""
    return sign_http_message(
        key=direct_auth_key(),
        path=path,
        body=body,
        status_code=status_code,
    )


def verify_response(
    *,
    path: str,
    body: bytes,
    headers: dict[str, str],
    status_code: int,
    base_dir: Path | None = None,
) -> None:
    """Verify a signed MCP direct API response."""
    verify_http_message(
        key=direct_auth_key(base_dir=base_dir),
        path=path,
        body=body,
        headers=headers,
        status_code=status_code,
    )


def signed_json_response(payload: dict[str, Any], *, path: str, status_code: int = 200) -> Any:
    """Build a signed Starlette JSON response."""
    from starlette.responses import Response

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = sign_response(path=path, body=body, status_code=status_code)
    return Response(body, status_code=status_code, headers=headers, media_type="application/json")


def auth_error_response(error: Exception, *, path: str = RUN_PATH) -> Any:
    """Build a signed 401 response for auth failures."""
    return signed_json_response({"protocol_version": 1, "result": str(error), "success": False}, path=path, status_code=401)


__all__ = [
    "AUTH_NAMESPACE",
    "HEALTH_PATH",
    "READY_PATH",
    "RUN_PATH",
    "HmacAuthError",
    "auth_error_response",
    "direct_auth_key",
    "sign_response",
    "signed_headers",
    "signed_json_response",
    "verify_request",
    "verify_response",
]
