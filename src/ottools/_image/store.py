"""Disk storage and session LRU cache for the image pack.

Images are stored in ``.onetool/images/`` as ``{handle}.png`` +
``{handle}.meta.json`` pairs. An in-memory LRU cache holds base64-encoded
model bytes for the most recently used images to avoid redundant disk I/O.
"""

from __future__ import annotations

import atexit
import base64
import json
import threading
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

from ot.utils.fs import unlink_tracking_bytes
from ot.utils.session import get_session_dir
from otpack import Cache

from .config import get_image_config

# Session LRU cache — sized once at module load from config.
# Config changes after first import of this module are not reflected.
_session_cache = Cache(max_size=get_image_config().session_cache_size)

# Serialises meta.json read-modify-write — the background-summary daemon
# thread races the main thread in save_summary().
_meta_lock = threading.Lock()


def _images_dir() -> Path:
    """Return (and create) the images subdirectory within the session directory."""
    p = get_session_dir() / "images"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------


def save_image(raw_bytes: bytes, handle_name: str, meta: dict[str, Any]) -> None:
    """Save image bytes and metadata to ``.onetool/images/``.

    Writes ``{handle_name}.png`` (verbatim original) and
    ``{handle_name}.meta.json``.

    Args:
        raw_bytes: Original image bytes (saved unmodified).
        handle_name: Handle name without ``#`` prefix (e.g. ``"img_a3f7b2c4"``).
        meta: Metadata dict to serialise as JSON.
    """
    images = _images_dir()
    (images / f"{handle_name}.png").write_bytes(raw_bytes)
    (images / f"{handle_name}.meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )


def load_raw_bytes(handle_name: str) -> bytes | None:
    """Read raw image bytes from disk.

    Args:
        handle_name: Handle name without ``#`` prefix.

    Returns:
        Raw bytes, or ``None`` if the file does not exist.
    """
    path = _images_dir() / f"{handle_name}.png"
    return path.read_bytes() if path.exists() else None


def load_meta(handle_name: str) -> dict[str, Any] | None:
    """Read and parse ``meta.json`` for a handle.

    Args:
        handle_name: Handle name without ``#`` prefix.

    Returns:
        Parsed metadata dict, or ``None`` if not found.
    """
    path = _images_dir() / f"{handle_name}.meta.json"
    if not path.exists():
        return None
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def save_summary(handle_name: str, summary_dict: dict[str, Any]) -> None:
    """Write the summary field into an existing ``meta.json`` in-place.

    The read-modify-write runs under ``_meta_lock`` and the file is replaced
    atomically (tmp file + ``Path.replace``) — safe against the background
    summary daemon thread racing the main thread.

    Args:
        handle_name: Handle name without ``#`` prefix.
        summary_dict: Summary dict to store in the ``"summary"`` field.

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist for the handle.
    """
    with _meta_lock:
        meta = load_meta(handle_name)
        if meta is None:
            raise FileNotFoundError(f"meta.json not found for handle: {handle_name}")
        meta["summary"] = summary_dict
        path = _images_dir() / f"{handle_name}.meta.json"
        tmp = path.parent / f"{path.name}.tmp"
        tmp.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)


def find_by_hash(sha256_hex: str) -> str | None:
    """Scan ``meta.json`` files for one matching the given SHA-256 hash.

    Args:
        sha256_hex: Full SHA-256 hex string to search for.

    Returns:
        Existing handle name (without ``#``) if found, else ``None``.
    """
    for meta_path in _images_dir().glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("hash") == sha256_hex:
                return str(meta.get("handle", ""))
        except (json.JSONDecodeError, OSError):
            continue
    return None


def delete_handle_files(handle_name: str) -> tuple[bool, int]:
    """Delete the ``.png`` and ``.meta.json`` files for a handle.

    Args:
        handle_name: Handle name without ``#`` prefix.

    Returns:
        Tuple of ``(found, bytes_freed)`` — ``found`` is False if neither
        file existed.
    """
    images = _images_dir()
    png = images / f"{handle_name}.png"
    meta_path = images / f"{handle_name}.meta.json"
    freed = sum(unlink_tracking_bytes(p) for p in (png, meta_path))
    found = freed > 0
    return found, freed


# ---------------------------------------------------------------------------
# Session LRU cache
# ---------------------------------------------------------------------------


def cache_put(handle_name: str, model_bytes: bytes) -> None:
    """Add or update an entry in the session LRU cache.

    Args:
        handle_name: Handle name without ``#`` prefix.
        model_bytes: Resized PNG bytes — base64-encoded before storing.
    """
    b64 = base64.b64encode(model_bytes).decode()
    _session_cache.set(handle_name, b64)


def cache_get(handle_name: str) -> str | None:
    """Retrieve base64 model bytes from the cache, updating LRU order.

    Args:
        handle_name: Handle name without ``#`` prefix.

    Returns:
        Base64-encoded model bytes, or ``None`` if not cached.
    """
    return _session_cache.get(handle_name)


def cache_evict(handle_name: str) -> None:
    """Remove a specific handle from the session cache.

    Args:
        handle_name: Handle name without ``#`` prefix.
    """
    _session_cache.evict(handle_name)


atexit.register(_session_cache.clear)
