"""Tests for grounding search tools.

Tests response parsing functions and main functions with Gemini mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("google.genai", reason="google-genai not installed ([util] extra)")

from otutil.tools.ground import (
    Config,
    _extract_structured_data,
    _extract_sources,
    _format_error,
    _format_response,
    _format_sources,
    dev,
    docs,
    reddit,
    search,
    search_batch,
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
        chunk.web.uri = "https://en.wikipedia.org/wiki/Test"

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]
        response.candidates[0].grounding_metadata.grounding_supports = None

        sources = _extract_sources(response)

        assert len(sources) == 1
        assert sources[0]["title"] == "Source Title"
        assert sources[0]["url"] == "https://en.wikipedia.org/wiki/Test"

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
        chunk1.web.uri = "https://en.wikipedia.org/wiki/Test"

        chunk2 = MagicMock()
        chunk2.web = MagicMock()
        chunk2.web.title = "Source 2"
        chunk2.web.uri = "https://en.wikipedia.org/wiki/Test"  # Same URL

        response.candidates[0].grounding_metadata.grounding_chunks = [chunk1, chunk2]

        result = _format_response(response)

        # Should only appear once
        assert result.count("https://en.wikipedia.org/wiki/Test") == 1


# -----------------------------------------------------------------------------
# Gemini Mock Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked Gemini client."""

    @patch("otutil.tools.ground._grounded_search")
    def test_successful_search(self, mock_grounded):
        mock_grounded.return_value = "Search results here."

        result = search(query="Python best practices")

        assert "Search results" in result
        mock_grounded.assert_called_once()

    def test_rejects_invalid_timeout_before_network(self):
        result = search(query="Python best practices", timeout=0)

        assert "timeout must be between 1.0 and 300.0 seconds" in result

    def test_rejects_non_numeric_timeout_before_network(self):
        result = search(query="Python best practices", timeout="x")  # type: ignore[arg-type]
        assert "timeout must be between 1.0 and 300.0 seconds" in result

        result = search(query="Python best practices", timeout=True)  # type: ignore[arg-type]
        assert "timeout must be between 1.0 and 300.0 seconds" in result

    @patch("otutil.tools.ground._grounded_search")
    def test_includes_context(self, mock_grounded):
        mock_grounded.return_value = "results"

        search(query="error handling", context="Python async")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "Python async" in prompt

    @patch("otutil.tools.ground._grounded_search")
    def test_focus_modes(self, mock_grounded):
        mock_grounded.return_value = "results"

        # Test each focus mode
        for focus in ["general", "code", "documentation", "troubleshooting"]:
            search(query="test", focus=focus)

        assert mock_grounded.call_count == 4

    @patch("otutil.tools.ground._grounded_search")
    def test_custom_model(self, mock_grounded):
        mock_grounded.return_value = "results"

        search(query="test query", model="gemini-3.0-flash")

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["model"] == "gemini-3.0-flash"

    @patch("otutil.tools.ground._grounded_search")
    def test_model_defaults_to_none(self, mock_grounded):
        mock_grounded.return_value = "results"

        search(query="test query")

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["model"] is None


