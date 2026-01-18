"""Smoke tests for tool registry."""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.core
def test_registry_imports() -> None:
    """Verify registry module imports successfully."""
    from ot.registry import ArgInfo, ToolInfo, ToolRegistry, get_registry, list_tools

    # These should all be importable
    assert ArgInfo is not None
    assert ToolInfo is not None
    assert ToolRegistry is not None
    assert get_registry is not None
    assert list_tools is not None


@pytest.mark.smoke
@pytest.mark.core
def test_registry_instantiation() -> None:
    """Verify ToolRegistry can be instantiated."""
    from pathlib import Path

    from ot.registry import ToolRegistry

    # Create a registry pointing to a non-existent directory (empty registry)
    registry = ToolRegistry(Path("/tmp/nonexistent-tools"))
    assert registry is not None
    assert len(registry.tools) == 0


@pytest.mark.smoke
@pytest.mark.core
def test_list_tools_runs() -> None:
    """Verify list_tools doesn't crash."""
    from ot.registry import list_tools

    # Should run without error (may return empty list)
    result = list_tools()
    assert isinstance(result, str)
