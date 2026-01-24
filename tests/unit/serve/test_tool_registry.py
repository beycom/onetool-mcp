"""Unit tests for tool registry and pack handling.

Tests that the registry correctly handles:
- Loading tools with pack support
- No name collisions between packs
- Pack proxy access (dot notation)
- Function lookup by full pack.function name
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_registry_has_packs() -> None:
    """Verify registry loads tools organized by pack."""
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    # Should have multiple packs
    assert len(registry.packs) >= 5

    # Check expected packs exist
    assert "brave" in registry.packs
    assert "ot" in registry.packs
    assert "page" in registry.packs
    assert "ground" in registry.packs


@pytest.mark.unit
@pytest.mark.serve
def test_registry_packs_have_correct_functions() -> None:
    """Verify each pack has its own functions."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerPackProxy

    registry = load_tool_registry()

    # brave pack should have brave-specific functions
    brave_pack = registry.packs["brave"]
    if isinstance(brave_pack, WorkerPackProxy):
        assert "search" in brave_pack.functions
        brave_search = brave_pack.search
    else:
        assert "search" in brave_pack
        brave_search = brave_pack["search"]

    # ground pack should have ground-specific functions
    ground_pack = registry.packs["ground"]
    if isinstance(ground_pack, WorkerPackProxy):
        assert "search" in ground_pack.functions
        ground_search = ground_pack.search
    else:
        assert "search" in ground_pack
        ground_search = ground_pack["search"]
        # Check docstrings for non-proxy functions
        assert "Gemini" in (ground_search.__doc__ or "") or "grounding" in (
            ground_search.__doc__ or ""
        )

    # These should be different functions/proxies
    assert brave_search is not ground_search


@pytest.mark.unit
@pytest.mark.serve
def test_registry_counts_all_functions() -> None:
    """Verify we can count all functions across packs without collision."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerPackProxy

    registry = load_tool_registry()

    # Count functions per pack - handle both dict and WorkerPackProxy
    total = 0
    for pack in registry.packs.values():
        if isinstance(pack, WorkerPackProxy):
            total += len(pack.functions)
        else:
            total += len(pack)

    # Should have many tools (including duplicates like 'search' in multiple packs)
    assert total >= 30


@pytest.mark.unit
@pytest.mark.serve
def test_build_execution_namespace_has_pack_proxies() -> None:
    """Verify execution namespace has pack proxy objects."""
    from ot.executor.pack_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()
    namespace = build_execution_namespace(registry)

    # Should have pack proxies
    assert "brave" in namespace
    assert "ground" in namespace
    assert "ot" in namespace

    # Proxies should allow attribute access
    assert hasattr(namespace["brave"], "search")
    assert hasattr(namespace["ground"], "search")
    assert hasattr(namespace["ot"], "tools")


@pytest.mark.unit
@pytest.mark.serve
def test_pack_proxy_returns_correct_function() -> None:
    """Verify pack proxy returns the correct function for each pack."""
    from ot.executor.pack_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()
    namespace = build_execution_namespace(registry)

    # Get search from different packs
    brave_search = namespace["brave"].search
    ground_search = namespace["ground"].search

    # They should be different functions/proxies
    assert brave_search is not ground_search

    # For non-worker-proxy packs, check docstrings
    # For worker-proxy packs, just verify they're callable
    assert callable(brave_search)
    assert callable(ground_search)


@pytest.mark.unit
@pytest.mark.serve
def test_pack_proxy_raises_on_unknown_function() -> None:
    """Verify pack proxy raises AttributeError for unknown functions."""
    from ot.executor.pack_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()
    namespace = build_execution_namespace(registry)

    # Accessing non-existent function should raise
    with pytest.raises(AttributeError) as exc_info:
        _ = namespace["brave"].nonexistent_function

    assert "nonexistent_function" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.serve
def test_registry_functions_by_full_name() -> None:
    """Verify we can look up functions by full pack.function name from packs dict."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerPackProxy

    registry = load_tool_registry()

    # Look up by full name using packs
    def get_function(full_name: str):
        if "." not in full_name:
            return None
        pack_name, func_name = full_name.split(".", 1)
        if pack_name not in registry.packs:
            return None
        pack = registry.packs[pack_name]
        if isinstance(pack, WorkerPackProxy):
            if func_name in pack.functions:
                return getattr(pack, func_name)
            return None
        return pack.get(func_name)

    # Should find each search function
    brave_search = get_function("brave.search")
    ground_search = get_function("ground.search")
    page_search = get_function("page.search")

    assert brave_search is not None
    assert ground_search is not None
    assert page_search is not None

    # All should be different functions
    assert brave_search is not ground_search
    assert brave_search is not page_search
    assert ground_search is not page_search


@pytest.mark.unit
@pytest.mark.serve
def test_load_tool_functions_returns_dict() -> None:
    """Verify load_tool_functions returns a dictionary."""
    from ot.executor.tool_loader import load_tool_functions

    functions = load_tool_functions()

    assert isinstance(functions, dict)
    assert len(functions) > 0


@pytest.mark.unit
@pytest.mark.serve
def test_registry_caching() -> None:
    """Verify registry caching works (same object returned)."""
    from ot.executor.tool_loader import load_tool_registry

    registry1 = load_tool_registry()
    registry2 = load_tool_registry()

    # Should return same cached object
    assert registry1 is registry2


@pytest.mark.unit
@pytest.mark.serve
def test_registry_functions_use_qualified_keys() -> None:
    """Verify registry.functions uses full pack.function names as keys."""
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    # Functions dict should have keys like "brave.search", not "search"
    assert "brave.search" in registry.functions
    assert "ground.search" in registry.functions
    assert "page.search" in registry.functions
    assert "ot.tools" in registry.functions

    # Each qualified key should point to the correct function
    brave_search = registry.functions["brave.search"]
    ground_search = registry.functions["ground.search"]

    # They should be different functions
    assert brave_search is not ground_search


@pytest.mark.unit
@pytest.mark.serve
def test_registry_no_bare_name_collisions() -> None:
    """Verify that bare names like 'search' are not in functions dict."""
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    # Should NOT have bare names for functions in packs
    # (only tools without a pack would have bare names)
    assert "search" not in registry.functions
