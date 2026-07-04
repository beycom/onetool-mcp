"""HMAC helpers for the MCP-owned direct API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from otpack import (
    HmacAuthError,
    NonceCache,
    ensure_hmac_key_file,
    sign_http_message,
    verify_http_message,
)

AUTH_KEY_NAME = "mcp-direct.key"
CONSOLE_OUTBOX_KEY_NAME = "console-outbox.key"
RUN_PATH = "/run"
HEALTH_PATH = "/health"
READY_PATH = "/ready"
_request_nonces = NonceCache()
_console_request_nonces = NonceCache()


def direct_auth_key(*, base_dir: Path | None = None) -> bytes:
    """Return the MCP direct API shared HMAC key."""
    if base_dir is None:
        from ot.meta import resolve_ot_path

        base_dir = resolve_ot_path(".")

    return ensure_hmac_key_file(base_dir / "auth" / AUTH_KEY_NAME)


def console_outbox_auth_key(*, base_dir: Path | None = None) -> bytes:
    """Return the Console outbox shared HMAC key.

    Scope-exclusive from `direct_auth_key`: this key authorizes only the
    Console outbox endpoints and never `/run`, `/health`, or `/ready`.
    """
    if base_dir is None:
        from ot.meta import resolve_ot_path

        base_dir = resolve_ot_path(".")

    return ensure_hmac_key_file(base_dir / "auth" / CONSOLE_OUTBOX_KEY_NAME)


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


def signed_console_headers(
    *,
    method: str,
    path: str,
    body: bytes,
    base_dir: Path | None = None,
) -> dict[str, str]:
    """Return signed request headers for the Console outbox endpoints."""
    return sign_http_message(
        key=console_outbox_auth_key(base_dir=base_dir),
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


def verify_console_request(
    *, method: str, path: str, body: bytes, headers: dict[str, str]
) -> None:
    """Verify a signed Console outbox request."""
    verify_http_message(
        key=console_outbox_auth_key(),
        method=method,
        path=path,
        body=body,
        headers=headers,
        nonce_cache=_console_request_nonces,
    )


def sign_response(*, path: str, body: bytes, status_code: int) -> dict[str, str]:
    """Return signed MCP direct API response headers."""
    return sign_http_message(
        key=direct_auth_key(),
        path=path,
        body=body,
        status_code=status_code,
    )


def sign_console_response(*, path: str, body: bytes, status_code: int) -> dict[str, str]:
    """Return signed Console outbox response headers."""
    return sign_http_message(
        key=console_outbox_auth_key(),
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


def verify_console_response(
    *,
    path: str,
    body: bytes,
    headers: dict[str, str],
    status_code: int,
    base_dir: Path | None = None,
) -> None:
    """Verify a signed Console outbox response."""
    verify_http_message(
        key=console_outbox_auth_key(base_dir=base_dir),
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


def signed_console_json_response(
    payload: dict[str, Any], *, path: str, status_code: int = 200
) -> Any:
    """Build a signed Starlette JSON response using the Console outbox key."""
    from starlette.responses import Response

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = sign_console_response(path=path, body=body, status_code=status_code)
    return Response(body, status_code=status_code, headers=headers, media_type="application/json")


def auth_error_response(error: Exception, *, path: str = RUN_PATH) -> Any:
    """Build a signed 401 response for auth failures."""
    return signed_json_response({"protocol_version": 1, "result": str(error), "success": False}, path=path, status_code=401)


def console_auth_error_response(error: Exception, *, path: str) -> Any:
    """Build a signed 401 response for Console outbox auth failures."""
    return signed_console_json_response(
        {"protocol": "onetool.console", "protocol_version": 1, "error": str(error)},
        path=path,
        status_code=401,
    )


__all__ = [
    "AUTH_KEY_NAME",
    "CONSOLE_OUTBOX_KEY_NAME",
    "HEALTH_PATH",
    "READY_PATH",
    "RUN_PATH",
    "HmacAuthError",
    "auth_error_response",
    "console_auth_error_response",
    "console_outbox_auth_key",
    "direct_auth_key",
    "sign_console_response",
    "sign_response",
    "signed_console_headers",
    "signed_console_json_response",
    "signed_headers",
    "signed_json_response",
    "verify_console_request",
    "verify_console_response",
    "verify_request",
    "verify_response",
]