@pytest.mark.unit
@pytest.mark.tools
class TestDev:
    """Test dev function with mocked Gemini client."""

    @patch("otutil.tools.ground._grounded_search")
    def test_successful_dev_search(self, mock_grounded):
        mock_grounded.return_value = "Developer resources."

        result = dev(query="websocket handling")

        assert "Developer resources" in result

    @patch("otutil.tools.ground._grounded_search")
    def test_includes_language(self, mock_grounded):
        mock_grounded.return_value = "results"

        dev(query="JSON parsing", language="Python")

        call_args = mock_grounded.call_args
        prompt = call_args[0][0]
        assert "Python" in prompt

    @patch("otutil.tools.ground._grounded_search")
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

    @patch("otutil.tools.ground._grounded_search")
    def test_successful_docs_search(self, mock_grounded):
        mock_grounded.return_value = "Documentation content."

        result = docs(query="async context managers")

        assert "Documentation" in result

    @patch("otutil.tools.ground._grounded_search")
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

    @patch("otutil.tools.ground._grounded_search")
    def test_successful_reddit_search(self, mock_grounded):
        mock_grounded.return_value = "Reddit discussions."

        result = reddit(query="best Python framework")

        assert "Reddit" in result

    @patch("otutil.tools.ground._grounded_search")
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

    @patch("otutil.tools.ground._require_google_genai")
    def test_missing_google_genai_returns_formatted_error(self, mock_require):
        from otutil.tools.ground import _grounded_search

        mock_require.side_effect = ImportError(
            "google-genai is required for grounding_search. "
            "Install with: pip install onetool-mcp[util]"
        )

        result = _grounded_search("test", span_name="test.span")

        assert isinstance(result, str)
        assert "google-genai" in result
        assert "pip install onetool-mcp[util]" in result

    def test_config_accepts_timeout(self):
        cfg = Config(timeout=180.0)

        assert cfg.timeout == 180.0

    def test_default_timeout_is_180(self):
        assert Config().timeout == 180.0

    @patch("otutil.tools.ground._require_google_genai")
    @patch("otutil.tools.ground._get_client")
    @patch("otutil.tools.ground.get_tool_config")
    def test_successful_grounded_search(self, mock_config, mock_get_client, mock_require):
        import sys
        from unittest.mock import MagicMock

        from otutil.tools.ground import Config, _grounded_search

        mock_config.return_value = Config(model="gemini-2.0-flash")

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Search result text"
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        mock_types = MagicMock()
        with patch.dict(sys.modules, {"google.genai.types": mock_types, "google.genai": MagicMock(types=mock_types)}):
            result = _grounded_search("test query", span_name="test.span")

        assert "Search result text" in result

    @patch("otutil.tools.ground._require_google_genai")
    @patch("otutil.tools.ground._get_client")
    @patch("otutil.tools.ground.get_tool_config")
    def test_grounded_search_uses_configured_timeout(self, mock_config, mock_get_client, mock_require):
        import sys
        from unittest.mock import MagicMock

        from otutil.tools.ground import Config, _grounded_search

        mock_config.return_value = Config(model="gemini-2.0-flash", timeout=180.0)

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Search result text"
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        mock_types = MagicMock()
        with patch.dict(sys.modules, {"google.genai.types": mock_types, "google.genai": MagicMock(types=mock_types)}):
            _grounded_search("test query", span_name="test.span")

        config_kwargs = mock_types.GenerateContentConfig.call_args.kwargs
        assert config_kwargs["http_options"]["timeout"] == 180_000

    @patch("otutil.tools.ground._require_google_genai")
    @patch("otutil.tools.ground._get_client")
    @patch("otutil.tools.ground.get_tool_config")
    def test_handles_api_error(self, mock_config, mock_get_client, mock_require):
        import sys
        from unittest.mock import MagicMock

        from otutil.tools.ground import Config, _grounded_search

        mock_config.return_value = Config(model="gemini-2.0-flash")

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API Error")

        mock_types = MagicMock()
        with patch.dict(sys.modules, {"google.genai.types": mock_types, "google.genai": MagicMock(types=mock_types)}):
            result = _grounded_search("test", span_name="test.span")

        assert "Error" in result

    @patch("otutil.tools.ground.require_api_key")
    def test_build_client_without_key(self, mock_require):
        from otutil.tools.ground import _build_client

        mock_require.return_value = ("", "Error: GEMINI_API_KEY secret not configured")

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            _build_client()


