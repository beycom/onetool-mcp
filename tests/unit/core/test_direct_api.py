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
    signed_console_headers,
    signed_headers,
    verify_console_response,
    verify_response,
)
from ot.console_outbox import OUTBOX_ACK_PATH, OUTBOX_PATH, STATE
from ot.display.models import ShowRequest
from ot.display.state import DisplayState

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.types import ASGIApp


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
async def test_unsigned_console_outbox_endpoint_returns_signed_401() -> None:
    """Console outbox routes require the Console HMAC key."""
    async with _direct_client() as client:
        response = await client.get(OUTBOX_PATH)

    verify_console_response(
        path=OUTBOX_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
async def test_signed_console_outbox_poll_returns_batch() -> None:
    """Signed Console outbox poll returns retained events without mutating them."""
    STATE.instance_id = "mcp-test"
    STATE.sequence = 0
    STATE.acked_through = 0
    STATE.entries.clear()
    STATE.append(event_type="instance.snapshot", payload={"id": "mcp-test", "status": "running"})

    async with _direct_client() as client:
        response = await client.get(
            f"{OUTBOX_PATH}?limit=1",
            headers=signed_console_headers(method="GET", path=OUTBOX_PATH, body=b""),
        )

    verify_console_response(
        path=OUTBOX_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["protocol"] == "onetool.console"
    assert payload["instance_id"] == "mcp-test"
    assert payload["events"][0]["type"] == "instance.snapshot"
    assert len(STATE.entries) == 1


@pytest.mark.unit
@pytest.mark.core
async def test_signed_console_outbox_ack_drops_consumed_entries() -> None:
    """Signed ack records consumption and can drop retained entries early."""
    STATE.instance_id = "mcp-test"
    STATE.sequence = 0
    STATE.acked_through = 0
    STATE.entries.clear()
    STATE.append(event_type="instance.snapshot", payload={"id": "mcp-test", "status": "running"})
    batch = STATE.poll(limit=10)
    body = (
        f'{{"protocol":"onetool.console","protocol_version":1,'
        f'"instance_id":"mcp-test","batch_id":"{batch["batch_id"]}",'
        f'"acked_through":{batch["next_cursor"]}}}'
    ).encode("utf-8")

    async with _direct_client() as client:
        response = await client.post(
            OUTBOX_ACK_PATH,
            content=body,
            headers={
                "content-type": "application/json",
                **signed_console_headers(method="POST", path=OUTBOX_ACK_PATH, body=body),
            },
        )

    verify_console_response(
        path=OUTBOX_ACK_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 200
    assert response.json()["acked_through"] == batch["next_cursor"]
    assert len(STATE.entries) == 0


@pytest.mark.unit
@pytest.mark.core
async def test_console_outbox_key_does_not_authorize_run() -> None:
    """The narrow Console key must not authorize direct execution."""
    body = b'{"protocol_version":1,"operation":"run","command":"ot.version()"}'

    async with _direct_client() as client:
        response = await client.post(
            RUN_PATH,
            content=body,
            headers={
                "content-type": "application/json",
                **signed_console_headers(method="POST", path=RUN_PATH, body=body),
            },
        )

    verify_response(
        path=RUN_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
async def test_display_message_is_available_in_console_outbox() -> None:
    """Display writes append Console protocol events for offline consumers."""
    STATE.instance_id = None
    STATE.sequence = 0
    STATE.acked_through = 0
    STATE.entries.clear()
    display_state = DisplayState()

    metadata = display_state.add_message(
        request=ShowRequest(kind="text", content="direct route", metadata={"source": "unit"})
    )

    batch = STATE.poll(limit=10)
    assert metadata.id
    assert batch["events"][-1]["type"] == "display.message.created"
    assert batch["events"][-1]["payload"]["id"] == metadata.id
    assert batch["events"][-1]["payload"]["payload"]["mode"] == "inline"


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
