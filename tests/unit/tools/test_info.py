"""Unit tests for internal tool functions.

Tests that ot.tools() correctly handles pack.function names,
especially when multiple packs have functions with the same name.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from ot.config import OneToolConfig
from ot.prompts import PromptsConfig
from ot.proxy import ProxyToolInfo

if TYPE_CHECKING:
    from collections.abc import Generator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def override_config() -> Generator[Any, None, None]:
    """Fixture to temporarily override OneToolConfig."""
    import ot.config.loader

    @contextmanager
    def _override(config: OneToolConfig) -> Generator[None, None, None]:
        old_config = ot.config.loader._config
        try:
            ot.config.loader._config = config
            yield
        finally:
            ot.config.loader._config = old_config

    yield _override


@pytest.fixture
def override_prompts() -> Generator[Any, None, None]:
    """Fixture to temporarily override PromptsConfig."""
    import ot.prompts

    @contextmanager
    def _override(prompts: PromptsConfig) -> Generator[None, None, None]:
        old_prompts = ot.prompts._prompts
        try:
            ot.prompts._prompts = prompts
            yield
        finally:
            ot.prompts._prompts = old_prompts

    yield _override


@pytest.fixture
def mock_proxy_manager() -> MagicMock:
    """Create a mock proxy manager."""
    mock = MagicMock()
    mock.servers = []
    mock.list_tools.return_value = []
    return mock


# ============================================================================
# Tool Discovery Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_tools_returns_correct_signatures_for_same_named_functions() -> None:
    """Verify ot.tools() returns correct signatures for functions with same name."""
    from ot.meta import tools

    result = tools(pattern="search")

    # Result is now a list of dicts
    tool_names = [t["name"] for t in result]
    tool_descs = " ".join(t.get("description", "") for t in result)

    # Each pack's search function should have its own signature
    assert "brave.search" in tool_names
    assert "ground.search" in tool_names
    assert "page.search" in tool_names

    # ground.search should mention Gemini/grounding (non-proxied function)
    assert "Gemini" in tool_descs or "grounding" in tool_descs

    # page.search should mention HTML/accessibility (non-proxied function)
    assert "accessibility" in tool_descs or "HTML" in tool_descs


@pytest.mark.unit
@pytest.mark.serve
def test_tools_compact_mode_reduces_output_size() -> None:
    """Verify compact mode produces smaller output."""
    from ot.meta import tools

    full_output = tools()
    compact_output = tools(compact=True)

    # Both are lists of dicts
    assert isinstance(full_output, list)
    assert isinstance(compact_output, list)

    # Compact should not have signature or source fields
    for tool in compact_output:
        assert "signature" not in tool
        assert "source" not in tool

    # But should still have name and description
    for tool in compact_output:
        assert "name" in tool
        assert "description" in tool


@pytest.mark.unit
@pytest.mark.serve
def test_tools_pack_filter() -> None:
    """Verify pack filter works correctly."""
    from ot.meta import tools

    result = tools(pack="ot")
    # Result is now a list of dicts directly
    tool_names = [t["name"] for t in result]

    # Should only have ot pack tools
    assert any(name == "ot.tools" for name in tool_names)
    assert any(name == "ot.packs" for name in tool_names)
    assert any(name == "ot.health" for name in tool_names)

    # Should NOT have other pack tools (check actual tool names, not examples)
    assert not any(name.startswith("brave.") for name in tool_names)
    assert not any(name.startswith("page.") for name in tool_names)


@pytest.mark.unit
@pytest.mark.serve
def test_tools_name_exact_match() -> None:
    """Verify tools(name=...) returns a single tool by exact name."""
    from ot.meta import tools

    result = tools(name="ot.tools")

    # Should return a single dict, not a list
    assert isinstance(result, dict)
    assert result["name"] == "ot.tools"
    assert "signature" in result
    assert "source" in result


@pytest.mark.unit
@pytest.mark.serve
def test_tools_name_not_found() -> None:
    """Verify tools(name=...) returns error for unknown tool."""
    from ot.meta import tools

    result = tools(name="nonexistent.tool")

    assert isinstance(result, str)
    assert "Error:" in result
    assert "not found" in result


@pytest.mark.unit
@pytest.mark.serve
def test_tools_name_invalid_format() -> None:
    """Verify tools(name=...) returns error for invalid format."""
    from ot.meta import tools

    result = tools(name="nopack")

    assert isinstance(result, str)
    assert "Error:" in result
    assert "pack.function" in result


@pytest.mark.unit
@pytest.mark.serve
def test_health_counts_all_tools() -> None:
    """Verify ot.health() counts all tools including duplicates."""
    from ot.meta import health

    result = health()

    # Result is now a dict directly
    assert "registry" in result
    assert "tool_count" in result["registry"]

    # The count should include all tools across packs
    # (not deduplicated by bare name)
    # We have at least 5 "search" functions in different packs
    # so total should be > 30 (rough estimate)
    count = result["registry"]["tool_count"]
    assert count >= 30, f"Expected at least 30 tools, got {count}"


@pytest.mark.unit
@pytest.mark.serve
def test_config_returns_configuration() -> None:
    """Verify ot.config() returns configuration information."""
    from ot.meta import config

    result = config()

    # Result is now a dict directly
    assert "aliases" in result
    assert "snippets" in result
    assert "servers" in result


# ============================================================================
# Packs Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_packs_list_all() -> None:
    """Verify ot.packs() lists all packs."""
    from ot.meta import packs

    result = packs()

    # Should return a list of pack dicts
    assert isinstance(result, list)
    assert len(result) > 0

    # Should have ot pack
    pack_names = [p["name"] for p in result]
    assert "ot" in pack_names
    assert "brave" in pack_names

    # Each pack should have name, source, tool_count
    for pack in result:
        assert "name" in pack
        assert "source" in pack
        assert "tool_count" in pack


@pytest.mark.unit
@pytest.mark.serve
def test_packs_get_by_name() -> None:
    """Verify ot.packs(name=...) returns detailed pack info."""
    from ot.meta import packs

    result = packs(name="ot")

    # Should return formatted string with pack info
    assert isinstance(result, str)
    assert "# ot pack" in result
    assert "## Tools" in result
    assert "ot.tools" in result
    assert "ot.packs" in result


@pytest.mark.unit
@pytest.mark.serve
def test_packs_pattern_filter() -> None:
    """Verify ot.packs() filters by pattern."""
    from ot.meta import packs

    result = packs(pattern="brav")

    # Should return filtered list
    assert isinstance(result, list)
    pack_names = [p["name"] for p in result]
    assert "brave" in pack_names
    assert "ot" not in pack_names


@pytest.mark.unit
@pytest.mark.serve
def test_packs_not_found() -> None:
    """Verify ot.packs() returns error for unknown pack."""
    from ot.meta import packs

    result = packs(name="nonexistent")

    assert isinstance(result, str)
    assert "Error:" in result
    assert "not found" in result


# ============================================================================
# Reload Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_reload_clears_config() -> None:
    """Verify ot.reload() clears and reloads configuration."""
    from ot.meta import reload

    result = reload()

    assert "OK" in result
    assert "reloaded" in result.lower()


# ============================================================================
# Aliases and Snippets Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_with_valid_alias(override_config: Any) -> None:
    """Verify ot.aliases() returns mapping for valid alias."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases(name="ws")
        assert "ws -> brave.web_search" in result


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_list_all(override_config: Any) -> None:
    """Verify ot.aliases() lists all aliases when called with no args."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases()
        assert "ws -> brave.web_search" in result
        assert "gs -> ground.search" in result


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_pattern_filter(override_config: Any) -> None:
    """Verify ot.aliases() filters by pattern."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases(pattern="brave")
        assert "ws -> brave.web_search" in result
        assert "gs -> ground.search" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_not_found(override_config: Any) -> None:
    """Verify ot.aliases() returns error for unknown alias."""
    from ot.meta import aliases

    with override_config(OneToolConfig(alias={"ws": "brave.web_search"})):
        result = aliases(name="unknown")
        assert "Error:" in result
        assert "not found" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_with_valid_snippet(override_config: Any) -> None:
    """Verify ot.snippets() returns definition for valid snippet."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "test_snip": SnippetDef(
                    description="Test snippet",
                    body="demo.call()",
                )
            }
        )
    ):
        result = snippets(name="test_snip")
        assert "name: test_snip" in result
        assert "description: Test snippet" in result
        assert "body:" in result
        assert "demo.call()" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_list_all(override_config: Any) -> None:
    """Verify ot.snippets() lists all snippets when called with no args."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "snip1": SnippetDef(description="First snippet", body="one()"),
                "snip2": SnippetDef(description="Second snippet", body="two()"),
            }
        )
    ):
        result = snippets()
        assert "snip1: First snippet" in result
        assert "snip2: Second snippet" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_pattern_filter(override_config: Any) -> None:
    """Verify ot.snippets() filters by pattern."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "pkg_pypi": SnippetDef(description="Check PyPI packages", body="one()"),
                "pkg_npm": SnippetDef(description="Check NPM packages", body="two()"),
                "search_web": SnippetDef(description="Search web", body="three()"),
            }
        )
    ):
        result = snippets(pattern="pkg")
        assert "pkg_pypi" in result
        assert "pkg_npm" in result
        assert "search_web" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_not_found(override_config: Any) -> None:
    """Verify ot.snippets() returns error for unknown snippet."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(OneToolConfig(snippets={"known": SnippetDef(body="demo()")})):
        result = snippets(name="unknown")
        assert "Error:" in result
        assert "not found" in result


