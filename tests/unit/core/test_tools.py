"""Tests for ot.tools inter-tool calling API."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestCallTool:
    """Tests for call_tool function."""

    def test_call_tool_requires_dot_notation(self) -> None:
        """Should raise ValueError for names without pack prefix."""
        from ot.tools import call_tool

        with pytest.raises(ValueError, match="must include pack prefix"):
            call_tool("search", query="test")

    def test_call_tool_unknown_pack(self) -> None:
        """Should raise KeyError for unknown pack name."""
        from ot.tools import call_tool

        with pytest.raises(KeyError, match="Pack .* not found"):
            call_tool("nonexistent_pack.function", arg="value")

    def test_call_tool_unknown_function(self) -> None:
        """Should raise KeyError for unknown function in valid pack."""
        from ot.tools import call_tool

        # 'ot' pack is always registered, so use it
        with pytest.raises(KeyError, match="Function .* not found"):
            call_tool("ot.nonexistent_function", arg="value")

    def test_call_tool_valid(self) -> None:
        """Should successfully call a valid tool."""
        from ot.tools import call_tool

        # Call ot.help() which should always be available
        result = call_tool("ot.help")
        assert result is not None
        assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.core
class TestGetPack:
    """Tests for get_pack function."""

    def test_get_pack_unknown(self) -> None:
        """Should raise KeyError for unknown pack name."""
        from ot.tools import get_pack

        with pytest.raises(KeyError, match="Pack .* not found"):
            get_pack("nonexistent_pack")

    def test_get_pack_valid(self) -> None:
        """Should return pack proxy for valid pack."""
        from ot.tools import get_pack

        # 'ot' pack is always registered
        ot_pack = get_pack("ot")
        assert ot_pack is not None
        assert hasattr(ot_pack, "help")

    def test_get_pack_allows_function_calls(self) -> None:
        """Should return pack that allows function calls."""
        from ot.tools import get_pack

        ot_pack = get_pack("ot")
        result = ot_pack.help()
        assert result is not None
        assert isinstance(result, str)
