"""Raw-ASGI verification for bounded Direct API request bodies."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ot.console.outbox import OUTBOX_PATH
from ot.direct_api import (
    MAX_CONTROL_BODY_BYTES,
    MAX_REQUEST_BODY_BYTES,
    create_app,
)
from ot.direct_auth import (
    HEALTH_PATH,
    READY_PATH,
    RUN_PATH,
    signed_console_headers,
    signed_headers,
    verify_console_response,
    verify_response,
)


@dataclass
class RawResponse:
    """Captured ASGI response and request-consumption count."""

    status: int
    headers: dict[str, str]
    body: bytes
    receive_calls: int


async def _raw_request(
    app: Any,
    *,
    method: str,
    path: str,
    chunks: list[bytes],
    headers: dict[str, str] | None = None,
) -> RawResponse:
    """Call an ASGI app with instrumented body messages."""
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]
    receive_calls = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal receive_calls
        receive_calls += 1
        if not messages:
            raise AssertionError("application requested the body after stream end")
        return messages.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8765),
    }

    await app(scope, receive, send)

    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    response_headers = {
        name.decode("latin-1"): value.decode("latin-1")
        for name, value in start["headers"]
    }
    return RawResponse(
        status=start["status"],
        headers=response_headers,
        body=body,
        receive_calls=receive_calls,
    )


_ROUTES = [
    (HEALTH_PATH, "GET", MAX_CONTROL_BODY_BYTES, False),
    (READY_PATH, "GET", MAX_CONTROL_BODY_BYTES, False),
    (RUN_PATH, "POST", MAX_REQUEST_BODY_BYTES, False),
    (OUTBOX_PATH, "GET", MAX_CONTROL_BODY_BYTES, True),
]


def _verify_signed_response(
    *,
    path: str,
    console: bool,
    response: RawResponse,
) -> None:
    verifier = verify_console_response if console else verify_response
    verifier(
        path=path,
        body=response.body,
        headers=response.headers,
        status_code=response.status,
    )


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "method", "limit", "console"), _ROUTES)
async def test_declared_oversize_rejects_before_first_receive(
    path: str,
    method: str,
    limit: int,
    console: bool,
) -> None:
    """A trustworthy oversize declaration needs no body message."""
    with (
        patch("ot.direct_auth.verify_request") as verify_direct,
        patch("ot.direct_auth.verify_console_request") as verify_console,
        patch("ot.config.get_config") as get_config,
        patch("ot.console.outbox.poll_outbox") as poll_outbox,
        patch("ot.executor.runner.execute_command", new_callable=AsyncMock) as execute,
    ):
        app = create_app()
        get_config.reset_mock()
        poll_outbox.reset_mock()
        response = await _raw_request(
            app,
            method=method,
            path=path,
            chunks=[b"must-not-be-read"],
            headers={"content-length": str(limit + 1)},
        )

    assert response.status == 413
    assert response.receive_calls == 0
    _verify_signed_response(path=path, console=console, response=response)
    verify_direct.assert_not_called()
    verify_console.assert_not_called()
    get_config.assert_not_called()
    poll_outbox.assert_not_called()
    execute.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "method", "limit", "console"), _ROUTES)
@pytest.mark.parametrize(
    ("header_name", "header_value"),
    [
        (None, None),
        ("content-length", "invalid"),
        ("content-length", "-1"),
        ("content-length", "1"),
        ("transfer-encoding", "chunked"),
    ],
)
async def test_streamed_overflow_stops_after_crossing_chunk(
    path: str,
    method: str,
    limit: int,
    console: bool,
    header_name: str | None,
    header_value: str | None,
) -> None:
    """Advisory or missing length metadata cannot bypass stream accounting."""
    headers = (
        {header_name: header_value}
        if header_name is not None and header_value is not None
        else {}
    )
    with (
        patch("ot.direct_auth.verify_request") as verify_direct,
        patch("ot.direct_auth.verify_console_request") as verify_console,
        patch("ot.config.get_config") as get_config,
        patch("ot.console.outbox.poll_outbox") as poll_outbox,
        patch("ot.executor.runner.execute_command", new_callable=AsyncMock) as execute,
    ):
        app = create_app()
        get_config.reset_mock()
        poll_outbox.reset_mock()
        response = await _raw_request(
            app,
            method=method,
            path=path,
            chunks=[b"a" * limit, b"b", b"must-not-be-read"],
            headers=headers,
        )

    assert response.status == 413
    assert response.receive_calls == 2
    _verify_signed_response(path=path, console=console, response=response)
    verify_direct.assert_not_called()
    verify_console.assert_not_called()
    get_config.assert_not_called()
    poll_outbox.assert_not_called()
    execute.assert_not_awaited()


def _exact_body(path: str, limit: int) -> bytes:
    if path != RUN_PATH:
        return b"x" * limit

    base = json.dumps(
        {
            "protocol_version": 1,
            "operation": "run",
            "command": "1 + 1",
            "format": "json",
            "sanitize": False,
        },
        separators=(",", ":"),
    ).encode()
    return base + b" " * (limit - len(base))


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "method", "limit", "console"), _ROUTES)
async def test_exact_boundary_authenticates_exact_streamed_bytes(
    path: str,
    method: str,
    limit: int,
    console: bool,
) -> None:
    """Every route accepts and authenticates the exact boundary byte sequence."""
    body = _exact_body(path, limit)
    assert len(body) == limit
    request_headers = (
        signed_console_headers(method=method, path=path, body=body)
        if console
        else signed_headers(method=method, path=path, body=body)
    )

    proxy = MagicMock()
    proxy.readiness.return_value = {
        "ready": True,
        "status": "ok",
        "configured": 0,
        "connected": 0,
        "failed": 0,
        "servers": {},
    }
    config_context = (
        patch("ot.config.get_config", return_value=SimpleNamespace(servers={}))
        if path == READY_PATH
        else nullcontext()
    )
    proxy_context = (
        patch("ot.proxy.get_proxy_manager", return_value=proxy)
        if path == READY_PATH
        else nullcontext()
    )
    with config_context, proxy_context:
        response = await _raw_request(
            create_app(),
            method=method,
            path=path,
            chunks=[body],
            headers=request_headers,
        )

    assert response.status == 200
    assert response.receive_calls == 1
    _verify_signed_response(path=path, console=console, response=response)
