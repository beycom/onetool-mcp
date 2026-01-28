"""Tests for parameter prefix matching."""

import pytest

from ot.executor.param_resolver import get_param_names_from_schema, resolve_kwargs


@pytest.mark.unit
@pytest.mark.core
class TestResolveKwargs:
    """Tests for resolve_kwargs function."""

    def test_exact_match_passthrough(self):
        """Exact parameter names pass through unchanged."""
        result = resolve_kwargs({"query": "test"}, ["query", "count"])
        assert result == {"query": "test"}

    def test_single_prefix_match(self):
        """Single prefix match resolves to full name."""
        result = resolve_kwargs({"q": "test"}, ["query", "count"])
        assert result == {"query": "test"}

    def test_multiple_prefix_matches_first_wins(self):
        """Multiple prefix matches select first in signature order."""
        result = resolve_kwargs({"q": "test"}, ["query_info", "query", "quality"])
        assert result == {"query_info": "test"}

    def test_partial_prefix_match(self):
        """Partial prefix matches single param."""
        result = resolve_kwargs({"qual": "test"}, ["query_info", "query", "quality"])
        assert result == {"quality": "test"}

    def test_no_match_passthrough(self):
        """Unmatched params pass through for function to error."""
        result = resolve_kwargs({"xyz": "test"}, ["query", "count"])
        assert result == {"xyz": "test"}

    def test_empty_kwargs(self):
        """Empty kwargs returns empty dict."""
        result = resolve_kwargs({}, ["query", "count"])
        assert result == {}

    def test_empty_param_names(self):
        """Empty param names returns kwargs unchanged."""
        result = resolve_kwargs({"q": "test"}, [])
        assert result == {"q": "test"}

    def test_mixed_exact_and_prefix(self):
        """Mix of exact and prefix matches work together."""
        result = resolve_kwargs({"query": "test", "c": 5}, ["query", "count"])
        assert result == {"query": "test", "count": 5}

    def test_multiple_params_resolved(self):
        """Multiple abbreviated params all get resolved."""
        result = resolve_kwargs({"q": "test", "c": 5, "p": 1}, ["query", "count", "page"])
        assert result == {"query": "test", "count": 5, "page": 1}

    def test_exact_match_wins_over_prefix(self):
        """When exact match exists, use it even if prefix matches others."""
        # 'c' could match 'count' or 'cache', but 'count' matches exactly
        result = resolve_kwargs({"count": 5}, ["cache", "count"])
        assert result == {"count": 5}

    def test_preserves_value_types(self):
        """Value types are preserved during resolution."""
        result = resolve_kwargs(
            {"q": "string", "c": 42, "f": 3.14, "b": True, "n": None, "l": [1, 2]},
            ["query", "count", "factor", "bool_val", "nullable", "list_val"]
        )
        assert result == {
            "query": "string",
            "count": 42,
            "factor": 3.14,
            "bool_val": True,
            "nullable": None,
            "list_val": [1, 2]
        }


@pytest.mark.unit
@pytest.mark.core
class TestGetParamNamesFromSchema:
    """Tests for get_param_names_from_schema function."""

    def test_extracts_property_names(self):
        """Extracts parameter names from schema properties."""
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "count": {"type": "integer"},
            }
        }
        result = get_param_names_from_schema(schema)
        assert result == ["query", "count"]

    def test_empty_schema(self):
        """Empty schema returns empty list."""
        result = get_param_names_from_schema({})
        assert result == []

    def test_no_properties(self):
        """Schema without properties returns empty list."""
        schema = {"type": "object"}
        result = get_param_names_from_schema(schema)
        assert result == []

    def test_properties_not_dict(self):
        """Non-dict properties returns empty list."""
        schema = {"properties": "invalid"}
        result = get_param_names_from_schema(schema)
        assert result == []


@pytest.mark.unit
@pytest.mark.core
class TestOtToolRegistration:
    """Tests for ot pack tool registration in the registry."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear registry and param resolver caches before each test."""
        import ot.registry
        import ot.executor.param_resolver

        ot.registry._registry = None
        ot.executor.param_resolver.get_tool_param_names.cache_clear()
        yield

    def test_ot_tools_registered_in_registry(self):
        """ot pack tools are registered in the global registry."""
        from ot.registry import get_registry

        registry = get_registry()

        # Check key ot tools are registered
        assert registry.get_tool("ot.tools") is not None
        assert registry.get_tool("ot.packs") is not None
        assert registry.get_tool("ot.help") is not None
        assert registry.get_tool("ot.aliases") is not None
        assert registry.get_tool("ot.snippets") is not None

    def test_ot_tools_have_correct_args(self):
        """ot tools have their parameters extracted correctly."""
        from ot.registry import get_registry

        registry = get_registry()
        tool = registry.get_tool("ot.tools")

        assert tool is not None
        arg_names = [arg.name for arg in tool.args]
        assert "pattern" in arg_names
        assert "info" in arg_names

    def test_get_tool_param_names_returns_ot_params(self):
        """get_tool_param_names returns params for ot tools."""
        from ot.executor.param_resolver import get_tool_param_names

        param_names = get_tool_param_names("ot.tools")
        assert "pattern" in param_names
        assert "info" in param_names

    def test_ot_tools_param_shorthand_resolves(self):
        """Parameter shorthand works for ot tools."""
        from ot.executor.param_resolver import get_tool_param_names, resolve_kwargs

        param_names = get_tool_param_names("ot.tools")
        resolved = resolve_kwargs({"p": "fire"}, list(param_names))

        assert resolved == {"pattern": "fire"}

    def test_ot_help_param_shorthand_resolves(self):
        """Parameter shorthand works for ot.help."""
        from ot.executor.param_resolver import get_tool_param_names, resolve_kwargs

        param_names = get_tool_param_names("ot.help")
        resolved = resolve_kwargs({"q": "github"}, list(param_names))

        assert resolved == {"query": "github"}
