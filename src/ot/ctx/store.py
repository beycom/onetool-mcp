"""Immutable per-handle storage for the ctx pack.

Each published handle is a directory containing a complete record:
    <handle>/content    — raw content (UTF-8 text)
    <handle>/meta.json  — metadata JSON
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any


def _resolve_handle(handle: Any) -> str:
    """Resolve a handle argument to a string handle ID.

    Transparently extracts the ID from a handle dict
    (``{"handle": "b2d18a1b9f9e4c86a3fbeb9ba2685107", ...}``) — consistent with how
    ``ctx_write()`` derefs content handle dicts.

    Raises:
        TypeError: If handle is not a string or a handle dict.
    """
    if isinstance(handle, str):
        return handle
    if isinstance(handle, dict):
        val = handle.get("handle")
        if isinstance(val, str):
            return val
    type_name = type(handle).__name__
    raise TypeError(
        f"handle must be a string (e.g. 'b2d18a1b9f9e4c86a3fbeb9ba2685107'), "
        f"got {type_name}. "
        "If you have a handle dict h, use h['handle']."
    )


# ---------------------------------------------------------------------------
# TTL helpers
# ---------------------------------------------------------------------------


def now_ts() -> float:
    """Return current Unix timestamp."""
    return time.time()


def expires_at_ts(ttl: int) -> float | None:
    """Return expiry timestamp, or None if TTL is 0 (no expiry)."""
    if ttl <= 0:
        return None
    return now_ts() + ttl


def is_expired(meta: dict[str, Any]) -> bool:
    """Return True if the handle has passed its TTL."""
    exp = meta.get("expires_at")
    if exp is None:
        return False
    return bool(now_ts() > exp)


def ttl_remaining(meta: dict[str, Any]) -> float:
    """Return remaining TTL in seconds (0.0 if no expiry or already expired)."""
    exp = meta.get("expires_at")
    if exp is None:
        return 0.0
    return max(0.0, float(exp) - now_ts())


def load_live_meta(
    store: HandleStore, handle: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Load a handle's metadata, rejecting missing or expired handles.

    Returns:
        (meta, None) on success, or (None, error_message) when the handle is
        missing, unreadable, or past its TTL.
    """
    if not store.exists(handle):
        return None, f"Handle not found: {handle}"
    try:
        meta = store.read_meta(handle)
    except (OSError, ValueError):
        return None, f"Handle not found: {handle}"
    if is_expired(meta):
        return None, f"Handle has expired: {handle}"
    return meta, None


# ---------------------------------------------------------------------------
# HandleStore
# ---------------------------------------------------------------------------


class HandleStore:
    """Manage atomically published immutable ctx records."""

    def __init__(self, ctx_dir: Path) -> None:
        self._dir = ctx_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def record_path(self, handle: str) -> Path:
        return self._dir / handle

    def content_path(self, handle: str) -> Path:
        return self.record_path(handle) / "content"

    def meta_path(self, handle: str) -> Path:
        return self.record_path(handle) / "meta.json"

    def exists(self, handle: str) -> bool:
        return (
            self.record_path(handle).is_dir()
            and self.meta_path(handle).is_file()
            and self.content_path(handle).is_file()
        )

    @staticmethod
    def _write_durable(path: Path, text: str) -> None:
        with path.open("w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def write(self, handle: str, content: str, meta: dict[str, Any]) -> None:
        """Publish a complete immutable record without replacing an existing one."""
        metadata = json.dumps(meta, indent=2)
        record_path = self.record_path(handle)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{handle}.",
                suffix=".tmp",
                dir=self._dir,
            )
        )
        published = False
        try:
            self._write_durable(staging / "content", content)
            self._write_durable(staging / "meta.json", metadata)
            self._fsync_dir(staging)
            if record_path.exists():
                raise FileExistsError(f"Handle already exists: {handle}")
            try:
                staging.rename(record_path)
            except OSError as error:
                if record_path.exists():
                    raise FileExistsError(f"Handle already exists: {handle}") from error
                raise
            published = True
            try:
                self._fsync_dir(self._dir)
            except OSError:
                shutil.rmtree(record_path)
                published = False
                raise
        finally:
            if not published and staging.exists():
                shutil.rmtree(staging)

    def read_content(self, handle: str) -> str:
        return self.content_path(handle).read_text(encoding="utf-8")

    def read_meta(self, handle: str) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(
            self.meta_path(handle).read_text(encoding="utf-8")
        )
        return result

    def list_handles(self) -> list[dict[str, Any]]:
        """Return metadata for complete published records.

        Sorted by metadata file mtime descending (most recent first).
        Incomplete and hidden staging directories are skipped.
        """
        result: list[dict[str, Any]] = []
        try:
            paths = list(self._dir.iterdir())
        except OSError:
            return result

        records: list[tuple[float, Path]] = []
        for path in paths:
            if path.name.startswith("."):
                continue
            try:
                if path.is_dir() and self.exists(path.name):
                    records.append((self.meta_path(path.name).stat().st_mtime, path))
            except OSError:
                continue

        records.sort(key=lambda item: item[0], reverse=True)
        for _, record in records:
            handle = record.name
            if not self.exists(handle):
                continue
            try:
                meta = self.read_meta(handle)
                result.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
        return result

    def delete(self, handle: str) -> None:
        """Remove the complete immutable record (silently if missing)."""
        record = self.record_path(handle)
        if record.is_dir():
            shutil.rmtree(record)


def _get_store() -> HandleStore:
    """Return the shared HandleStore for the current session."""
    from ot.utils.session import get_session_dir

    return HandleStore(get_session_dir() / "ctx")


__all__ = [
    "HandleStore",
    "_get_store",
    "_resolve_handle",
    "expires_at_ts",
    "is_expired",
    "now_ts",
    "ttl_remaining",
]
