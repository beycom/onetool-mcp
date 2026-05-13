"""HMAC HTTP authentication helpers for local OneTool bridges."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from contextlib import suppress
from pathlib import Path

__all__ = [
    "HmacAuthError",
    "NonceCache",
    "ensure_hmac_key",
    "sign_http_message",
    "verify_http_message",
]

PROTOCOL = "hmac-sha256-v1"
HEADER_PROTOCOL = "X-OneTool-Protocol"
HEADER_TIMESTAMP = "X-OneTool-Timestamp"
HEADER_NONCE = "X-OneTool-Nonce"
HEADER_SIGNATURE = "X-OneTool-Signature"


class HmacAuthError(ValueError):
    """Raised when HMAC HTTP authentication fails."""


class NonceCache:
    """Small in-memory nonce replay cache."""

    def __init__(self, *, ttl_seconds: float = 60.0, max_entries: int = 4096) -> None:
        """Create a nonce cache.

        Args:
            ttl_seconds: How long nonces remain invalid for replay.
            max_entries: Maximum nonces retained after TTL cleanup.
        """
        if max_entries < 1:
            raise ValueError("NonceCache max_entries must be at least 1")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._seen: dict[str, float] = {}

    def check(self, nonce: str, *, now: float | None = None) -> None:
        """Record a nonce or raise if it has been seen recently."""
        current = time.time() if now is None else now
        expired = [
            value
            for value, seen_at in self._seen.items()
            if current - seen_at > self.ttl_seconds
        ]
        for value in expired:
            self._seen.pop(value, None)

        if nonce in self._seen:
            raise HmacAuthError("Replayed OneTool auth nonce")
        self._seen[nonce] = current
        if len(self._seen) > self.max_entries:
            oldest = min(self._seen, key=self._seen.__getitem__)
            self._seen.pop(oldest, None)


def ensure_hmac_key(namespace: str, *, base_dir: Path | None = None) -> bytes:
    """Read or create the local HMAC key for a namespace.

    Keys are stored at ``<base_dir>/<namespace>/auth.key``. When ``base_dir``
    is omitted, the OneTool default ``~/.onetool`` is used.
    """
    if not namespace or "/" in namespace or "\\" in namespace:
        raise ValueError("HMAC key namespace must be a simple name")

    root = Path.home() / ".onetool" if base_dir is None else base_dir
    path = root / namespace / "auth.key"
    if path.exists():
        return _decode_key(path.read_text().strip())

    path.parent.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        path.parent.chmod(0o700)

    key = secrets.token_bytes(32)
    encoded = base64.b64encode(key).decode("ascii")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return _decode_key(path.read_text().strip())

    with os.fdopen(fd, "w") as handle:
        handle.write(encoded + "\n")
    return key


def sign_http_message(
    *,
    key: bytes,
    method: str | None = None,
    path: str,
    body: bytes,
    status_code: int | None = None,
    timestamp: float | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Return HMAC auth headers for an HTTP request or response."""
    ts = str(int(time.time() if timestamp is None else timestamp))
    nonce_value = nonce or secrets.token_hex(16)
    signature = _signature(
        key=key,
        method=method,
        path=path,
        body=body,
        status_code=status_code,
        timestamp=ts,
        nonce=nonce_value,
    )
    return {
        HEADER_PROTOCOL: PROTOCOL,
        HEADER_TIMESTAMP: ts,
        HEADER_NONCE: nonce_value,
        HEADER_SIGNATURE: signature,
    }


def verify_http_message(
    *,
    key: bytes,
    path: str,
    body: bytes,
    headers: dict[str, str],
    method: str | None = None,
    status_code: int | None = None,
    max_skew_seconds: float = 30.0,
    nonce_cache: NonceCache | None = None,
    now: float | None = None,
) -> None:
    """Verify HMAC auth headers for an HTTP request or response."""
    protocol = _header(headers, HEADER_PROTOCOL)
    if protocol != PROTOCOL:
        raise HmacAuthError(f"Unsupported OneTool auth protocol: {protocol!r}")

    timestamp = _header(headers, HEADER_TIMESTAMP)
    nonce = _header(headers, HEADER_NONCE)
    signature = _header(headers, HEADER_SIGNATURE)
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HmacAuthError("Invalid OneTool auth timestamp") from exc

    current = time.time() if now is None else now
    if abs(current - ts) > max_skew_seconds:
        raise HmacAuthError("Stale OneTool auth timestamp")

    expected = _signature(
        key=key,
        method=method,
        path=path,
        body=body,
        status_code=status_code,
        timestamp=timestamp,
        nonce=nonce,
    )
    if not hmac.compare_digest(signature, expected):
        raise HmacAuthError("Invalid OneTool auth signature")

    if nonce_cache is not None:
        nonce_cache.check(nonce, now=current)


def _decode_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise HmacAuthError("Invalid OneTool HMAC key file") from exc
    if len(key) != 32:
        raise HmacAuthError("Invalid OneTool HMAC key length")
    return key


def _header(headers: dict[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            if not value:
                raise HmacAuthError(f"Missing OneTool auth header: {name}")
            return value
    raise HmacAuthError(f"Missing OneTool auth header: {name}")


def _signature_payload(
    *,
    method: str | None,
    path: str,
    body: bytes,
    status_code: int | None,
    timestamp: str,
    nonce: str,
) -> bytes:
    subject = method.upper() if method is not None else f"STATUS:{status_code}"
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join([subject, path, timestamp, nonce, body_hash]).encode("utf-8")


def _signature(
    *,
    key: bytes,
    method: str | None,
    path: str,
    body: bytes,
    status_code: int | None,
    timestamp: str,
    nonce: str,
) -> str:
    if (method is None) == (status_code is None):
        raise ValueError("Provide exactly one of method or status_code")
    payload = _signature_payload(
        method=method,
        path=path,
        body=body,
        status_code=status_code,
        timestamp=timestamp,
        nonce=nonce,
    )
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")
