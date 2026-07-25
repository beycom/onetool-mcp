"""Content-addressed disk storage and session cache for the image pack."""

from __future__ import annotations

import atexit
import base64
import json
import re
import threading
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

from ot.utils.fs import unlink_tracking_bytes
from ot.utils.session import get_session_dir
from otpack import Cache

from .config import get_image_config

_session_cache = Cache(max_size=get_image_config().session_cache_size)
_meta_lock = threading.Lock()

_HANDLE_NAME_RE = re.compile(r"img_[0-9a-f]{64}")
_PUBLIC_HANDLE_RE = re.compile(r"#img_[0-9a-f]{64}")
_META_FILENAME_RE = re.compile(r"(img_[0-9a-f]{64})\.meta\.json")

_FORMAT_EXTENSIONS: dict[str, str] = {
    "PNG": "png",
    "JPEG": "jpg",
    "GIF": "gif",
    "WEBP": "webp",
    "TIFF": "tiff",
    "HEIC": "heic",
    "AVIF": "avif",
    "SVG": "svg",
}


def validate_handle_name(handle_name: str) -> str:
    """Validate and return a canonical internal image handle name."""
    if _HANDLE_NAME_RE.fullmatch(handle_name) is None:
        raise ValueError(
            "invalid image handle name; expected img_ followed by "
            "64 lowercase hexadecimal characters"
        )
    return handle_name


def parse_public_handle(handle: str) -> str:
    """Validate a canonical public image reference and return its name."""
    if _PUBLIC_HANDLE_RE.fullmatch(handle) is None:
        raise ValueError(
            "invalid image reference; expected #img_ followed by "
            "64 lowercase hexadecimal characters"
        )
    return handle[1:]


def public_handle(handle_name: str) -> str:
    """Return the public reference for a validated internal handle name."""
    return f"#{validate_handle_name(handle_name)}"


def handle_name_for_hash(sha256_hex: str) -> str:
    """Return the canonical internal handle for a complete SHA-256 digest."""
    if re.fullmatch(r"[0-9a-f]{64}", sha256_hex) is None:
        raise ValueError("image SHA-256 must be 64 lowercase hexadecimal characters")
    return f"img_{sha256_hex}"


