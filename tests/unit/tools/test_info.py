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
    from ot_tools.internal import tools

    result = tools(pattern="search")

    # Each pack's search function should have its own signature
    assert "brave.search" in result
    assert "ground.search" in result
    assert "page.search" in result

    # ground.search should mention Gemini/grounding (non-proxied function)
    assert "Gemini" in result or "grounding" in result

    # page.search should mention HTML/accessibility (non-proxied function)
    assert "accessibility" in result or "HTML" in result


@pytest.mark.unit
@pytest.mark.serve
def test_tools_compact_mode_reduces_output_size() -> None:
    """Verify compact mode produces smaller output."""
    from ot_tools.internal import tools

    full_output = tools()
    compact_output = tools(compact=True)

    # Compact should be significantly smaller
    assert len(compact_output) < len(full_output) * 0.5

    # Compact should not have signature or source fields (JSON format)
    assert '"signature"' not in compact_output
    assert '"source"' not in compact_output

    # But should still have name and description (JSON format)
    assert '"name"' in compact_output
    assert '"description"' in compact_output


@pytest.mark.unit
@pytest.mark.serve
def test_tools_pack_filter() -> None:
    """Verify pack filter works correctly."""
    import json

    from ot_tools.internal import tools

    result = tools(pack="ot")
    tools_list = json.loads(result)
    tool_names = [t["name"] for t in tools_list]

    # Should only have ot pack tools
    assert any(name == "ot.tools" for name in tool_names)
    assert any(name == "ot.health" for name in tool_names)

    # Should NOT have other pack tools (check actual tool names, not examples)
    assert not any(name.startswith("brave.") for name in tool_names)
    assert not any(name.startswith("page.") for name in tool_names)


@pytest.mark.unit
@pytest.mark.serve
def test_health_counts_all_tools() -> None:
    """Verify ot.health() counts all tools including duplicates."""
    import json

    from ot_tools.internal import health

    result = health()

    # Should be valid JSON with registry status
    data = json.loads(result)
    assert "registry" in data
    assert "tool_count" in data["registry"]

    # The count should include all tools across packs
    # (not deduplicated by bare name)
    # We have at least 5 "search" functions in different packs
    # so total should be > 30 (rough estimate)
    count = data["registry"]["tool_count"]
    assert count >= 30, f"Expected at least 30 tools, got {count}"


@pytest.mark.unit
@pytest.mark.serve
def test_config_returns_configuration() -> None:
    """Verify ot.config() returns configuration information."""
    import json

    from ot_tools.internal import config

    result = config()

    # Should be valid JSON with expected sections
    data = json.loads(result)
    assert "aliases" in data
    assert "snippets" in data
    assert "servers" in data


# ============================================================================
# Introspection Tool Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_help_with_valid_tool() -> None:
    """Verify ot.help() returns documentation for valid tool."""
    from ot_tools.internal import help

    result = help(tool="ot.tools")

    # Should have formatted sections
    assert "## ot.tools" in result
    assert "**Signature**:" in result
    assert "**Args**:" in result or "**Returns**:" in result


@pytest.mark.unit
@pytest.mark.serve
def test_help_with_invalid_format() -> None:
    """Verify ot.help() returns error for invalid tool format."""
    from ot_tools.internal import help

    result = help(tool="nopack")

    assert "Error:" in result
    assert "pack.function" in result


@pytest.mark.unit
@pytest.mark.serve
def test_help_with_unknown_pack() -> None:
    """Verify ot.help() returns error for unknown pack."""
    from ot_tools.internal import help

    result = help(tool="nonexistent.function")

    assert "Error:" in result
    assert "Pack" in result
    assert "not found" in result


@pytest.mark.unit
@pytest.mark.serve
def test_help_with_unknown_function() -> None:
    """Verify ot.help() returns error for unknown function."""
    from ot_tools.internal import help

    result = help(tool="ot.nonexistent")

    assert "Error:" in result
    assert "not in ot" in result


@pytest.mark.unit
@pytest.mark.serve
def test_alias_with_valid_alias(override_config: Any) -> None:
    """Verify ot.alias() returns mapping for valid alias."""
    from ot_tools.internal import alias

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = alias(name="ws")
        assert "ws -> brave.web_search" in result


@pytest.mark.unit
@pytest.mark.serve
def test_alias_with_star(override_config: Any) -> None:
    """Verify ot.alias(name='*') lists all aliases."""
    from ot_tools.internal import alias

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = alias(name="*")
        assert "ws -> brave.web_search" in result
        assert "gs -> ground.search" in result


