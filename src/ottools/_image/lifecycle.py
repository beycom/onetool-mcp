"""Lifecycle tools for the image pack: list, delete, purge.

Manages images stored in ``.onetool/images/`` — scans meta.json files,
removes individual handles, and bulk-purges by age.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .store import _images_dir, cache_evict, delete_handle_files, load_meta


def list_images() -> list[dict[str, Any]]:
    """List all images in ``.onetool/images/``.

    Returns:
        List of dicts, one per image, with keys: ``handle``, ``source``,
        ``dims``, ``resized``, ``created_at``, ``summary`` (bool), ``type``
        (``null`` if summary has not been called).
    """
    results: list[dict[str, Any]] = []
    for meta_path in sorted(_images_dir().glob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        has_summary = meta.get("summary") is not None
        results.append(
            {
                "handle": f"#{meta.get('handle', meta_path.stem)}",
                "source": meta.get("source", ""),
                "dims": meta.get("original_dims"),
                "resized": meta.get("resized", False),
                "created_at": meta.get("created_at", ""),
                "summary": has_summary,
                "type": meta.get("summary", {}).get("type") if has_summary else None,
            }
        )
    return results


def delete_image(*, handle: str) -> dict[str, Any]:
    """Delete a loaded image and remove it from the session cache.

    Args:
        handle: Handle string with or without ``#`` prefix.

    Returns:
        ``{"deleted": "#name", "bytes_freed": N}`` on success, or
        ``{"error": str}`` if the handle was not found.

    Example:
        image.delete(handle="#img_a3f7b2c4")
    """
    handle_name = handle.lstrip("#")
    found, freed = delete_handle_files(handle_name)
    if not found:
        return {"error": f"handle #{handle_name} not found"}
    cache_evict(handle_name)
    return {"deleted": f"#{handle_name}", "bytes_freed": freed}


def purge_images(*, all: bool = False, minutes: int = 15) -> dict[str, Any]:
    """Delete images from ``.onetool/images/``, optionally filtered by age.

    Args:
        all: If True, delete all images regardless of age.
        minutes: Delete images older than this many minutes. Must be positive.
            Defaults to 15. Ignored when ``all=True``.

    Returns:
        ``{"purged": N, "bytes_freed": N}`` — count and content bytes removed.

    Raises:
        ValueError: If ``minutes`` is zero or negative.

    Example:
        image.purge()              # delete images older than 15 minutes
        image.purge(minutes=60)    # delete images older than 1 hour
        image.purge(all=True)      # delete all images
    """
    if not all and minutes <= 0:
        raise ValueError("minutes must be a positive integer")

    cutoff: datetime | None = None
    if not all:
        cutoff = datetime.now(UTC) - timedelta(minutes=minutes)

    count = 0
    total_freed = 0

    for meta_path in _images_dir().glob("*.meta.json"):
        handle_name = meta_path.name.removesuffix(".meta.json")

        if cutoff is not None:
            meta = load_meta(handle_name)
            if meta is None:
                continue
            created_str = meta.get("created_at", "")
            try:
                created = datetime.fromisoformat(created_str)
            except (ValueError, TypeError):
                continue
            if created >= cutoff:
                continue

        found, freed = delete_handle_files(handle_name)
        if found:
            cache_evict(handle_name)
            count += 1
            total_freed += freed

    return {"purged": count, "bytes_freed": total_freed}


