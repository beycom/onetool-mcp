"""Tests for the shared otpack Cache singleton bound (p12 R8 P2)."""

from __future__ import annotations

import pytest

from otpack.cache import Cache, cache


@pytest.mark.unit
@pytest.mark.pkg
class TestCacheBound:
    """R8 P2: the shared singleton is bounded so LRU eviction engages."""

    def test_singleton_is_bounded(self) -> None:
        """The shared cache singleton has a finite max_size (no unbounded growth)."""
        assert cache._max_size > 0

    def test_lru_evicts_oldest_beyond_bound(self) -> None:
        """Once max_size distinct keys are exceeded, oldest entries are evicted."""
        c = Cache(max_size=3)
        for i in range(5):
            c.set(f"k{i}", i)
        keys = c.keys()
        assert len(keys) == 3
        # The two oldest (k0, k1) were evicted; the three newest remain.
        assert keys == ["k2", "k3", "k4"]

    def test_access_promotes_lru_order(self) -> None:
        """Accessing an entry protects it from eviction (LRU, not FIFO)."""
        c = Cache(max_size=3)
        for i in range(3):
            c.set(f"k{i}", i)
        c.get("k0")  # promote k0 to most-recently-used
        c.set("k3", 3)  # evicts the now-oldest (k1)
        assert "k0" in c.keys()
        assert "k1" not in c.keys()