# -----------------------------------------------------------------------------
# Source Numbering Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFormatSources:
    """Test _format_sources function for correct numbering."""

    def test_sequential_numbering_with_duplicates(self):
        """Verify source numbers are sequential when duplicates are removed."""
        sources = [
            {"title": "Source A", "url": "https://a.com"},
            {"title": "Source B", "url": "https://b.com"},
            {"title": "Source A Dup", "url": "https://a.com"},  # Duplicate URL
            {"title": "Source C", "url": "https://c.com"},
        ]

        result = _format_sources(sources)

        # Should have sequential numbering 1, 2, 3 (not 1, 2, 4)
        assert "1. [Source A]" in result
        assert "2. [Source B]" in result
        assert "3. [Source C]" in result
        assert "4." not in result

    def test_max_sources_limit(self):
        """Verify max_sources parameter limits output."""
        sources = [
            {"title": "Source A", "url": "https://a.com"},
            {"title": "Source B", "url": "https://b.com"},
            {"title": "Source C", "url": "https://c.com"},
        ]

        result = _format_sources(sources, max_sources=2)

        assert "1. [Source A]" in result
        assert "2. [Source B]" in result
        assert "Source C" not in result

    def test_uses_url_when_title_empty(self):
        """Verify URL is used as title when title is empty."""
        sources = [{"title": "", "url": "https://en.wikipedia.org/wiki/Test"}]

        result = _format_sources(sources)

        assert "[https://en.wikipedia.org/wiki/Test](https://en.wikipedia.org/wiki/Test)" in result


# -----------------------------------------------------------------------------
# Empty Query Validation Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestEmptyQueryValidation:
    """Test empty query validation across all search functions."""

    def test_search_rejects_empty_query(self):
        """search() should return error string for empty query."""
        result = search(query="")
        assert "Error" in result
        assert "query cannot be empty" in result

    def test_search_rejects_whitespace_query(self):
        """search() should return error string for whitespace-only query."""
        result = search(query="   ")
        assert "Error" in result
        assert "query cannot be empty" in result

    def test_dev_rejects_empty_query(self):
        """dev() should return error string for empty query."""
        result = dev(query="")
        assert "Error" in result
        assert "query cannot be empty" in result

    def test_docs_rejects_empty_query(self):
        """docs() should return error string for empty query."""
        result = docs(query="")
        assert "Error" in result
        assert "query cannot be empty" in result

    def test_reddit_rejects_empty_query(self):
        """reddit() should return error string for empty query."""
        result = reddit(query="")
        assert "Error" in result
        assert "query cannot be empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestEmptyBatchValidation:
    """Test empty batch validation for search_batch."""

    def test_search_batch_rejects_empty_list(self):
        """search_batch() should return error string for empty queries list."""
        result = search_batch(queries=[])
        assert "Error" in result
        assert "queries list cannot be empty" in result


