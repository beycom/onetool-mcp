"""Thread-safe in-memory LRU cache with optional TTL.

Provides a general-purpose ``Cache`` class and a singleton ``cache`` instance
for function memoization.

Example::

    from ot.utils.cache import cache

    # Memoize a function for 1 hour
    @cache.memoize(ttl=3600)
    def _resolve_library_id(library_id: str) -> str:
        ...

    # Manual cache operations
    cache.set("key", value)
    result = cache.get("key")
    cache.evict("key")
    cache.clear()
"""

from __future__ import annotations

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

__all__ = ["Cache", "cache"]

F = TypeVar("F", bound=Callable[..., Any])


class _Entry:
    """A cached value with optional expiration time."""

    __slots__ = ("expires_at", "value")

    def __init__(self, value: Any, ttl: float | None) -> None:
        self.value = value
        self.expires_at: float | None = (
            (time.monotonic() + ttl) if ttl is not None else None
        )


class Cache:
    """Thread-safe in-memory LRU cache with optional TTL.

    Args:
        max_size: Maximum number of entries. ``0`` means unlimited (only TTL
            expiry applies). Defaults to ``0``.
        ttl: Default time-to-live in seconds. ``None`` means entries never
            expire. Defaults to ``None``.
    """

    def __init__(self, *, max_size: int = 0, ttl: float | None = None) -> None:
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Return cached value, promoting LRU order. ``None`` if missing or expired.

        Args:
            key: Cache key.

        Returns:
            Cached value, or ``None`` if absent or past TTL.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        """Store value. Uses construction-time TTL unless overridden.

        Evicts LRU entry if over ``max_size``.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Optional per-call TTL override in seconds.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = _Entry(value, effective_ttl)
            if self._max_size > 0:
                while len(self._store) > self._max_size:
                    self._store.popitem(last=False)

    def evict(self, key: str) -> None:
        """Remove a specific key (no-op if absent).

        Args:
            key: Cache key to remove.
        """
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._store.clear()

    def keys(self) -> list[str]:
        """Snapshot of current keys.

        Returns:
            List of all current cache keys.
        """
        with self._lock:
            return list(self._store.keys())

    def memoize(self, ttl: float = 300.0) -> Callable[[F], F]:
        """Decorator that memoizes a function's return value with TTL.

        Keys are prefixed with the function's qualified name to avoid collisions
        when multiple functions share the same ``Cache`` instance.

        Args:
            ttl: Time-to-live in seconds (default: 5 minutes).

        Returns:
            Decorator function.

        Example::

            @cache.memoize(ttl=3600)
            def expensive(query: str) -> str:
                ...
        """

        def decorator(func: F) -> F:
            func_prefix = f"{func.__module__}.{func.__qualname__}:"

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key_parts = [repr(arg) for arg in args]
                key_parts.extend(f"{k}={v!r}" for k, v in sorted(kwargs.items()))
                cache_key = func_prefix + ":".join(key_parts)

                # Wrap in a 1-tuple so None results are cached correctly.
                # cache.get() returns None for misses; a tuple is never None.
                cached = self.get(cache_key)
                if cached is not None:
                    return cached[0]

                result = func(*args, **kwargs)
                self.set(cache_key, (result,), ttl=ttl)
                return result

            return wrapper  # type: ignore[return-value]

        return decorator


# Singleton instance — unlimited size, TTL controlled per-call via memoize()
cache = Cache(max_size=0)
