"""In-memory caching with TTL for worker tools.

Provides both a decorator for function memoization and manual cache operations.
Cache persists for the lifetime of the worker process.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class CacheEntry:
    """A cached value with expiration time."""

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.time() + ttl


class CacheNamespace:
    """Cache namespace with get/set/clear operations and decorator."""

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._memoize_stores: dict[str, dict[str, CacheEntry]] = {}

    def get(self, key: str) -> Any | None:
        """Get a cached value by key.

        Args:
            key: Cache key

        Returns:
            Cached value, or None if not found or expired
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float = 300.0) -> None:
        """Set a cached value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        self._store[key] = CacheEntry(value, ttl)

    def clear(self, key: str | None = None) -> None:
        """Clear cached values.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._store.clear()
            self._memoize_stores.clear()
        else:
            self._store.pop(key, None)

    def __call__(self, ttl: float = 300.0) -> Callable[[F], F]:
        """Decorator for memoizing function results with TTL.

        Args:
            ttl: Time-to-live in seconds (default: 5 minutes)

        Returns:
            Decorator function

        Example:
            @cache(ttl=60)
            def expensive_operation(query: str) -> str:
                ...
        """

        def decorator(func: F) -> F:
            # Create a separate store for this function
            func_id = f"{func.__module__}.{func.__qualname__}"
            self._memoize_stores[func_id] = {}

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Build cache key from args and kwargs
                key_parts = [repr(arg) for arg in args]
                key_parts.extend(f"{k}={v!r}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

                # Get or create store (may have been cleared by cache.clear())
                store = self._memoize_stores.get(func_id)
                if store is None:
                    store = {}
                    self._memoize_stores[func_id] = store
                entry = store.get(cache_key)

                if entry is not None and time.time() <= entry.expires_at:
                    return entry.value

                result = func(*args, **kwargs)
                store[cache_key] = CacheEntry(result, ttl)
                return result

            return wrapper  # type: ignore[return-value]

        return decorator


# Singleton instance
cache = CacheNamespace()