# -----------------------------------------------------------------------------
# New Parameter Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestNewParameters:
    """Test new parameters for search functions."""

    @patch("otutil.tools.ground._grounded_search")
    def test_search_passes_timeout(self, mock_grounded):
        """search() should pass timeout parameter."""
        mock_grounded.return_value = "results"

        search(query="test", timeout=60.0)

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["timeout"] == 60.0

    @patch("otutil.tools.ground._grounded_search")
    def test_search_passes_max_sources(self, mock_grounded):
        """search() should pass max_sources parameter."""
        mock_grounded.return_value = "results"

        search(query="test", max_sources=5)

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["max_sources"] == 5

    @patch("otutil.tools.ground._grounded_search")
    def test_search_passes_output_format(self, mock_grounded):
        """search() should pass output_format parameter."""
        mock_grounded.return_value = "results"

        search(query="test", output_format="text_only")

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["output_format"] == "text_only"

    @patch("otutil.tools.ground._grounded_search")
    def test_dev_passes_new_parameters(self, mock_grounded):
        """dev() should pass new parameters."""
        mock_grounded.return_value = "results"

        dev(query="test", timeout=45.0, max_sources=3, output_format="sources_only")

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["timeout"] == 45.0
        assert call_kwargs["max_sources"] == 3
        assert call_kwargs["output_format"] == "sources_only"

    @patch("otutil.tools.ground._grounded_search")
    def test_docs_passes_new_parameters(self, mock_grounded):
        """docs() should pass new parameters."""
        mock_grounded.return_value = "results"

        docs(query="test", timeout=45.0, max_sources=3)

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["timeout"] == 45.0
        assert call_kwargs["max_sources"] == 3

    @patch("otutil.tools.ground._grounded_search")
    def test_reddit_passes_new_parameters(self, mock_grounded):
        """reddit() should pass new parameters."""
        mock_grounded.return_value = "results"

        reddit(query="test", timeout=45.0, max_sources=3)

        call_kwargs = mock_grounded.call_args[1]
        assert call_kwargs["timeout"] == 45.0
        assert call_kwargs["max_sources"] == 3


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatchModel:
    """Test model parameter in search_batch."""

    @patch("otutil.tools.ground.search")
    @patch("otutil.tools.ground.batch_execute_enveloped")
    def test_search_batch_passes_model(self, mock_batch, mock_search):
        """search_batch() should pass model parameter to search()."""
        mock_batch.return_value = {"results": [], "meta": {"success_count": 0, "error_count": 0}}

        search_batch(queries=["test"], model="gemini-3.0-flash")

        # Extract the function passed to batch_execute_enveloped and call it
        search_fn = mock_batch.call_args[0][0]
        search_fn("test query", "label")

        # Verify model was passed
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["model"] == "gemini-3.0-flash"

    @patch("otutil.tools.ground.search")
    def test_search_batch_structured_envelope(self, mock_search):
        mock_search.return_value = "Result"
        result = search_batch(queries=["q1", "q2"])

        assert isinstance(result, dict)
        assert result["meta"]["query_count"] == 2
        assert result["results"][0]["query"] == "q1"
        assert result["results"][1]["query"] == "q2"

    def test_search_batch_rejects_invalid_retry_controls(self):
        result = search_batch(queries=["q1"], retries=-1)

        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["q1"], retries="x")  # type: ignore[arg-type]

        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["q1"], retries=4)

        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["q1"], retry_delay_ms=10_001)

        assert "retry_delay_ms must be between 0 and 10000" in result

        result = search_batch(queries=["q1"], retry_delay_ms="x")  # type: ignore[arg-type]

        assert "retry_delay_ms must be between 0 and 10000" in result

    @patch("otutil.tools.ground.search")
    def test_search_batch_accepts_retry_control_upper_bounds(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(
            queries=["q1"],
            timeout=300.0,
            retries=3,
            retry_delay_ms=10_000,
        )

        assert isinstance(result, dict)
        assert result["meta"]["retries"] == 3


@pytest.mark.unit
@pytest.mark.tools
class TestStructuredExtraction:
    def test_extract_structured_data_required_and_optional(self):
        result = _extract_structured_data(
            text="name: Alice\nemail: alice@example.com",
            sources=[{"title": "src", "url": "https://example.invalid"}],
            extract_schema={
                "fields": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "phone", "type": "string", "required": False},
                ]
            },
            return_provenance=True,
        )

        assert result["data"]["name"] == "Alice"
        assert result["data"]["phone"] is None
        assert result["errors"] == []
        assert "provenance" in result
        assert result["provenance"]["name"]["source_url"] == "https://example.invalid"

    @patch("otutil.tools.ground._grounded_search")
    def test_search_passes_extract_schema(self, mock_grounded):
        mock_grounded.return_value = {"mode": "structured_extraction", "data": {}, "errors": []}
        schema = {"fields": [{"name": "email", "type": "string", "required": True}]}

        search(query="contact info", extract_schema=schema, return_provenance=True)

        kwargs = mock_grounded.call_args.kwargs
        assert kwargs["extract_schema"] == schema
        assert kwargs["return_provenance"] is True

    def test_search_rejects_invalid_extract_schema(self):
        result = search(query="x", extract_schema={"fields": []})
        assert "extract_schema.fields must be a non-empty list" in result