# ============================================================================
# Proxy Pack Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_packs_with_proxy(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.packs() includes proxy packs."""
    from unittest.mock import patch

    from ot.meta import packs

    # Create mock proxy tools
    mock_tools = [
        ProxyToolInfo(
            server="github",
            name="create_issue",
            description="Create a new issue",
            input_schema={},
        ),
        ProxyToolInfo(
            server="github",
            name="list_repos",
            description="List repositories",
            input_schema={},
        ),
    ]

    mock_proxy_manager.list_tools.return_value = mock_tools
    mock_proxy_manager.servers = ["github"]

    with patch("ot.meta.get_proxy_manager", return_value=mock_proxy_manager):
        result = packs(name="github")

    # Should generate from proxy tool list
    assert isinstance(result, str)
    assert "# github pack" in result
    assert "github.create_issue" in result
    assert "github.list_repos" in result


@pytest.mark.unit
@pytest.mark.serve
def test_packs_with_config_instructions(
    override_prompts: Any, mock_proxy_manager: MagicMock
) -> None:
    """Verify ot.packs() includes configured instructions."""
    from unittest.mock import patch

    from ot.meta import packs

    mock_proxy_manager.list_tools.return_value = []
    mock_proxy_manager.servers = []

    with override_prompts(
        PromptsConfig(
            instructions="Main instructions",
            packs={
                "brave": "Custom brave instructions from config.\nUse brave.search() for web search."
            },
        )
    ):
        with patch(
            "ot.meta.get_proxy_manager", return_value=mock_proxy_manager
        ):
            result = packs(name="brave")

    # Should include configured instructions
    assert "Custom brave instructions" in result
    assert "brave.search()" in result


