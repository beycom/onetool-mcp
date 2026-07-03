"""Timer tools for measuring elapsed time across tool calls.

Provides named stopwatch timers that persist across multiple tool calls,
useful for profiling workflows, benchmarking API responses, or capturing
lap times during multi-step operations.

Example:
    ot_timer.start(name="api_call")
    # ... do work across multiple tool calls ...
    ot_timer.elapsed(name="api_call", store_as="api_total")
    ot_timer.list()
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from otpack import LogSpan

pack = "ot_timer"
pack_aliases = ("tmr",)

__all__ = ["clear", "elapsed", "list", "start"]

# Module-level state: active timers and stored results
_timers: dict[str, tuple[float, datetime]] = {}
_results: dict[str, dict[str, Any]] = {}
_MAX_TIMERS = 1000
_MAX_RESULTS = 1000


def _evict_oldest(d: dict[str, Any], limit: int) -> None:
    """Keep dict size bounded by evicting oldest inserted keys."""
    while len(d) > limit:
        oldest_key = next(iter(d))
        del d[oldest_key]


def start(*, name: str = "_default") -> dict[str, Any]:
    """Start or restart a named timer.

    Args:
        name: Timer name. Defaults to "_default".

    Returns:
        Confirmation with timer name and wall-clock start time.
    """
    with LogSpan(span="ot_timer.start", name=name):
        now_perf = perf_counter()
        now_wall = datetime.now(UTC)
        _timers[name] = (now_perf, now_wall)
        _evict_oldest(_timers, _MAX_TIMERS)
        return {"status": "started", "name": name, "started_at": now_wall.isoformat()}


def elapsed(*, name: str = "_default", store_as: str | None = None) -> dict[str, Any] | str:
    """Get elapsed time for a named timer.

    The timer keeps running after this call (lap behaviour).

    Args:
        name: Timer name to check. Defaults to "_default".
        store_as: If provided, store the result under this key for later retrieval via list().

    Returns:
        Dict with elapsed seconds and formatted duration, or error string if timer not found.
    """
    with LogSpan(span="ot_timer.elapsed", name=name):
        if name not in _timers:
            return f"No timer named '{name}' is running. Call ot_timer.start(name='{name}') first."

        start_perf, start_wall = _timers[name]
        elapsed_secs = perf_counter() - start_perf
        result = {
            "name": name,
            "elapsed_seconds": round(elapsed_secs, 6),
            "elapsed_formatted": _format_duration(elapsed_secs),
            "started_at": start_wall.isoformat(),
        }

        if store_as is not None:
            _results[store_as] = result
            _evict_oldest(_results, _MAX_RESULTS)

        return result


def list() -> dict[str, Any]:
    """Return all stored timer results and currently running timers.

    Returns:
        Dict with stored results and active timer names.
    """
    with LogSpan(span="ot_timer.list"):
        active = {
            name: {"started_at": wall.isoformat()}
            for name, (_perf, wall) in _timers.items()
        }
        return {"stored": dict(_results), "active": active}


def clear(*, results: bool = False) -> dict[str, Any]:
    """Clear all running timers and optionally stored results.

    Args:
        results: If True, also clear stored results. Defaults to False.

    Returns:
        Confirmation with count of timers and results cleared.
    """
    with LogSpan(span="ot_timer.clear", results=results):
        timer_count = len(_timers)
        result_count = len(_results) if results else 0
        _timers.clear()
        if results:
            _results.clear()
        return {"status": "cleared", "timers_removed": timer_count, "results_removed": result_count}


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.3f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.3f}s"
