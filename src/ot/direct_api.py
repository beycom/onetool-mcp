"""MCP-owned HTTP API for `onetool direct run`.

The API is bound by the MCP server process when ``direct.host.enabled`` is
true. It is intentionally small and authenticated on every endpoint.
"""

from __future__ import annotations

import json
import time
from typing import Any

PROTOCOL_VERSION = 1
MAX_REQUEST_BODY_BYTES = 1_000_000


def _protocol_payload(**values: Any) -> dict[str, Any]:
    return {"protocol_version": PROTOCOL_VERSION, **values}


async def _read_limited_body(request: Any) -> bytes:
    """Read a request body after enforcing a small direct-API payload limit."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                raise ValueError("request body too large")
        except ValueError as e:
            raise ValueError("request body too large") from e

    body: bytes = await request.body()
    if len(body) > MAX_REQUEST_BODY_BYTES:
        raise ValueError("request body too large")
    return body


def create_app() -> Any:
    """Build and return the Starlette ASGI app for the MCP direct API."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    from ot.direct_auth import (
        HEALTH_PATH,
        READY_PATH,
        RUN_PATH,
        HmacAuthError,
        auth_error_response,
        signed_json_response,
        verify_request,
    )

    async def health_endpoint(request: Any) -> Any:
        body = await request.body()
        try:
            verify_request(
                method=request.method,
                path=HEALTH_PATH,
                body=body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return auth_error_response(e, path=HEALTH_PATH)
        return signed_json_response(
            _protocol_payload(status="ok", identity="onetool-mcp-direct"),
            path=HEALTH_PATH,
        )

    async def ready_endpoint(request: Any) -> Any:
        body = await request.body()
        try:
            verify_request(
                method=request.method,
                path=READY_PATH,
                body=body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return auth_error_response(e, path=READY_PATH)

        from ot.config import get_config
        from ot.proxy import get_proxy_manager

        cfg = get_config()
        proxy = get_proxy_manager()
        readiness = proxy.readiness(tuple(cfg.servers.keys()))
        return signed_json_response(
            _protocol_payload(
                status="ok" if readiness["ready"] else "starting",
                ready=readiness["ready"],
                proxy=readiness,
            ),
            path=READY_PATH,
        )

    async def run_endpoint(request: Any) -> Any:
        start = time.monotonic()
        try:
            raw_body = await _read_limited_body(request)
        except ValueError as e:
            return signed_json_response(
                _protocol_payload(result=str(e), success=False),
                path=RUN_PATH,
                status_code=413,
            )
        try:
            verify_request(
                method=request.method,
                path=RUN_PATH,
                body=raw_body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return auth_error_response(e, path=RUN_PATH)

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return signed_json_response(
                _protocol_payload(result="invalid JSON body", success=False),
                path=RUN_PATH,
                status_code=400,
            )

        if body.get("protocol_version") != PROTOCOL_VERSION:
            return signed_json_response(
                _protocol_payload(result="unsupported direct protocol version", success=False),
                path=RUN_PATH,
                status_code=409,
            )
        if body.get("operation") != "run":
            return signed_json_response(
                _protocol_payload(result="unsupported direct operation", success=False),
                path=RUN_PATH,
                status_code=400,
            )

        command = body.get("command", "")
        if not isinstance(command, str) or not command:
            return signed_json_response(
                _protocol_payload(result="'command' field is empty", success=False),
                path=RUN_PATH,
                status_code=400,
            )

        fmt = body.get("format", "json_h")
        sanitize = body.get("sanitize", False)
        if not isinstance(fmt, str) or not isinstance(sanitize, bool):
            return signed_json_response(
                _protocol_payload(result="invalid format or sanitize field", success=False),
                path=RUN_PATH,
                status_code=400,
            )

        from ot.executor.runner import execute_command, prepare_command
        from ot.utils import sanitize_output

        full_command = f"__format__ = {fmt!r}; __sanitize__ = {sanitize!r}\n{command}"
        prepared = prepare_command(full_command)
        if prepared.error:
            return signed_json_response(
                _protocol_payload(result=f"Error: {prepared.error}", success=False),
                path=RUN_PATH,
            )

        result = await execute_command(
            full_command,
            prepared_code=prepared.code,
            skip_validation=True,
        )
        text = sanitize_output(result.result, enabled=result.should_sanitize, fmt=result.format)
        duration_ms = int((time.monotonic() - start) * 1000)
        return signed_json_response(
            _protocol_payload(result=text, success=result.success, duration_ms=duration_ms),
            path=RUN_PATH,
        )

    return Starlette(
        routes=[
            Route(HEALTH_PATH, health_endpoint, methods=["GET"]),
            Route(READY_PATH, ready_endpoint, methods=["GET"]),
            Route(RUN_PATH, run_endpoint, methods=["POST"]),
        ]
    )


__all__ = ["PROTOCOL_VERSION", "create_app"]
