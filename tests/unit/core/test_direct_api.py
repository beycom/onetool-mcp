"""Tests for the MCP-owned direct API."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from ot.console.outbox import OUTBOX_ACK_PATH, OUTBOX_PATH
from ot.console.outbox import STATE as CONSOLE_STATE
from ot.direct_api import MAX_REQUEST_BODY_BYTES, create_app
from ot.direct_auth import (
    HEALTH_PATH,
    READY_PATH,
    RUN_PATH,
    console_outbox_auth_key,
    signed_console_headers,
    signed_headers,
    verify_console_response,
    verify_response,
)
from otpack import sign_http_message

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _reset_console_state(instance_id: str = "mcp-test") -> None:
    """Reset the module-level Console outbox singleton to a known state.

    `create_app()` binds the outbox to the current runtime process id and
    appends an initial `instance.snapshot` (task 2.2's startup wiring), so
    tests reset to a deterministic instance id/sequence *after* building the
    app to keep assertions independent of the real process instance id.
    """
    CONSOLE_STATE.instance_id = instance_id
    CONSOLE_STATE.sequence = 0
    CONSOLE_STATE.acked_through = 0
    CONSOLE_STATE.entries.clear()


@pytest.fixture(autouse=True)
def _isolate_console_outbox_state() -> Iterator[None]:
    """Isolate the module-level Console outbox singleton across tests."""
    _reset_console_state()
    yield
    _reset_console_state()


@pytest.mark.unit
@pytest.mark.core
def test_create_app_eagerly_ensures_console_outbox_key(tmp_path: Path) -> None:
    """The Console outbox HMAC key file exists immediately after `create_app()`.

    A Console started right after MCP is up must be able to authenticate
    without first waiting for an outbox request to lazily create the key.
    """
    key_path = tmp_path / "auth" / "console-outbox.key"
    assert not key_path.exists()

    with patch("ot.meta.resolve_ot_path", return_value=tmp_path):
        create_app()

    assert key_path.exists()
    assert oct(key_path.stat().st_mode)[-3:] == "600"


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


@pytest.mark.unit
@pytest.mark.core
def test_console_outbox_poll_returns_batch_with_identity_and_cursors() -> None:
    """A signed poll returns protocol/instance identity, cursors, and has_more."""
    client = TestClient(create_app())
    _reset_console_state()
    CONSOLE_STATE.append(
        event_type="instance.snapshot", payload={"id": "mcp-test", "status": "running"}
    )
    CONSOLE_STATE.append(event_type="console.message.created", payload={"id": "m1"})

    response = client.get(
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
    assert payload["protocol_version"] == 1
    assert payload["instance_id"] == "mcp-test"
    assert payload["cursor"] == 0
    assert payload["next_cursor"] == 1
    assert payload["has_more"] is True
    assert len(payload["events"]) == 1
    assert payload["events"][0]["type"] == "instance.snapshot"
    # Polling does not remove events from the outbox.
    assert len(CONSOLE_STATE.entries) == 2


@pytest.mark.unit
@pytest.mark.core
def test_console_outbox_ack_records_and_advances_cursor() -> None:
    """Acknowledging a batch advances the cursor and drops acked entries."""
    client = TestClient(create_app())
    _reset_console_state()
    CONSOLE_STATE.append(
        event_type="instance.snapshot", payload={"id": "mcp-test", "status": "running"}
    )
    CONSOLE_STATE.append(event_type="console.message.created", payload={"id": "m1"})
    batch = CONSOLE_STATE.poll(limit=10)
    body = (
        f'{{"protocol":"onetool.console","protocol_version":1,'
        f'"instance_id":"mcp-test",'
        f'"acked_through":{batch["next_cursor"]}}}'
    ).encode()

    response = client.post(
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
    payload = response.json()
    assert payload["acked_through"] == batch["next_cursor"]
    assert payload["retained"] == 0
    assert len(CONSOLE_STATE.entries) == 0


@pytest.mark.unit
@pytest.mark.core
def test_console_outbox_redelivers_unacked_events_at_least_once() -> None:
    """Events not yet acked stay eligible for redelivery on the next poll."""
    client = TestClient(create_app())
    _reset_console_state()
    CONSOLE_STATE.append(
        event_type="instance.snapshot", payload={"id": "mcp-test", "status": "running"}
    )
    CONSOLE_STATE.append(event_type="console.message.created", payload={"id": "m1"})

    first = client.get(
        f"{OUTBOX_PATH}?limit=1",
        headers=signed_console_headers(method="GET", path=OUTBOX_PATH, body=b""),
    )
    second = client.get(
        f"{OUTBOX_PATH}?limit=1",
        headers=signed_console_headers(method="GET", path=OUTBOX_PATH, body=b""),
    )

    assert first.json()["events"] == second.json()["events"]
    assert second.json()["events"][0]["type"] == "instance.snapshot"


@pytest.mark.unit
@pytest.mark.core
def test_console_key_does_not_authorize_run_health_or_ready() -> None:
    """The narrow Console key must not authorize `/run`, `/health`, or `/ready`."""
    client = TestClient(create_app())

    for path, method in ((HEALTH_PATH, "get"), (READY_PATH, "get"), (RUN_PATH, "post")):
        body = (
            b'{"protocol_version":1,"operation":"run","command":"ot.version()"}'
            if method == "post"
            else b""
        )
        headers = {
            **({"content-type": "application/json"} if method == "post" else {}),
            **signed_console_headers(
                method="POST" if method == "post" else "GET", path=path, body=body
            ),
        }
        response = (
            client.post(path, content=body, headers=headers)
            if method == "post"
            else client.get(path, headers=headers)
        )
        verify_response(
            path=path,
            body=response.content,
            headers=dict(response.headers),
            status_code=response.status_code,
        )
        assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_direct_key_does_not_authorize_console_outbox() -> None:
    """The general direct key must not authorize Console outbox endpoints."""
    client = TestClient(create_app())

    response = client.get(
        OUTBOX_PATH, headers=signed_headers(method="GET", path=OUTBOX_PATH, body=b"")
    )
    verify_console_response(
        path=OUTBOX_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 401

    ack_body = b'{"protocol":"onetool.console","protocol_version":1}'
    ack_response = client.post(
        OUTBOX_ACK_PATH,
        content=ack_body,
        headers={
            "content-type": "application/json",
            **signed_headers(method="POST", path=OUTBOX_ACK_PATH, body=ack_body),
        },
    )
    verify_console_response(
        path=OUTBOX_ACK_PATH,
        body=ack_response.content,
        headers=dict(ack_response.headers),
        status_code=ack_response.status_code,
    )
    assert ack_response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_unsigned_console_outbox_endpoints_return_signed_401() -> None:
    """Console outbox endpoints require the Console HMAC key, not just any signature."""
    client = TestClient(create_app())

    poll_response = client.get(OUTBOX_PATH)
    verify_console_response(
        path=OUTBOX_PATH,
        body=poll_response.content,
        headers=dict(poll_response.headers),
        status_code=poll_response.status_code,
    )
    assert poll_response.status_code == 401

    ack_response = client.post(OUTBOX_ACK_PATH, content=b"{}")
    verify_console_response(
        path=OUTBOX_ACK_PATH,
        body=ack_response.content,
        headers=dict(ack_response.headers),
        status_code=ack_response.status_code,
    )
    assert ack_response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_stale_timestamp_console_request_is_rejected() -> None:
    """A Console outbox request signed far in the past is rejected."""
    client = TestClient(create_app())
    stale_headers = sign_http_message(
        key=console_outbox_auth_key(),
        method="GET",
        path=OUTBOX_PATH,
        body=b"",
        timestamp=time.time() - 1000,
    )

    response = client.get(OUTBOX_PATH, headers=stale_headers)

    verify_console_response(
        path=OUTBOX_PATH,
        body=response.content,
        headers=dict(response.headers),
        status_code=response.status_code,
    )
    assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.core
def test_replayed_nonce_console_request_is_rejected() -> None:
    """The Console outbox nonce cache rejects replayed signed requests."""
    client = TestClient(create_app())
    headers = signed_console_headers(method="GET", path=OUTBOX_PATH, body=b"")

    first = client.get(OUTBOX_PATH, headers=headers)
    second = client.get(OUTBOX_PATH, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 401