# -----------------------------------------------------------------------------
# Output Format Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestOutputFormat:
    """Test output_format parameter behavior."""

    def test_format_response_text_only(self):
        """output_format='text_only' should return only text content."""
        response = MagicMock()
        response.text = "Content here."
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        chunk = MagicMock()
        chunk.web = MagicMock()
        chunk.web.title = "Source"
        chunk.web.uri = "https://source.com"
        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]

        result = _format_response(response, output_format="text_only")

        assert "Content here." in result
        assert "Sources" not in result
        assert "source.com" not in result

    def test_format_response_sources_only(self):
        """output_format='sources_only' should return only sources."""
        response = MagicMock()
        response.text = "Content here."
        response.candidates = [MagicMock()]
        response.candidates[0].grounding_metadata = MagicMock()

        chunk = MagicMock()
        chunk.web = MagicMock()
        chunk.web.title = "Source"
        chunk.web.uri = "https://source.com"
        response.candidates[0].grounding_metadata.grounding_chunks = [chunk]

        result = _format_response(response, output_format="sources_only")

        assert "Content here." not in result
        assert "source.com" in result

    def test_format_response_sources_only_no_sources(self):
        """output_format='sources_only' with no sources returns appropriate message."""
        response = MagicMock()
        response.text = "Content here."
        response.candidates = []

        result = _format_response(response, output_format="sources_only")

        assert result == "No sources found."


# -----------------------------------------------------------------------------
# Error Message Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestErrorMessages:
    """Test improved error message formatting."""

    def test_quota_error(self):
        """Quota errors should return helpful message."""
        exc = Exception("Resource has been exhausted (quota)")

        result = _format_error(exc)

        assert "quota exceeded" in result.lower()
        assert "try again later" in result.lower()

    def test_rate_limit_error(self):
        """Rate limit errors should return helpful message."""
        exc = Exception("Rate limit exceeded")

        result = _format_error(exc)

        assert "quota exceeded" in result.lower()

    def test_authentication_error(self):
        """Authentication errors should return helpful message."""
        exc = Exception("Authentication failed")

        result = _format_error(exc)

        assert "GEMINI_API_KEY" in result
        assert "secrets.yaml" in result.lower()

    def test_api_key_error(self):
        """API key errors should return helpful message."""
        exc = Exception("Invalid API key provided")

        result = _format_error(exc)

        assert "GEMINI_API_KEY" in result

    def test_timeout_error(self):
        """Timeout errors should return helpful message."""
        exc = Exception("Request timeout after 30 seconds")

        result = _format_error(exc)

        assert "timed out" in result.lower()

    def test_ground_config_timeout_error_not_masked(self):
        """Config errors mentioning timeout should not look like request timeouts."""
        exc = Exception("Invalid tools.ground configuration: timeout must be less than or equal to 300")

        result = _format_error(exc)

        assert "Invalid tools.ground configuration" in result
        assert "Request timed out" not in result

    def test_generic_error(self):
        """Generic errors should include original message."""
        exc = Exception("Something went wrong")

        result = _format_error(exc)

        assert "Search failed" in result
        assert "Something went wrong" in result


# -----------------------------------------------------------------------------
# Client Caching Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestClientCaching:
    """Test client caching functionality."""

    def test_cached_client_reuses_instance(self):
        """lazy_client should create the factory exactly once across repeated calls."""
        from otpack import lazy_client

        mock_client = MagicMock()
        call_count = 0

        def factory() -> MagicMock:
            nonlocal call_count
            call_count += 1
            return mock_client

        get_client = lazy_client(factory)
        client1 = get_client()
        client2 = get_client()

        assert client1 is client2
        assert call_count == 1
