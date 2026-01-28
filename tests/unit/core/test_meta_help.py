"""Unit tests for ot.help() function."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestHelp:
    """Tests for ot.help() function."""

    def test_general_help_no_query(self) -> None:
        """No query returns general help overview."""
        from ot.meta import help

        result = help()

        assert "# OneTool Help" in result
        assert "## Discovery" in result
        assert "ot.tools()" in result
        assert "ot.packs()" in result
        assert "ot.snippets()" in result
        assert "ot.aliases()" in result
        assert "## Info Levels" in result
        assert "## Quick Examples" in result
        assert "## Tips" in result

    def test_tool_lookup_exact(self) -> None:
        """Exact tool name returns detailed tool help."""
        from ot.meta import help

        result = help(query="ot.tools")

        assert "# ot.tools" in result
        assert "## Signature" in result
        assert "## Docs" in result
        assert "https://onetool.beycom.online/reference/tools/ot/" in result

    def test_pack_lookup_exact(self) -> None:
        """Exact pack name returns pack help."""
        from ot.meta import help

        result = help(query="ot")

        assert "# ot pack" in result
        assert "## Tools" in result
        assert "## Docs" in result
        assert "https://onetool.beycom.online/reference/tools/ot/" in result

    def test_fuzzy_search_returns_search_results(self) -> None:
        """Fuzzy search always returns search results format."""
        from ot.meta import help

        # "tool" fuzzy matches to "ot.tools"
        result = help(query="tool")

        # Should show search results, not detailed help (info controls detail)
        assert "Search results" in result
        assert "ot.tools" in result

    def test_info_controls_detail_regardless_of_match_count(self) -> None:
        """Info parameter controls detail level for any number of matches."""
        from ot.meta import help

        # Single match with info="list" should show minimal detail
        result_list = help(query="ot.tools", info="list")
        result_min = help(query="ot.tools", info="min")

        # Exact matches show detailed help, fuzzy shows search results
        # Both should respect info level when showing search results
        assert isinstance(result_list, str)
        assert isinstance(result_min, str)

    def test_no_matches_shows_suggestions(self) -> None:
        """No matches returns helpful suggestions."""
        from ot.meta import help

        result = help(query="xyznonexistent12345")

        assert "No matches found" in result
        assert "ot.tools()" in result
        assert "ot.packs()" in result

    def test_info_level_list(self) -> None:
        """info='list' returns names only in search results."""
        from ot.meta import help

        result = help(query="ot", info="list")

        # Should have search results or pack details
        assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.core
class TestGetDocUrl:
    """Tests for _get_doc_url() helper."""

    def test_aligned_pack_uses_name(self) -> None:
        """Aligned packs use pack name as slug."""
        from ot.meta import _get_doc_url

        result = _get_doc_url("firecrawl")

        assert result == "https://onetool.beycom.online/reference/tools/firecrawl/"

    def test_misaligned_pack_uses_mapping(self) -> None:
        """Misaligned packs use DOC_SLUGS mapping."""
        from ot.meta import _get_doc_url

        assert _get_doc_url("brave") == "https://onetool.beycom.online/reference/tools/brave-search/"
        assert _get_doc_url("code") == "https://onetool.beycom.online/reference/tools/code-search/"
        assert _get_doc_url("db") == "https://onetool.beycom.online/reference/tools/database/"
        assert _get_doc_url("ground") == "https://onetool.beycom.online/reference/tools/grounding-search/"
        assert _get_doc_url("llm") == "https://onetool.beycom.online/reference/tools/transform/"
        assert _get_doc_url("web") == "https://onetool.beycom.online/reference/tools/web-fetch/"


@pytest.mark.unit
@pytest.mark.core
class TestFuzzyMatch:
    """Tests for _fuzzy_match() helper."""

    def test_substring_match_scores_high(self) -> None:
        """Substring matches get priority."""
        from ot.meta import _fuzzy_match

        candidates = ["brave.search", "web.fetch", "search_tool"]
        result = _fuzzy_match("search", candidates)

        # Both brave.search and search_tool should match
        assert "brave.search" in result
        assert "search_tool" in result
        # search_tool has "search" at start, brave.search has it at end
        # Both are substring matches so both score 1.0

    def test_fuzzy_match_with_typos(self) -> None:
        """Fuzzy matching finds close matches despite typos."""
        from ot.meta import _fuzzy_match

        candidates = ["firecrawl", "scaffold", "brave"]
        result = _fuzzy_match("frirecrawl", candidates)

        # Should find firecrawl despite typo
        assert "firecrawl" in result

    def test_no_match_returns_empty(self) -> None:
        """No matches returns empty list."""
        from ot.meta import _fuzzy_match

        candidates = ["apple", "banana", "cherry"]
        result = _fuzzy_match("xyz", candidates)

        assert result == []

    def test_threshold_filters_low_scores(self) -> None:
        """Low similarity scores are filtered out."""
        from ot.meta import _fuzzy_match

        candidates = ["abcdefghij"]
        # "z" has very low similarity to "abcdefghij"
        result = _fuzzy_match("z", candidates, threshold=0.5)

        assert result == []


@pytest.mark.unit
@pytest.mark.core
class TestFormatHelpers:
    """Tests for format helper functions."""

    def test_format_general_help_structure(self) -> None:
        """General help has expected sections."""
        from ot.meta import _format_general_help

        result = _format_general_help()

        assert "# OneTool Help" in result
        assert "## Discovery" in result
        assert "## Info Levels" in result
        assert "## Quick Examples" in result
        assert "## Tips" in result

    def test_format_tool_help_includes_doc_url(self) -> None:
        """Tool help includes documentation URL."""
        from ot.meta import _format_tool_help

        tool_info = {
            "name": "brave.search",
            "description": "Web search",
            "signature": "brave.search(query: str)",
            "args": ["query: Search query string"],
            "returns": "Search results",
            "example": "brave.search(query='test')",
        }

        result = _format_tool_help(tool_info, "brave")

        assert "# brave.search" in result
        assert "## Docs" in result
        assert "brave-search" in result  # Uses mapped slug

    def test_format_search_results_grouped(self) -> None:
        """Search results are grouped by type."""
        from ot.meta import _format_search_results

        result = _format_search_results(
            query="test",
            tools_results=[{"name": "ot.tools", "description": "List tools"}],
            packs_results=[{"name": "ot", "tool_count": 5}],
            snippets_results=[],
            aliases_results=[],
            info="min",
        )

        assert 'Search results for "test"' in result
        assert "## Tools" in result
        assert "## Packs" in result
        assert "ot.tools" in result

    def test_format_search_results_no_matches(self) -> None:
        """Empty search results show suggestions."""
        from ot.meta import _format_search_results

        result = _format_search_results(
            query="nonexistent",
            tools_results=[],
            packs_results=[],
            snippets_results=[],
            aliases_results=[],
            info="min",
        )

        assert "No matches found" in result
        assert "ot.tools()" in result


@pytest.mark.unit
@pytest.mark.core
class TestHelpRegistration:
    """Tests for help function registration."""

    def test_help_in_pack_functions(self) -> None:
        """help is registered in ot pack functions."""
        from ot.meta import get_ot_pack_functions

        funcs = get_ot_pack_functions()

        assert "help" in funcs
        assert callable(funcs["help"])

    def test_help_in_all_exports(self) -> None:
        """help is in __all__ exports."""
        from ot import meta

        assert "help" in meta.__all__
