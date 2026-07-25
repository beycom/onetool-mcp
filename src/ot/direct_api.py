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
MAX_CONTROL_BODY_BYTES = 65_536


def _protocol_payload(**values: Any) -> dict[str, Any]:
    return {"protocol_version": PROTOCOL_VERSION, **values}


async def _read_limited_body(request: Any, *, limit: int) -> bytes:
    """Incrementally read at most ``limit`` bytes from one request body."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if (
            declared_length is not None
            and declared_length >= 0
            and declared_length > limit
        ):
            raise ValueError("request body too large")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise ValueError("request body too large")
        body.extend(chunk)
    return bytes(body)


def create_app() -> Any:
    """Build and return the Starlette ASGI app for the MCP direct API."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    from ot.console.outbox import (
        OUTBOX_PATH,
        ensure_instance_snapshot,
        poll_outbox,
    )
    from ot.direct_auth import (
        HEALTH_PATH,
        READY_PATH,
        RUN_PATH,
        HmacAuthError,
        auth_error_response,
        console_auth_error_response,
        console_outbox_auth_key,
        signed_console_json_response,
        signed_json_response,
        verify_console_request,
        verify_request,
    )

    # Eagerly ensure the Console outbox HMAC key file exists as soon as the
    # Console outbox routes are mounted, instead of lazily on the first
    # request. This lets a Console started right after MCP is up authenticate
    # from the moment MCP is ready. `ensure_hmac_key_file` is idempotent: a
    # pre-existing key is read, not regenerated, so the lazy call path on the
    # first request still works unchanged.
    console_outbox_auth_key()

    # Bind the Console outbox to this runtime instance and append the
    # initial `instance.snapshot` event before the app can serve any
    # requests, so a Console polling immediately after startup always sees
    # instance identity even before any display activity occurs (the app is
    # served with uvicorn `lifespan="off"`, so this happens here rather than
    # in an ASGI lifespan handler).
    ensure_instance_snapshot(message_count=0)

    async def health_endpoint(request: Any) -> Any:
        try:
            body = await _read_limited_body(request, limit=MAX_CONTROL_BODY_BYTES)
        except ValueError as e:
            return signed_json_response(
                _protocol_payload(result=str(e), success=False),
                path=HEALTH_PATH,
                status_code=413,
            )
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
        try:
            body = await _read_limited_body(request, limit=MAX_CONTROL_BODY_BYTES)
        except ValueError as e:
            return signed_json_response(
                _protocol_payload(result=str(e), success=False),
                path=READY_PATH,
                status_code=413,
            )
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
        enabled_servers = tuple(
            name for name, server in cfg.servers.items() if server.enabled
        )
        readiness = proxy.readiness(enabled_servers)
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
            raw_body = await _read_limited_body(
                request,
                limit=MAX_REQUEST_BODY_BYTES,
            )
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
                _protocol_payload(
                    result="unsupported direct protocol version", success=False
                ),
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
                _protocol_payload(
                    result="invalid format or sanitize field", success=False
                ),
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
        text = sanitize_output(
            result.result, enabled=result.should_sanitize, fmt=result.format
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return signed_json_response(
            _protocol_payload(
                result=text, success=result.success, duration_ms=duration_ms
            ),
            path=RUN_PATH,
        )

    async def console_outbox_endpoint(request: Any) -> Any:
        try:
            body = await _read_limited_body(request, limit=MAX_CONTROL_BODY_BYTES)
        except ValueError as e:
            return signed_console_json_response(
                {
                    "protocol": "onetool.console",
                    "protocol_version": 1,
                    "error": str(e),
                },
                path=OUTBOX_PATH,
                status_code=413,
            )
        try:
            verify_console_request(
                method=request.method,
                path=OUTBOX_PATH,
                body=body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return console_auth_error_response(e, path=OUTBOX_PATH)
        try:
            limit = int(request.query_params.get("limit", "100"))
            after_param = request.query_params.get("after")
            after = int(after_param) if after_param not in {None, ""} else None
        except ValueError:
            return signed_console_json_response(
                {
                    "protocol": "onetool.console",
                    "protocol_version": 1,
                    "error": "invalid outbox cursor",
                },
                path=OUTBOX_PATH,
                status_code=400,
            )
        return signed_console_json_response(
            poll_outbox(limit=limit, after=after),
            path=OUTBOX_PATH,
        )

    return Starlette(
        routes=[
            Route(HEALTH_PATH, health_endpoint, methods=["GET"]),
            Route(READY_PATH, ready_endpoint, methods=["GET"]),
            Route(RUN_PATH, run_endpoint, methods=["POST"]),
            Route(OUTBOX_PATH, console_outbox_endpoint, methods=["GET"]),
        ]
    )


__all__ = ["PROTOCOL_VERSION", "create_app"]
