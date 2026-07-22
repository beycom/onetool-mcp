"""Small immutable process-local content-addressed cache."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from threading import Lock


class ContentAddressedCache:
    """Store immutable bytes under SHA-256 identities with bounded LRU eviction."""

    def __init__(self, *, max_entries: int = 32, max_bytes: int = 64 * 1024 * 1024) -> None:
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("Content-addressed cache bounds must be positive")
        self._values: OrderedDict[str, bytes] = OrderedDict()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._size = 0
        self._lock = Lock()

    @staticmethod
    def key(*parts: bytes) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
        return digest.hexdigest()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            value = self._values.get(key)
            if value is not None:
                self._values.move_to_end(key)
            return value

    def put(self, key: str, value: bytes) -> None:
        immutable = bytes(value)
        with self._lock:
            existing = self._values.get(key)
            if existing is not None and existing != immutable:
                raise ValueError(f"Content-addressed cache collision for {key}")
            if existing is not None:
                self._values.move_to_end(key)
                return
            if len(immutable) > self._max_bytes:
                return
            self._values[key] = immutable
            self._size += len(immutable)
            while len(self._values) > self._max_entries or self._size > self._max_bytes:
                _, removed = self._values.popitem(last=False)
                self._size -= len(removed)

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)


LIKEC4_COMPILE_CACHE = ContentAddressedCache()
LIKEC4_EXPORT_CACHE = ContentAddressedCache()
