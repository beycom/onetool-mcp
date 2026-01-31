"""Tests for tool loader module cache behavior."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def isolated_cache() -> Generator[None, None, None]:
    """Isolate module cache state for testing."""
    import ot.executor.tool_loader as loader

    original_cache = loader._module_cache.copy()
    original_maxsize = loader._MODULE_CACHE_MAXSIZE
    loader._module_cache.clear()

    yield

    loader._module_cache.clear()
    loader._module_cache.update(original_cache)
    loader._MODULE_CACHE_MAXSIZE = original_maxsize


@pytest.mark.unit
@pytest.mark.core
class TestModuleCacheBounds:
    """Tests for module cache size limits."""

    def test_module_cache_has_maxsize(self):
        """Module cache should have a defined maxsize constant."""
        import ot.executor.tool_loader as loader

        assert hasattr(loader, "_MODULE_CACHE_MAXSIZE")
        assert loader._MODULE_CACHE_MAXSIZE > 0

    def test_module_cache_is_ordered_dict(self):
        """Module cache should use OrderedDict for LRU semantics."""
        import ot.executor.tool_loader as loader

        assert isinstance(loader._module_cache, OrderedDict)

    def test_cache_get_returns_none_for_missing(self):
        """_cache_get should return None for missing keys."""
        import ot.executor.tool_loader as loader

        result = loader._cache_get(Path("/nonexistent/path"))
        assert result is None

    def test_cache_set_enforces_maxsize(self, isolated_cache):  # noqa: ARG002
        """_cache_set should evict oldest entries when maxsize exceeded."""
        import ot.executor.tool_loader as loader
        from ot.executor.tool_loader import LoadedTools

        loader._MODULE_CACHE_MAXSIZE = 3
        mock_tools = LoadedTools(functions={}, packs={}, worker_tools=[])

        # Add entries up to and beyond maxsize
        for i in range(5):
            path = Path(f"/test/path/{i}")
            loader._cache_set(path, (mock_tools, {f"file{i}": float(i)}))

        # Should only have maxsize entries
        assert len(loader._module_cache) == 3

        # Oldest entries should be evicted (paths 0 and 1)
        assert Path("/test/path/0") not in loader._module_cache
        assert Path("/test/path/1") not in loader._module_cache

        # Newest entries should remain
        assert Path("/test/path/2") in loader._module_cache
        assert Path("/test/path/3") in loader._module_cache
        assert Path("/test/path/4") in loader._module_cache

    def test_cache_get_updates_lru_order(self, isolated_cache):  # noqa: ARG002
        """_cache_get should move accessed entry to end (most recent)."""
        import ot.executor.tool_loader as loader
        from ot.executor.tool_loader import LoadedTools

        mock_tools = LoadedTools(functions={}, packs={}, worker_tools=[])

        # Add two entries
        path1 = Path("/test/lru/1")
        path2 = Path("/test/lru/2")
        loader._cache_set(path1, (mock_tools, {"f1": 1.0}))
        loader._cache_set(path2, (mock_tools, {"f2": 2.0}))

        # path1 was added first, so it's at the front
        first_key = next(iter(loader._module_cache))
        assert first_key == path1

        # Access path1 - should move to end
        loader._cache_get(path1)

        # Now path2 should be at front
        first_key = next(iter(loader._module_cache))
        assert first_key == path2
