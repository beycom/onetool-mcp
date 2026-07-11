"""Flat-file handle storage for the ctx pack.

One session directory holds a "ctx/" subdirectory.
Each handle is stored as two files:
    <handle>       — raw content (UTF-8 text)
    <handle>.json  — metadata JSON (handle, source, format, size_bytes, etc.)
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def _resolve_handle(handle: Any) -> str:
    """Resolve a handle argument to a string handle ID.

    Transparently extracts the ID from a handle dict
    (``{"handle": "b2d18a1b", ...}``) — consistent with how
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
        f"handle must be a string (e.g. 'b2d18a1b'), got {type_name}. "
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


# ---------------------------------------------------------------------------
# HandleStore
# ---------------------------------------------------------------------------


class HandleStore:
    """Manages ctx handles in a flat directory."""

    def __init__(self, ctx_dir: Path) -> None:
        self._dir = ctx_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def content_path(self, handle: str) -> Path:
        return self._dir / handle

    def meta_path(self, handle: str) -> Path:
        return self._dir / f"{handle}.json"

    def exists(self, handle: str) -> bool:
        return self.meta_path(handle).exists() and self.content_path(handle).exists()

    @staticmethod
    def _write_atomic(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def write(self, handle: str, content: str, meta: dict[str, Any]) -> None:
        """Write content file then metadata file, each via tmp+rename (content-first)."""
        self._write_atomic(self.content_path(handle), content)
        self._write_atomic(self.meta_path(handle), json.dumps(meta, indent=2))

    def read_content(self, handle: str) -> str:
        return self.content_path(handle).read_text(encoding="utf-8")

    def read_meta(self, handle: str) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.meta_path(handle).read_text(encoding="utf-8"))
        return result

    def update_meta(self, handle: str, meta: dict[str, Any]) -> None:
        """Overwrite the metadata file via tmp+rename."""
        self._write_atomic(self.meta_path(handle), json.dumps(meta, indent=2))

    def list_handles(self) -> list[dict[str, Any]]:
        """Return metadata dicts for all handles that have both files.

        Sorted by metadata file mtime descending (most recent first).
        Entries where the content file is missing are skipped silently.
        """
        result: list[dict[str, Any]] = []
        try:
            meta_files = sorted(
                self._dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return result
        for meta_path in meta_files:
            handle = meta_path.stem
            if not self.content_path(handle).exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                result.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
        return result

    def delete(self, handle: str) -> None:
        """Unlink both content and metadata files (silently if missing)."""
        cp = self.content_path(handle)
        mp = self.meta_path(handle)
        if cp.exists():
            cp.unlink()
        if mp.exists():
            mp.unlink()


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