def ext_for_format(fmt: str) -> str:
    """Map a supported detected image format to its storage extension."""
    try:
        return _FORMAT_EXTENSIONS[fmt.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported stored image format: {fmt!r}") from exc


def _images_dir() -> Path:
    """Return and create the session image directory."""
    session = get_session_dir()
    path = session / "images"
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.resolve().parent != session.resolve():
        raise ValueError("session image directory must not be a symlink")
    return path


def _direct_child(filename: str) -> Path:
    """Return a safe exact child path and reject existing symlink redirection."""
    images = _images_dir()
    path = images / filename
    if path.parent != images:
        raise ValueError("image storage path is not a direct child")
    if path.is_symlink():
        raise ValueError(f"image storage path must not be a symlink: {filename}")
    if path.resolve(strict=False).parent != images.resolve():
        raise ValueError(
            f"image storage path escapes the session directory: {filename}"
        )
    return path


def _meta_path(handle_name: str) -> Path:
    return _direct_child(f"{validate_handle_name(handle_name)}.meta.json")


def _validate_meta(handle_name: str, meta: object) -> dict[str, Any]:
    if not isinstance(meta, dict):
        raise ValueError(f"invalid metadata for {public_handle(handle_name)}")
    typed = cast("dict[str, Any]", meta)
    if typed.get("handle") != handle_name:
        raise ValueError(f"metadata handle mismatch for {public_handle(handle_name)}")
    digest = handle_name.removeprefix("img_")
    if typed.get("hash") != digest:
        raise ValueError(f"metadata hash mismatch for {public_handle(handle_name)}")
    if "file" in typed:
        raise ValueError(f"obsolete metadata filename for {public_handle(handle_name)}")
    original_format = typed.get("original_format")
    if not isinstance(original_format, str):
        raise ValueError(f"invalid metadata format for {public_handle(handle_name)}")
    ext_for_format(original_format)
    return typed


def _content_path(handle_name: str, meta: dict[str, Any]) -> Path:
    ext = ext_for_format(cast("str", meta["original_format"]))
    return _direct_child(f"{validate_handle_name(handle_name)}.{ext}")


def save_image(
    raw_bytes: bytes, handle_name: str, meta: dict[str, Any], *, fmt: str
) -> None:
    """Atomically save original bytes and canonical metadata."""
    handle_name = validate_handle_name(handle_name)
    if meta.get("original_format") != fmt.upper():
        raise ValueError("metadata format does not match detected image format")
    validated_meta = _validate_meta(handle_name, meta)
    content_path = _content_path(handle_name, validated_meta)
    meta_path = _meta_path(handle_name)
    content_tmp = _direct_child(f"{handle_name}.content.tmp")
    meta_tmp = _direct_child(f"{handle_name}.meta.tmp")
    if content_path.exists() or meta_path.exists():
        raise FileExistsError(
            f"image entry already exists: {public_handle(handle_name)}"
        )

    try:
        content_tmp.write_bytes(raw_bytes)
        meta_tmp.write_text(
            json.dumps(validated_meta, indent=2, default=str),
            encoding="utf-8",
        )
        content_tmp.replace(content_path)
        meta_tmp.replace(meta_path)
    except BaseException:
        content_tmp.unlink(missing_ok=True)
        meta_tmp.unlink(missing_ok=True)
        if content_path.exists() and not meta_path.exists():
            content_path.unlink()
        raise


def load_meta(handle_name: str) -> dict[str, Any] | None:
    """Load and validate canonical metadata for an internal handle name."""
    handle_name = validate_handle_name(handle_name)
    path = _meta_path(handle_name)
    if not path.exists():
        return None
    meta = _validate_meta(
        handle_name,
        json.loads(path.read_text(encoding="utf-8")),
    )
    _content_path(handle_name, meta)
    return meta


def load_raw_bytes(handle_name: str) -> bytes | None:
    """Read original bytes from the exact canonical content path."""
    meta = load_meta(handle_name)
    if meta is None:
        return None
    path = _content_path(handle_name, meta)
    if not path.exists():
        return None
    return path.read_bytes()


def save_summary(handle_name: str, summary_dict: dict[str, Any]) -> None:
    """Atomically add a summary to canonical metadata."""
    handle_name = validate_handle_name(handle_name)
    with _meta_lock:
        meta = load_meta(handle_name)
        if meta is None:
            raise FileNotFoundError(
                f"meta.json not found for handle: {public_handle(handle_name)}"
            )
        meta["summary"] = summary_dict
        path = _meta_path(handle_name)
        tmp = _direct_child(f"{handle_name}.summary.tmp")
        try:
            tmp.write_text(
                json.dumps(meta, indent=2, default=str),
                encoding="utf-8",
            )
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)


def iter_handle_names() -> Iterator[str]:
    """Yield canonical handle names with safe metadata paths."""
    images = _images_dir()
    for path in sorted(images.iterdir()):
        match = _META_FILENAME_RE.fullmatch(path.name)
        if match is None or path.is_symlink():
            continue
        try:
            safe_path = _direct_child(path.name)
        except ValueError:
            continue
        if safe_path.is_file():
            yield match.group(1)


def delete_handle_files(handle_name: str) -> tuple[bool, int]:
    """Delete only the exact canonical content and metadata paths."""
    handle_name = validate_handle_name(handle_name)
    meta = load_meta(handle_name)
    if meta is None:
        return False, 0
    content_path = _content_path(handle_name, meta)
    meta_path = _meta_path(handle_name)
    found = content_path.exists() or meta_path.exists()
    freed = 0
    for path in (content_path, meta_path):
        if path.exists():
            freed += unlink_tracking_bytes(path)
    return found, freed


def cache_put(handle_name: str, model_bytes: bytes) -> None:
    """Add model bytes for a canonical handle to the session LRU cache."""
    handle_name = validate_handle_name(handle_name)
    _session_cache.set(handle_name, base64.b64encode(model_bytes).decode())


def cache_get(handle_name: str) -> str | None:
    """Get cached model bytes for a canonical handle and promote LRU order."""
    return cast("str | None", _session_cache.get(validate_handle_name(handle_name)))


def cache_evict(handle_name: str) -> None:
    """Evict one canonical handle from the session LRU cache."""
    _session_cache.evict(validate_handle_name(handle_name))


atexit.register(_session_cache.clear)
