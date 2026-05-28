"""Tests for the MCP-owned direct API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from ot.direct_api import MAX_REQUEST_BODY_BYTES, create_app
from ot.direct_auth import (
    HEALTH_PATH,
    READY_PATH,
    RUN_PATH,
    signed_headers,
    verify_response,
)


@pytest.mark.unit
@pytest.mark.core
def test_ready_endpoint_reports_proxy_readiness() -> None:
    """Should expose proxy readiness separately from lightweight health."""
    proxy = MagicMock()
    proxy.readiness.return_value = {
        "ready": True,
        "status": "degraded",
        "configured": 2,
        "connected": 1,
        "failed": 1,
        "servers": {
            "ok": {"status": "connected", "tool_count": 3},
            "bad": {"status": "failed", "error": "boom"},
        },
    }
    cfg = SimpleNamespace(
        servers={
            "ok": SimpleNamespace(enabled=True),
            "bad": SimpleNamespace(enabled=True),
            "disabled": SimpleNamespace(enabled=False),
        }
    )

    with (
        patch("ot.config.get_config", return_value=cfg),
        patch("ot.proxy.get_proxy_manager", return_value=proxy),
    ):
        client = TestClient(create_app())
        response = client.get(
            READY_PATH,
            headers=signed_headers(method="GET", path=READY_PATH, body=b""),
        )

    verify_response(
        path=READY_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["proxy"]["status"] == "degraded"
    assert payload["proxy"]["servers"]["bad"]["error"] == "boom"
    proxy.readiness.assert_called_once_with(("ok", "bad"))


@pytest.mark.unit
@pytest.mark.core
def test_unsigned_endpoints_return_signed_401() -> None:
    """All direct API endpoints require HMAC auth."""
    client = TestClient(create_app())

    for path, method in ((HEALTH_PATH, "get"), (READY_PATH, "get"), (RUN_PATH, "post")):
        response = client.post(path, json={}) if method == "post" else client.get(path)
        verify_response(
            path=path,
            body=response.content,
            headers=dict(response.headers),
            status_code=response.status_code,
        )
        assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_replayed_nonce_is_rejected() -> None:
    """The request nonce cache rejects replayed signed requests."""
    client = TestClient(create_app())
    headers = signed_headers(method="GET", path=HEALTH_PATH, body=b"")

    first = client.get(HEALTH_PATH, headers=headers)
    second = client.get(HEALTH_PATH, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_run_rejects_protocol_mismatch() -> None:
    """The run endpoint enforces direct protocol version 1."""
    client = TestClient(create_app())
    body = b'{"protocol_version":2,"operation":"run","command":"ot.version()"}'

    response = client.post(
        RUN_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            **signed_headers(method="POST", path=RUN_PATH, body=body),
        },
    )

    verify_response(
        path=RUN_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 409
    assert response.json()["success"] is False


@pytest.mark.unit
@pytest.mark.core
def test_run_rejects_oversized_body() -> None:
    """The run endpoint rejects oversized payloads before command execution."""
    client = TestClient(create_app())
    body = b"x" * (MAX_REQUEST_BODY_BYTES + 1)

    response = client.post(
        RUN_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            **signed_headers(method="POST", path=RUN_PATH, body=body),
        },
    )

    verify_response(
        path=RUN_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 413
    assert response.json()["success"] is False