# ============================================================================
# Schema Helper Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_empty_schema() -> None:
    """Verify _schema_to_signature handles empty schema."""
    from ot.meta import _schema_to_signature

    result = _schema_to_signature("github.search", {})
    assert result == "github.search()"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_required_params() -> None:
    """Verify _schema_to_signature handles required parameters."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["query", "count"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(count: int, query: str)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_optional_params_with_defaults() -> None:
    """Verify _schema_to_signature handles optional params with defaults."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(query: str, limit: int = 10)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_optional_params_no_defaults() -> None:
    """Verify _schema_to_signature uses ellipsis for optional params without defaults."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["query"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(query: str, repo: str = ...)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_type_mapping() -> None:
    """Verify _schema_to_signature maps JSON Schema types to Python types."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
            "score": {"type": "number"},
            "enabled": {"type": "boolean"},
            "items": {"type": "array"},
            "data": {"type": "object"},
        },
        "required": ["text", "count", "score", "enabled", "items", "data"],
    }
    result = _schema_to_signature("test.func", schema)
    assert "text: str" in result
    assert "count: int" in result
    assert "score: float" in result
    assert "enabled: bool" in result
    assert "items: list" in result
    assert "data: dict" in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_extracts_descriptions() -> None:
    """Verify _parse_input_schema extracts argument descriptions."""
    from ot.meta import _parse_input_schema

    schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "limit": {"type": "integer", "description": "Maximum results to return"},
        },
        "required": ["query"],
    }
    result = _parse_input_schema(schema)
    assert "query: Search query string" in result
    assert "limit: Maximum results to return" in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_missing_description() -> None:
    """Verify _parse_input_schema handles missing descriptions."""
    from ot.meta import _parse_input_schema

    schema = {
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
    }
    result = _parse_input_schema(schema)
    assert "query: (no description)" in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_empty() -> None:
    """Verify _parse_input_schema handles empty schema."""
    from ot.meta import _parse_input_schema

    result = _parse_input_schema({})
    assert result == []


