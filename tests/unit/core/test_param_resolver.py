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

    def test_collision_exact_and_prefix_raises(self):
        """D4: exact + prefix both targeting one param raises, not silent overwrite."""
        with pytest.raises(ValueError, match="query"):
            resolve_kwargs({"query": "real", "q": "typo"}, ["query", "count"])

    def test_collision_is_order_independent(self):
        """D4: the ambiguity is refused regardless of provided-key order."""
        with pytest.raises(ValueError):
            resolve_kwargs({"c": "A", "count": "B"}, ["count"])
        with pytest.raises(ValueError):
            resolve_kwargs({"count": "B", "c": "A"}, ["count"])

    def test_single_key_multi_prefix_first_wins_unchanged(self):
        """D4: a single provided key ambiguously prefixing many params is unchanged."""
        result = resolve_kwargs({"q": "test"}, ["query_info", "query", "quality"])
        assert result == {"query_info": "test"}

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
        result = resolve_kwargs(
            {"q": "test", "c": 5, "p": 1}, ["query", "count", "page"]
        )
        assert result == {"query": "test", "count": 5, "page": 1}

    def test_exact_match_wins_over_prefix(self):
        """When exact match exists, use it even if prefix matches others."""
        # 'c' could match 'count' or 'cache', but 'count' matches exactly
        result = resolve_kwargs({"count": 5}, ["cache", "count"])
        assert result == {"count": 5}

    def test_multi_prefix_skips_target_claimed_by_another_key(self):
        """Multiple prefix matches must not fabricate ambiguity with another
        provided key: 'p' prefix-matches both 'path' and 'pattern', but 'path'
        is itself an exact key in kwargs, so 'p' should resolve to 'pattern'."""
        result = resolve_kwargs({"p": "x", "path": "y"}, ["path", "pattern"])
        assert result == {"pattern": "x", "path": "y"}

    def test_multi_prefix_ambiguity_still_raises_when_targets_are_taken(self):
        """D4 must still hold: query='x', q='y' both target 'query' (the only
        candidate), so this remains a genuine ambiguity."""
        with pytest.raises(ValueError, match="query"):
            resolve_kwargs({"query": "x", "q": "y"}, ["query", "count"])

    def test_preserves_value_types(self):
        """Value types are preserved during resolution."""
        result = resolve_kwargs(
            {"q": "string", "c": 42, "f": 3.14, "b": True, "n": None, "l": [1, 2]},
            ["query", "count", "factor", "bool_val", "nullable", "list_val"],
        )
        assert result == {
            "query": "string",
            "count": 42,
            "factor": 3.14,
            "bool_val": True,
            "nullable": None,
            "list_val": [1, 2],
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
            },
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
        import ot.executor.param_resolver
        import ot.registry

        ot.registry._registry = None
        ot.executor.param_resolver.get_tool_param_names.cache_clear()
        yield

    def test_ottools_registered_in_registry(self):
        """ot pack tools are registered in the global registry."""
        from ot.registry import get_registry

        registry = get_registry()

        # Check key ot tools are registered
        assert registry.get_tool("ot.tools") is not None
        assert registry.get_tool("ot.packs") is not None
        assert registry.get_tool("ot.help") is not None
        assert registry.get_tool("ot.aliases") is not None
        assert registry.get_tool("ot.snippets") is not None

    def test_ottools_have_correct_args(self):
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

    def test_ottools_param_shorthand_resolves(self):
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


@pytest.mark.unit
@pytest.mark.core
class TestMcpParamCacheBounds:
    """Tests for MCP param cache size limits."""

    def test_mcp_param_cache_has_maxsize(self):
        """MCP param cache should have a defined maxsize constant."""
        import ot.executor.param_resolver as resolver

        assert hasattr(resolver, "_MCP_PARAM_CACHE_MAXSIZE")
        assert resolver._MCP_PARAM_CACHE_MAXSIZE > 0

    def test_mcp_param_cache_is_ordered_dict(self):
        """MCP param cache should use OrderedDict for LRU semantics."""
        from collections import OrderedDict

        import ot.executor.param_resolver as resolver

        assert isinstance(resolver._mcp_param_cache, OrderedDict)
