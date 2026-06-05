"""Tests for mutable runtime metadata."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_set_meta_partial_updates_and_empty_strings() -> None:
    """Runtime metadata partial updates preserve and clear expected fields."""
    from ot.runtime_meta import set_runtime_meta

    first = set_runtime_meta(name="Planning", description="Scope Admin metadata")
    second = set_runtime_meta(name="Implementation")
    third = set_runtime_meta(name="", description="")

    assert first["name"] == "Planning"
    assert first["description"] == "Scope Admin metadata"
    assert second["name"] == "Implementation"
    assert second["description"] == "Scope Admin metadata"
    assert third["name"] == ""
    assert third["description"] == ""
    assert third["identity"].startswith("mcp-")
    assert "cwd" in third

