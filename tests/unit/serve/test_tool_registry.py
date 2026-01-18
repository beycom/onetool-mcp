"""Unit tests for tool registry and namespace handling.

Tests that the registry correctly handles:
- Loading tools with namespace support
- No name collisions between namespaces
- Namespace proxy access (dot notation)
- Function lookup by full namespaced name
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_registry_has_namespaces() -> None:
    """Verify registry loads tools organized by namespace."""
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    # Should have multiple namespaces
    assert len(registry.namespaces) >= 5

    # Check expected namespaces exist
    assert "brave" in registry.namespaces
    assert "ot" in registry.namespaces
    assert "page" in registry.namespaces
    assert "ground" in registry.namespaces


@pytest.mark.unit
@pytest.mark.serve
def test_registry_namespaces_have_correct_functions() -> None:
    """Verify each namespace has its own functions."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerNamespaceProxy

    registry = load_tool_registry()

    # brave namespace should have brave-specific functions
    brave_ns = registry.namespaces["brave"]
    if isinstance(brave_ns, WorkerNamespaceProxy):
        assert "search" in brave_ns.functions
        brave_search = brave_ns.search
    else:
        assert "search" in brave_ns
        brave_search = brave_ns["search"]

    # ground namespace should have ground-specific functions
    ground_ns = registry.namespaces["ground"]
    if isinstance(ground_ns, WorkerNamespaceProxy):
        assert "search" in ground_ns.functions
        ground_search = ground_ns.search
    else:
        assert "search" in ground_ns
        ground_search = ground_ns["search"]
        # Check docstrings for non-proxy functions
        assert "Gemini" in (ground_search.__doc__ or "") or "grounding" in (
            ground_search.__doc__ or ""
        )

    # These should be different functions/proxies
    assert brave_search is not ground_search


@pytest.mark.unit
@pytest.mark.serve
def test_registry_counts_all_functions() -> None:
    """Verify we can count all functions across namespaces without collision."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerNamespaceProxy

    registry = load_tool_registry()

    # Count functions per namespace - handle both dict and WorkerNamespaceProxy
    total = 0
    for ns in registry.namespaces.values():
        if isinstance(ns, WorkerNamespaceProxy):
            total += len(ns.functions)
        else:
            total += len(ns)

    # Should have many tools (including duplicates like 'search' in multiple namespaces)
    assert total >= 30


@pytest.mark.unit
@pytest.mark.serve
def test_build_execution_namespace_has_namespace_proxies() -> None:
    """Verify execution namespace has namespace proxy objects."""
    from ot.executor.namespace_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()
    namespace = build_execution_namespace(registry)

    # Should have namespace proxies
    assert "brave" in namespace
    assert "ground" in namespace
    assert "ot" in namespace

    # Proxies should allow attribute access
    assert hasattr(namespace["brave"], "search")
    assert hasattr(namespace["ground"], "search")
    assert hasattr(namespace["ot"], "tools")


@pytest.mark.unit
@pytest.mark.serve
def test_namespace_proxy_returns_correct_function() -> None:
    """Verify namespace proxy returns the correct function for each namespace."""
    from ot.executor.namespace_proxy import build_execution_namespace
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()
    namespace = build_execution_namespace(registry)

    # Get search from different namespaces
    brave_search = namespace["brave"].search
    ground_search = namespace["ground"].search

    # They should be different functions/proxies
    assert brave_search is not ground_search

    # For non-worker-proxy namespaces, check docstrings
    # For worker-proxy namespaces, just verify they're callable
    assert callable(brave_search)
    assert callable(ground_search)


@pytest.mark.unit
@pytest.mark.serve
def test_namespace_proxy_raises_on_unknown_function() -> None:
    """Verify namespace proxy raises AttributeError for unknown functions."""
    from ot.executor.namespace_proxy import build_execution_namespace
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
    """Verify we can look up functions by full namespaced name from namespaces dict."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.executor.worker_proxy import WorkerNamespaceProxy

    registry = load_tool_registry()

    # Look up by full name using namespaces
    def get_function(full_name: str):
        if "." not in full_name:
            return None
        ns_name, func_name = full_name.split(".", 1)
        if ns_name not in registry.namespaces:
            return None
        ns = registry.namespaces[ns_name]
        if isinstance(ns, WorkerNamespaceProxy):
            if func_name in ns.functions:
                return getattr(ns, func_name)
            return None
        return ns.get(func_name)

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
def test_registry_functions_use_namespaced_keys() -> None:
    """Verify registry.functions uses full namespaced names as keys."""
    from ot.executor.tool_loader import load_tool_registry

    registry = load_tool_registry()

    # Functions dict should have keys like "brave.search", not "search"
    assert "brave.search" in registry.functions
    assert "ground.search" in registry.functions
    assert "page.search" in registry.functions
    assert "ot.tools" in registry.functions

    # Each namespaced key should point to the correct function
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

    # Should NOT have bare names for namespaced functions
    # (only tools without a namespace would have bare names)
    assert "search" not in registry.functions
