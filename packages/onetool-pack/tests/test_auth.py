"""Tests for otpack HMAC HTTP auth helpers."""

from __future__ import annotations

import base64
import stat
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.pkg
def test_ensure_hmac_key_creates_and_reuses_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_hmac_key creates a 32-byte key and reuses it."""
    import otpack.auth as auth

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    first = auth.ensure_hmac_key("ide")
    second = auth.ensure_hmac_key("ide")

    assert len(first) == 32
    assert second == first
    path = tmp_path / ".onetool" / "ide" / "auth.key"
    assert base64.b64decode(path.read_text().strip()) == first
    assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


@pytest.mark.unit
@pytest.mark.pkg
def test_verify_accepts_signed_request() -> None:
    """A matching signed request verifies successfully."""
    from otpack.auth import sign_http_message, verify_http_message

    key = b"1" * 32
    body = b'{"ok":true}'
    headers = sign_http_message(
        key=key,
        method="POST",
        path="/state",
        body=body,
        timestamp=1000,
        nonce="abc",
    )

    verify_http_message(
        key=key,
        method="POST",
        path="/state",
        body=body,
        headers=headers,
        now=1000,
    )


@pytest.mark.unit
@pytest.mark.pkg
def test_verify_accepts_signed_response() -> None:
    """A matching signed response verifies successfully."""
    from otpack.auth import sign_http_message, verify_http_message

    key = b"2" * 32
    body = b'{"ok":true}'
    headers = sign_http_message(
        key=key,
        status_code=200,
        path="/health",
        body=body,
        timestamp=1000,
        nonce="resp",
    )

    verify_http_message(
        key=key,
        status_code=200,
        path="/health",
        body=body,
        headers=headers,
        now=1000,
    )


@pytest.mark.unit
@pytest.mark.pkg
def test_verify_rejects_invalid_signature() -> None:
    """Body tampering fails signature verification."""
    from otpack.auth import HmacAuthError, sign_http_message, verify_http_message

    key = b"3" * 32
    headers = sign_http_message(
        key=key,
        method="POST",
        path="/state",
        body=b"one",
        timestamp=1000,
        nonce="abc",
    )

    with pytest.raises(HmacAuthError, match="Invalid OneTool auth signature"):
        verify_http_message(
            key=key,
            method="POST",
            path="/state",
            body=b"two",
            headers=headers,
            now=1000,
        )


@pytest.mark.unit
@pytest.mark.pkg
def test_verify_rejects_stale_timestamp() -> None:
    """Old signatures are rejected."""
    from otpack.auth import HmacAuthError, sign_http_message, verify_http_message

    key = b"4" * 32
    headers = sign_http_message(
        key=key,
        method="GET",
        path="/health",
        body=b"",
        timestamp=1000,
        nonce="abc",
    )

    with pytest.raises(HmacAuthError, match="Stale OneTool auth timestamp"):
        verify_http_message(
            key=key,
            method="GET",
            path="/health",
            body=b"",
            headers=headers,
            now=1100,
        )


@pytest.mark.unit
@pytest.mark.pkg
def test_nonce_cache_rejects_replay() -> None:
    """NonceCache rejects a reused nonce inside the TTL."""
    from otpack.auth import HmacAuthError, NonceCache

    cache = NonceCache(ttl_seconds=60)
    cache.check("nonce", now=1000)

    with pytest.raises(HmacAuthError, match="Replayed OneTool auth nonce"):
        cache.check("nonce", now=1001)
