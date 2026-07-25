"""Lifecycle tools for canonical session-scoped image entries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .store import (
    cache_evict,
    delete_handle_files,
    iter_handle_names,
    load_meta,
    parse_public_handle,
    public_handle,
)


def list_images() -> list[dict[str, Any]]:
    """List valid canonical images in the current session."""
    results: list[dict[str, Any]] = []
    for handle_name in iter_handle_names():
        try:
            meta = load_meta(handle_name)
        except (OSError, ValueError):
            continue
        if meta is None:
            continue
        summary = meta.get("summary")
        results.append(
            {
                "handle": public_handle(handle_name),
                "source": meta.get("source", ""),
                "dims": meta.get("original_dims"),
                "resized": meta.get("resized", False),
                "created_at": meta.get("created_at", ""),
                "summary": summary is not None,
                "type": summary.get("type") if isinstance(summary, dict) else None,
            }
        )
    return results


def delete_image(*, handle: str) -> dict[str, Any]:
    """Delete one image by its canonical public reference."""
    try:
        handle_name = parse_public_handle(handle)
        found, freed = delete_handle_files(handle_name)
    except (OSError, ValueError) as exc:
        return {"error": str(exc)}
    if not found:
        return {"error": f"handle {handle} not found"}
    cache_evict(handle_name)
    return {"deleted": handle, "bytes_freed": freed}


def purge_images(*, all: bool = False, minutes: int = 15) -> dict[str, Any]:
    """Delete valid canonical images, optionally filtered by age."""
    if not all and minutes <= 0:
        raise ValueError("minutes must be a positive integer")

    cutoff = None if all else datetime.now(UTC) - timedelta(minutes=minutes)
    count = 0
    total_freed = 0

    for handle_name in list(iter_handle_names()):
        try:
            meta = load_meta(handle_name)
            if meta is None:
                continue
            if cutoff is not None:
                created = datetime.fromisoformat(str(meta.get("created_at", "")))
                if created >= cutoff:
                    continue
            found, freed = delete_handle_files(handle_name)
        except (OSError, TypeError, ValueError):
            continue
        if found:
            cache_evict(handle_name)
            count += 1
            total_freed += freed

    return {"purged": count, "bytes_freed": total_freed}