@pytest.mark.unit
@pytest.mark.serve
def test_alias_not_found(override_config: Any) -> None:
    """Verify ot.alias() returns error for unknown alias."""
    from ot_tools.internal import alias

    with override_config(OneToolConfig(alias={"ws": "brave.web_search"})):
        result = alias(name="unknown")
        assert "Error:" in result
        assert "not found" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_with_valid_snippet(override_config: Any) -> None:
    """Verify ot.snippet() returns definition for valid snippet."""
    from ot.config import SnippetDef
    from ot_tools.internal import snippet

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
        result = snippet(name="test_snip")
        assert "name: test_snip" in result
        assert "description: Test snippet" in result
        assert "body:" in result
        assert "demo.call()" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_with_star(override_config: Any) -> None:
    """Verify ot.snippet(name='*') lists all snippets."""
    from ot.config import SnippetDef
    from ot_tools.internal import snippet

    with override_config(
        OneToolConfig(
            snippets={
                "snip1": SnippetDef(description="First snippet", body="one()"),
                "snip2": SnippetDef(description="Second snippet", body="two()"),
            }
        )
    ):
        result = snippet(name="*")
        assert "snip1: First snippet" in result
        assert "snip2: Second snippet" in result


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_not_found(override_config: Any) -> None:
    """Verify ot.snippet() returns error for unknown snippet."""
    from ot.config import SnippetDef
    from ot_tools.internal import snippet

    with override_config(OneToolConfig(snippets={"known": SnippetDef(body="demo()")})):
        result = snippet(name="unknown")
        assert "Error:" in result
        assert "not found" in result


# ============================================================================
# Proxy Tool Help Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_help_with_proxy_tool(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.help() returns documentation for proxy tools."""
    from unittest.mock import patch

    from ot_tools.internal import help

    # Create mock proxy tool
    mock_tool = ProxyToolInfo(
        server="github",
        name="create_issue",
        description="Create a new issue in a repository.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue body"},
            },
            "required": ["repo", "title"],
        },
    )

    mock_proxy_manager.list_tools.return_value = [mock_tool]
    mock_proxy_manager.servers = ["github"]

    with patch("ot_tools.internal.get_proxy_manager", return_value=mock_proxy_manager):
        result = help(tool="github.create_issue")

    # Should have proxy tool help format
    assert "## github.create_issue" in result
    assert "Create a new issue" in result
    assert "**Parameters**:" in result
    assert "repo:" in result
    assert "(required)" in result
    assert "**Source**: proxy:github" in result


@pytest.mark.unit
@pytest.mark.serve
def test_help_proxy_tool_not_found(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.help() returns error when proxy tool not found."""
    from unittest.mock import patch

    from ot_tools.internal import help

    mock_tool = ProxyToolInfo(
        server="github",
        name="list_repos",
        description="List repositories",
        input_schema={},
    )

    mock_proxy_manager.list_tools.return_value = [mock_tool]
    mock_proxy_manager.servers = ["github"]

    with patch("ot_tools.internal.get_proxy_manager", return_value=mock_proxy_manager):
        result = help(tool="github.nonexistent")

    assert "Error:" in result
    assert "nonexistent" in result
    assert "list_repos" in result  # Should list available tools


# ============================================================================
# Instructions Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_with_config_override(override_prompts: Any) -> None:
    """Verify ot.instructions() returns config override when present."""
    from ot_tools.internal import instructions

    with override_prompts(
        PromptsConfig(
            instructions="Main instructions",
            packs={
                "brave": "Custom brave instructions from config.\nUse brave.search() for web search."
            },
        )
    ):
        result = instructions(pack="brave")
        assert "Custom brave instructions" in result
        assert "brave.search()" in result


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_fallback_local(override_prompts: Any) -> None:
    """Verify ot.instructions() falls back to docstrings for local pack."""
    from ot_tools.internal import instructions

    with override_prompts(
        PromptsConfig(
            instructions="Main instructions",
            packs={},  # No override for ot pack
        )
    ):
        result = instructions(pack="ot")
        # Should generate from docstrings
        assert "# ot pack" in result
        assert "ot.tools" in result
        assert "ot.help" in result


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_fallback_proxy(
    override_prompts: Any, mock_proxy_manager: MagicMock
) -> None:
    """Verify ot.instructions() falls back to tool list for proxy pack."""
    from unittest.mock import patch

    from ot_tools.internal import instructions

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

    with override_prompts(
        PromptsConfig(
            instructions="Main instructions",
            packs={},  # No override
        )
    ):
        with patch(
            "ot_tools.internal.get_proxy_manager", return_value=mock_proxy_manager
        ):
            result = instructions(pack="github")

        # Should generate from proxy tool list
        assert "# github pack (proxy)" in result
        assert "github.create_issue" in result
        assert "github.list_repos" in result


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_unknown_pack(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.instructions() returns error for unknown pack."""
    from unittest.mock import patch

    from ot_tools.internal import instructions

    mock_proxy_manager.servers = []

    with patch("ot_tools.internal.get_proxy_manager", return_value=mock_proxy_manager):
        result = instructions(pack="nonexistent")

    assert "Error:" in result
    assert "Pack" in result
    assert "not found" in result
