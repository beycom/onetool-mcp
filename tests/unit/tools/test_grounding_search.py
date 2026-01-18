"""Tests for grounding search tools.

Tests response parsing functions and main functions with Gemini mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ot_tools.grounding_search import (
    _extract_sources,
    _format_response,
    dev,
    docs,
    reddit,
    search,
)


# -----------------------------------------------------------------------------
# Pure Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestExtractSources:
    """Test _extract_sources response parsing function."""

    def test_extracts_from_grounding_chunks(self):
        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        chunk = MagicMock()
        chunk.web = MagicMock()
        chunk.web.title = "Source Title"
        chunk.web.uri = "https://example.com"

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]
        response.candidates[0].grounding_metadata.grounding_supports = None

        sources = _extract_sources(response)

        assert len(sources) == 1
        assert sources[0]["title"] == "Source Title"
        assert sources[0]["url"] == "https://example.com"

    def test_handles_no_candidates(self):
        response = MagicMock()
        response.candidates = []

        sources = _extract_sources(response)

        assert sources == []

    def test_handles_no_grounding_metadata(self):
        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = None

        sources = _extract_sources(response)

        assert sources == []

    def test_handles_missing_candidates_attr(self):
        response = MagicMock(spec=[])  # No attributes

        sources = _extract_sources(response)

        assert sources == []

    def test_skips_empty_uri(self):
        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        chunk = MagicMock()
        chunk.web = MagicMock()
        chunk.web.title = "Title"
        chunk.web.uri = ""  # Empty URI

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]

        sources = _extract_sources(response)

        assert sources == []


@pytest.mark.unit
@pytest.mark.tools
class TestFormatResponse:
    """Test _format_response function."""

    def test_formats_text_content(self):
        response = MagicMock()
        response.text = "This is the response content."
        response.candidates = []

        result = _format_response(response)

        assert "This is the response content." in result

    def test_extracts_text_from_candidates(self):
        response = MagicMock(spec=["candidates"])
        response.candidates = [MagicMock()]
        response.candidates[0].content = MagicMock()
        response.candidates[0].content.parts = [MagicMock()]
        response.candidates[0].content.parts[0].text = "Candidate text"
        response.candidates[0].grounding_metadata = None

        result = _format_response(response)

        assert "Candidate text" in result

    def test_returns_no_results_for_empty(self):
        response = MagicMock(spec=["candidates"])
        response.candidates = []

        result = _format_response(response)

        assert "No results found" in result

    def test_appends_sources(self):
        response = MagicMock()
        response.text = "Content here."
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        chunk = MagicMock()
        chunk.web = MagicMock()
        chunk.web.title = "Source"
        chunk.web.uri = "https://source.com"

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]

        result = _format_response(response)

        assert "Sources" in result
        assert "source.com" in result

    def test_deduplicates_sources(self):
        response = MagicMock()
        response.text = "Content"
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        # Two chunks with same URL
        chunk1 = MagicMock()
        chunk1.web = MagicMock()
        chunk1.web.title = "Source 1"
        chunk1.web.uri = "https://example.com"

        chunk2 = MagicMock()
        chunk2.web = MagicMock()
        chunk2.web.title = "Source 2"
        chunk2.web.uri = "https://example.com"  # Same URL

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk1, chunk2]

        result = _format_response(response)

        # Should only appear once
        assert result.count("https://example.com") == 1


# -----------------------------------------------------------------------------
# Gemini Mock Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked Gemini client."""

    @patch("ot_tools.grounding_search._grounded_search")
    def test_successful_search(self, mock_grounded):
        mock_grounded.return_value = "Search results here."

        result = search(query="Python best practices")

        assert "Search results" in result
        mock_grounded.assert_called_once()

    @patch("ot_tools.grounding_search._grounded_search")
    def test_includes_context(self, mock_grounded):
        mock_grounded.return_value = "results"

        search(query="error handling", context="Python async")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "Python async" in prompt

    @patch("ot_tools.grounding_search._grounded_search")
    def test_focus_modes(self, mock_grounded):
        mock_grounded.return_value = "results"

        # Test each focus mode
        for focus in ["general", "code", "documentation", "troubleshooting"]:
            search(query="test", focus=focus)

        assert mock_grounded.call_count == 4


@pytest.mark.unit
@pytest.mark.tools
class TestDev:
    """Test dev function with mocked Gemini client."""

    @patch("ot_tools.grounding_search._grounded_search")
    def test_successful_dev_search(self, mock_grounded):
        mock_grounded.return_value = "Developer resources."

        result = dev(query="websocket handling")

        assert "Developer resources" in result

    @patch("ot_tools.grounding_search._grounded_search")
    def test_includes_language(self, mock_grounded):
        mock_grounded.return_value = "results"

        dev(query="JSON parsing", language="Python")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "Python" in prompt

    @patch("ot_tools.grounding_search._grounded_search")
    def test_includes_framework(self, mock_grounded):
        mock_grounded.return_value = "results"

        dev(query="dependency injection", framework="FastAPI")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "FastAPI" in prompt


@pytest.mark.unit
@pytest.mark.tools
class TestDocs:
    """Test docs function with mocked Gemini client."""

    @patch("ot_tools.grounding_search._grounded_search")
    def test_successful_docs_search(self, mock_grounded):
        mock_grounded.return_value = "Documentation content."

        result = docs(query="async context managers")

        assert "Documentation" in result

    @patch("ot_tools.grounding_search._grounded_search")
    def test_includes_technology(self, mock_grounded):
        mock_grounded.return_value = "results"

        docs(query="hooks lifecycle", technology="React")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "React" in prompt


@pytest.mark.unit
@pytest.mark.tools
class TestReddit:
    """Test reddit function with mocked Gemini client."""

    @patch("ot_tools.grounding_search._grounded_search")
    def test_successful_reddit_search(self, mock_grounded):
        mock_grounded.return_value = "Reddit discussions."

        result = reddit(query="best Python framework")

        assert "Reddit" in result

    @patch("ot_tools.grounding_search._grounded_search")
    def test_includes_subreddit(self, mock_grounded):
        mock_grounded.return_value = "results"

        reddit(query="FastAPI tips", subreddit="python")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "r/python" in prompt


# -----------------------------------------------------------------------------
# Grounded Search Core Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGroundedSearch:
    """Test _grounded_search core function."""

    @patch("ot_tools.grounding_search._create_client")
    @patch("ot_tools.grounding_search.get_config")
    def test_successful_grounded_search(self, mock_config, mock_create_client):
        from ot_tools.grounding_search import _grounded_search

        mock_config.return_value.tools.ground.model = "gemini-2.0-flash"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Search result text"
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        result = _grounded_search("test query", span_name="test.span")

        assert "Search result text" in result

    @patch("ot_tools.grounding_search._create_client")
    @patch("ot_tools.grounding_search.get_config")
    def test_handles_api_error(self, mock_config, mock_create_client):
        from ot_tools.grounding_search import _grounded_search

        mock_config.return_value.tools.ground.model = "gemini-2.0-flash"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API Error")

        result = _grounded_search("test", span_name="test.span")

        assert "Error" in result

    @patch("ot_tools.grounding_search._get_api_key")
    def test_create_client_without_key(self, mock_key):
        from ot_tools.grounding_search import _create_client

        mock_key.return_value = ""

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            _create_client()
