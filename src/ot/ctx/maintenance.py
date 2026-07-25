"""Maintenance tools for the ctx pack: delete and purge."""

from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, is_expired, now_ts

log = LogSpan


def ctx_delete(
    handle: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Delete a single immutable handle record.

    Args:
        handle: Context store handle to delete.
        store: HandleStore instance (uses session default if not provided).
    """
    with log(span="ctx.delete", handle=handle):
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        if not store.exists(handle):
            return {"error": f"Handle not found: {handle}"}

        store.delete(handle)
        return {"deleted": handle}


def ctx_purge(
    *,
    delete_all: bool = False,
    minutes: int | None = None,
    source: str = "",
    status: str = "",
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Delete handles matching the given filters.

    With no filters: deletes only handles that have passed their TTL, so a
    routine cleanup never removes handles a caller may still hold.
    With ``minutes``: deletes handles older than that many minutes regardless
    of TTL.
    With ``delete_all=True``: ignores the age filter — deletes every handle
    that matches the ``source``/``status`` filters (or all handles when no
    filters are given).

    Args:
        delete_all: If True, bypass the age filter. Source/status filters still apply.
        minutes: Delete handles older than this many minutes. Must be positive.
            Defaults to deleting only expired handles.
            Ignored when ``delete_all=True``.
        source: Source substring filter (case-insensitive).
        status: Status filter ("ready", "failed").
        store: HandleStore instance (uses session default if not provided).

    Returns:
        Dict with "deleted" (handle count) and "bytes_freed" (content bytes removed).

    Raises:
        ValueError: If ``minutes`` is zero or negative.

    Examples:
        ctx.purge()                                 # delete expired handles (past TTL)
        ctx.purge(delete_all=True)                  # wipe everything
        ctx.purge(minutes=60)                       # delete handles older than 1 hour
        ctx.purge(source="brave")                   # delete expired brave handles
        ctx.purge(delete_all=True, source="brave")  # delete ALL brave handles regardless of age
        ctx.purge(status="failed")                  # delete expired failed handles
        ctx.purge(delete_all=True, status="failed") # delete ALL failed handles regardless of age
    """
    if not delete_all and minutes is not None and minutes <= 0:
        raise ValueError("minutes must be a positive integer")

    with log(
        span="ctx.purge",
        delete_all=delete_all or None,
        minutes=minutes if not delete_all else None,
        source=source or None,
        status=status or None,
    ) as s:
        if store is None:
            store = _get_store()

        cutoff_ts = (
            None if (delete_all or minutes is None) else (now_ts() - minutes * 60)
        )
        all_meta = store.list_handles()

        to_delete: list[dict[str, Any]] = []
        for meta in all_meta:
            if not delete_all and minutes is None and not is_expired(meta):
                continue
            if cutoff_ts is not None and meta.get("created_at", 0) > cutoff_ts:
                continue
            if source and source.lower() not in (meta.get("source") or "").lower():
                continue
            if status and meta.get("status") != status:
                continue
            to_delete.append(meta)

        bytes_freed = sum(m.get("size_bytes", 0) for m in to_delete)
        deleted = 0

        for meta in to_delete:
            handle = meta["handle"]
            store.delete(handle)
            deleted += 1

        s.add("deleted", deleted)
        s.add("bytes_freed", bytes_freed)
        return {"deleted": deleted, "bytes_freed": bytes_freed}


__all__ = ["ctx_delete", "ctx_purge"]
