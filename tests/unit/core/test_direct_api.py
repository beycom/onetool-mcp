"""Tests for the MCP-owned direct API."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ot.direct_api import MAX_REQUEST_BODY_BYTES, create_app
from ot.direct_auth import (
    HEALTH_PATH,
    READY_PATH,
    RUN_PATH,
    signed_headers,
    verify_response,
)

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.types import ASGIApp

ADMIN_BOOTSTRAP_PATH = "/api/admin/bootstrap"
ADMIN_DISPLAY_STATUS_PATH = "/api/admin/display/status"
ADMIN_DISPLAY_MESSAGES_PATH = "/api/admin/display/messages"


def _direct_client(app: ASGIApp | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app or create_app()),
        base_url="http://testserver",
    )


@pytest.mark.unit
@pytest.mark.core
async def test_ready_endpoint_reports_proxy_readiness() -> None:
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
        async with _direct_client() as client:
            response = await client.get(
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
async def test_unsigned_endpoints_return_signed_401() -> None:
    """All direct API endpoints require HMAC auth."""
    async with _direct_client() as client:
        for path, method in ((HEALTH_PATH, "get"), (READY_PATH, "get"), (RUN_PATH, "post")):
            response = await client.post(path, json={}) if method == "post" else await client.get(path)
            verify_response(
                path=path,
                body=response.content,
                headers=dict(response.headers),
                status_code=response.status_code,
            )
            assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
async def test_unsigned_admin_display_endpoint_returns_signed_401() -> None:
    """MCP-side admin/display routes require HMAC auth."""
    async with _direct_client() as client:
        response = await client.get(ADMIN_DISPLAY_STATUS_PATH)

    verify_response(
        path=ADMIN_DISPLAY_STATUS_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
async def test_signed_admin_bootstrap_returns_mcp_metadata() -> None:
    """Bootstrap returns MCP identity and display summary over signed Direct API."""
    async with _direct_client(create_app(base_url="http://127.0.0.1:9999")) as client:
        response = await client.get(
            ADMIN_BOOTSTRAP_PATH,
            headers=signed_headers(method="GET", path=ADMIN_BOOTSTRAP_PATH, body=b""),
        )

    verify_response(
        path=ADMIN_BOOTSTRAP_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["identity"].startswith("mcp-")
    assert payload["base_url"] == "http://127.0.0.1:9999"
    assert payload["display"]["mcp_instance_id"] == payload["identity"]
    assert payload["meta"]["identity"] == payload["identity"]
    assert "cwd" in payload["meta"]
    assert "url" not in payload["display"]


@pytest.mark.unit
@pytest.mark.core
async def test_signed_admin_display_messages_round_trip() -> None:
    """Signed Direct API display routes create and read current MCP messages."""
    body = b'{"kind":"text","content":"direct route","metadata":{"source":"unit"}}'

    async with _direct_client() as client:
        created = await client.post(
            ADMIN_DISPLAY_MESSAGES_PATH,
            content=body,
            headers={
                "content-type": "application/json",
                **signed_headers(method="POST", path=ADMIN_DISPLAY_MESSAGES_PATH, body=body),
            },
        )
        created_payload = created.json()
        read_path = f"{ADMIN_DISPLAY_MESSAGES_PATH}/{created_payload['id']}"
        read = await client.get(
            read_path,
            headers=signed_headers(method="GET", path=read_path, body=b""),
        )

    verify_response(
        path=ADMIN_DISPLAY_MESSAGES_PATH,
        body=created.content,
        headers=dict(created.headers),
        status_code=created.status_code,
    )
    verify_response(
        path=read_path,
        body=read.content,
        headers=dict(read.headers),
        status_code=read.status_code,
    )
    assert created.status_code == 200
    assert read.json()["preview"]["text"] == "direct route"


@pytest.mark.unit
@pytest.mark.core
async def test_signed_admin_display_asset_rejects_oversized_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signed Direct API asset route rejects files above the memory cap."""
    from ot.admin.routes import direct_display

    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setattr(direct_display, "MAX_ASSET_BYTES", 4)
    asset = tmp_path / "large.png"
    asset.write_bytes(b"abcde")
    path = "/api/admin/display/asset"

    async with _direct_client() as client:
        response = await client.get(
            f"{path}?path={asset}",
            headers=signed_headers(method="GET", path=path, body=b""),
        )

    verify_response(
        path=path,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 413
    assert response.json()["error"] == "asset too large"


@pytest.mark.unit
@pytest.mark.core
async def test_replayed_nonce_is_rejected() -> None:
    """The request nonce cache rejects replayed signed requests."""
    headers = signed_headers(method="GET", path=HEALTH_PATH, body=b"")

    async with _direct_client() as client:
        first = await client.get(HEALTH_PATH, headers=headers)
        second = await client.get(HEALTH_PATH, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 401


@pytest.mark.unit
@pytest.mark.core
async def test_run_rejects_protocol_mismatch() -> None:
    """The run endpoint enforces direct protocol version 1."""
    body = b'{"protocol_version":2,"operation":"run","command":"ot.version()"}'

    async with _direct_client() as client:
        response = await client.post(
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
async def test_run_rejects_oversized_body() -> None:
    """The run endpoint rejects oversized payloads before command execution."""
    body = b"x" * (MAX_REQUEST_BODY_BYTES + 1)

    async with _direct_client() as client:
        response = await client.post(
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
