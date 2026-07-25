"""Management tools for the ctx pack: list, inspect, stats."""

from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, is_expired, ttl_remaining

log = LogSpan

_VALID_STATUSES = {"ready", "failed"}


def ctx_list(
    *,
    source: str = "",
    status: str = "",
    store: HandleStore | None = None,
) -> list[dict[str, Any]]:
    """Return all active (non-expired) handles with summary information.

    Args:
        source: Filter by source substring (case-insensitive)
        status: Filter by status ("ready", "failed")
        store: HandleStore instance (uses session default if not provided)
    """
    if status and status not in _VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Valid values: {', '.join(sorted(_VALID_STATUSES))}"
        )

    with log(span="ctx.list", source=source or None, status=status or None) as s:
        if store is None:
            store = _get_store()

        all_meta = store.list_handles()
        active: list[dict[str, Any]] = []

        for meta in all_meta:
            if is_expired(meta):
                continue
            if source and source.lower() not in (meta.get("source") or "").lower():
                continue
            if status and meta.get("status") != status:
                continue

            handle = meta["handle"]
            active.append(
                {
                    "handle": handle,
                    "source": meta.get("source") or "",
                    "format": meta.get("format", "text"),
                    "size_bytes": meta.get("size_bytes", 0),
                    "total_lines": meta.get("total_lines", 0),
                    "status": meta.get("status", "ready"),
                    "command": f"ctx.read('{handle}')",
                    "ttl_remaining": int(ttl_remaining(meta)),
                }
            )

        s.add("count", len(active))
        return active


def ctx_inspect(
    handle: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Return detailed metadata for a single handle.

    Args:
        handle: Context store handle
        store: HandleStore instance (uses session default if not provided)
    """
    with log(span="ctx.inspect", handle=handle):
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        if not store.exists(handle):
            return {"error": f"Handle not found: {handle}"}

        try:
            meta = store.read_meta(handle)
        except (OSError, ValueError):
            return {"error": f"Handle not found: {handle}"}

        toc: list[dict[str, Any]] = meta.get("toc", [])

        return {
            "handle": meta["handle"],
            "source": meta.get("source") or "",
            "format": meta.get("format", "text"),
            "size_bytes": meta.get("size_bytes", 0),
            "total_lines": meta.get("total_lines", 0),
            "status": meta.get("status", "ready"),
            "created_at": meta.get("created_at"),
            "toc_entries": len(toc),
            "ttl_remaining": int(ttl_remaining(meta)),
        }


def ctx_stats(
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Return session-level storage metrics.

    Returns total_handles, handles_by_status (dict), total_bytes_stored,
    estimated_tokens_saved.
    """
    with log(span="ctx.stats") as s:
        if store is None:
            store = _get_store()

        all_meta = store.list_handles()
        handles_by_status: dict[str, int] = {}
        total_bytes = 0
        total_handles = 0

        for meta in all_meta:
            if is_expired(meta):
                continue
            st = meta.get("status", "ready")
            handles_by_status[st] = handles_by_status.get(st, 0) + 1
            total_bytes += meta.get("size_bytes", 0)
            total_handles += 1

        estimated_tokens_saved = total_bytes // 4

        s.add("total_handles", total_handles)
        s.add("total_bytes", total_bytes)
        return {
            "total_handles": total_handles,
            "handles_by_status": handles_by_status,
            "total_bytes_stored": total_bytes,
            "estimated_tokens_saved": estimated_tokens_saved,
        }


__all__ = ["ctx_inspect", "ctx_list", "ctx_stats"]