@pytest.mark.unit
@pytest.mark.serve
def test_build_proxy_tool_info_compact() -> None:
    """Verify _build_proxy_tool_info returns compact format."""
    from ot.meta import _build_proxy_tool_info

    result = _build_proxy_tool_info(
        "github.search",
        "Search GitHub",
        {"properties": {"query": {"type": "string"}}},
        "proxy:github",
        compact=True,
    )
    assert result == {"name": "github.search", "description": "Search GitHub"}
    assert "signature" not in result
    assert "args" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_build_proxy_tool_info_full() -> None:
    """Verify _build_proxy_tool_info returns full format with schema-derived info."""
    from ot.meta import _build_proxy_tool_info

    schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "default": 10, "description": "Max results"},
        },
        "required": ["query"],
    }
    result = _build_proxy_tool_info(
        "github.search",
        "Search GitHub repositories",
        schema,
        "proxy:github",
        compact=False,
    )
    assert result["name"] == "github.search"
    assert result["description"] == "Search GitHub repositories"
    assert result["source"] == "proxy:github"
    assert "query: str" in result["signature"]
    assert "limit: int = 10" in result["signature"]
    assert "query: Search query" in result["args"]
    assert "limit: Max results" in result["args"]


@pytest.mark.unit
@pytest.mark.serve
def test_tools_proxy_returns_enriched_info(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.tools() returns enriched info for proxy tools."""
    from unittest.mock import patch

    from ot.meta import tools

    # Create mock proxy tool with input schema
    mock_tools = [
        ProxyToolInfo(
            server="github",
            name="search",
            description="Search GitHub code",
            input_schema={
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
                "required": ["query"],
            },
        ),
    ]

    mock_proxy_manager.list_tools.return_value = mock_tools
    mock_proxy_manager.servers = ["github"]

    with patch("ot.meta.get_proxy_manager", return_value=mock_proxy_manager):
        result = tools(name="github.search")

    assert isinstance(result, dict)
    assert result["name"] == "github.search"
    assert result["source"] == "proxy:github"
    # Signature should be derived from schema, not just (...)
    assert "query: str" in result["signature"]
    assert "repo: str = ..." in result["signature"]
    # Args should be extracted from schema descriptions
    assert "query: Search query" in result["args"]
    assert "repo: Repository name" in result["args"]
