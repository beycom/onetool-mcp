"""Tests for web content extraction tools.

Tests trafilatura mocks for fetch functionality.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Skip all tests if dependencies are not available
pytest.importorskip("trafilatura")

from ot_tools.web_fetch import (
    Config,
    _format_error,
    _validate_options,
    _validate_url,
    fetch,
    fetch_batch,
)


@pytest.fixture
def mock_web_config() -> Generator[None, None, None]:
    """Mock web fetch configuration."""
    test_config = Config(timeout=30.0, max_length=50000)
    with patch("ot_tools.web_fetch.get_tool_config", return_value=test_config):
        yield


# -----------------------------------------------------------------------------
# Validation Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestValidateUrl:
    """Test URL validation."""

    def test_valid_url_passes(self):
        # Should not raise
        _validate_url("https://example.com")
        _validate_url("http://example.com/path")
        _validate_url("https://sub.example.com/path?query=1")

    def test_empty_url_raises(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            _validate_url("")

    def test_whitespace_url_raises(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            _validate_url("   ")

    def test_missing_scheme_raises(self):
        with pytest.raises(ValueError, match="Invalid URL format"):
            _validate_url("example.com")

    def test_missing_netloc_raises(self):
        with pytest.raises(ValueError, match="Invalid URL format"):
            _validate_url("https://")


@pytest.mark.unit
@pytest.mark.tools
class TestValidateOptions:
    """Test conflicting options validation."""

    def test_both_false_passes(self):
        # Should not raise
        _validate_options(favor_precision=False, favor_recall=False)

    def test_precision_only_passes(self):
        # Should not raise
        _validate_options(favor_precision=True, favor_recall=False)

    def test_recall_only_passes(self):
        # Should not raise
        _validate_options(favor_precision=False, favor_recall=True)

    def test_both_true_raises(self):
        with pytest.raises(ValueError, match="Cannot set both"):
            _validate_options(favor_precision=True, favor_recall=True)


@pytest.mark.unit
@pytest.mark.tools
class TestFormatError:
    """Test error formatting."""

    def test_text_format(self):
        result = _format_error(
            url="https://example.com",
            error="fetch_failed",
            message="Failed to fetch",
            output_format="text",
        )
        assert result == "Error: Failed to fetch"

    def test_markdown_format(self):
        result = _format_error(
            url="https://example.com",
            error="fetch_failed",
            message="Failed to fetch",
            output_format="markdown",
        )
        assert result == "Error: Failed to fetch"

    def test_json_format(self):
        result = _format_error(
            url="https://example.com",
            error="fetch_failed",
            message="Failed to fetch",
            output_format="json",
        )
        parsed = json.loads(result)
        assert parsed["error"] == "fetch_failed"
        assert parsed["url"] == "https://example.com"
        assert parsed["message"] == "Failed to fetch"


# -----------------------------------------------------------------------------
# Configuration Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestCreateConfig:
    """Test _create_config function."""

    def test_creates_config_with_timeout(self):
        from ot_tools.web_fetch import _create_config

        config = _create_config(30.0)

        # Should return a trafilatura config object
        assert config is not None


# -----------------------------------------------------------------------------
# Fetch Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFetch:
    """Test fetch function with mocked trafilatura."""

    @patch("ot_tools.web_fetch.trafilatura")
    def test_successful_fetch(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted content from page."

        result = fetch(url="https://example.com", use_cache=False)

        assert "Extracted content" in result

    @patch("ot_tools.web_fetch.trafilatura")
    def test_returns_error_on_fetch_failure(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = None

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "Failed to fetch" in result

    @patch("ot_tools.web_fetch.trafilatura")
    def test_returns_error_on_no_content(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html></html>"
        mock_trafilatura.extract.return_value = None

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "No content" in result

    @patch("ot_tools.web_fetch.trafilatura")
    def test_text_output_format(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "Plain text"

        fetch(url="https://example.com", output_format="text", use_cache=False)

        # Should convert "text" to "txt" for trafilatura
        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["output_format"] == "txt"

    @patch("ot_tools.web_fetch.trafilatura")
    def test_markdown_output_format(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "# Heading\n\nParagraph"

        fetch(
            url="https://example.com", output_format="markdown", use_cache=False
        )

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["output_format"] == "markdown"

    @patch("ot_tools.web_fetch.trafilatura")
    def test_include_links_option(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", include_links=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["include_links"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    def test_fast_option(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", fast=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["fast"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.truncate")
    def test_truncates_long_content(self, mock_truncate, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "x" * 200
        mock_truncate.return_value = "x" * 100 + "...[Content truncated...]"

        # Pass explicit max_length to trigger truncation (overrides config default)
        fetch(url="https://example.com", max_length=100, use_cache=False)

        mock_truncate.assert_called_once()

    @patch("ot_tools.web_fetch.trafilatura")
    def test_handles_exception(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.side_effect = Exception("Network error")

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "Network error" in result

    @patch("ot_tools.web_fetch.trafilatura")
    def test_favor_precision(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", favor_precision=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["favor_precision"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    def test_target_language(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", target_language="en", use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["target_language"] == "en"

    def test_raises_on_empty_url(self, mock_web_config):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            fetch(url="", use_cache=False)

    def test_raises_on_invalid_url(self, mock_web_config):
        with pytest.raises(ValueError, match="Invalid URL format"):
            fetch(url="not-a-url", use_cache=False)

    def test_raises_on_conflicting_options(self, mock_web_config):
        with pytest.raises(ValueError, match="Cannot set both"):
            fetch(
                url="https://example.com",
                favor_precision=True,
                favor_recall=True,
                use_cache=False,
            )

    @patch("ot_tools.web_fetch.trafilatura")
    def test_json_error_format(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = None

        result = fetch(
            url="https://example.com", output_format="json", use_cache=False
        )

        parsed = json.loads(result)
        assert parsed["error"] == "fetch_failed"
        assert parsed["url"] == "https://example.com"

    @patch("ot_tools.web_fetch.trafilatura")
    def test_include_metadata(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = '{"text": "content", "title": "Test"}'

        result = fetch(
            url="https://example.com",
            output_format="json",
            include_metadata=True,
            use_cache=False,
        )

        parsed = json.loads(result)
        assert "content" in parsed
        assert "metadata" in parsed
        assert "final_url" in parsed["metadata"]
        assert parsed["metadata"]["final_url"] == "https://example.com"


# -----------------------------------------------------------------------------
# Fetch Batch Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFetchBatch:
    """Test fetch_batch function."""

    @patch("ot_tools.web_fetch.fetch")
    def test_fetches_multiple_urls(self, mock_fetch):
        mock_fetch.return_value = "Content"

        result = fetch_batch(
            urls=[
                "https://example1.com",
                "https://example2.com",
            ]
        )

        assert mock_fetch.call_count == 2
        assert "example1.com" in result
        assert "example2.com" in result

    @patch("ot_tools.web_fetch.fetch")
    def test_handles_tuples_with_labels(self, mock_fetch):
        mock_fetch.return_value = "Content"

        result = fetch_batch(
            urls=[
                ("https://example.com", "Custom Label"),
            ]
        )

        assert "Custom Label" in result

    @patch("ot_tools.web_fetch.fetch")
    def test_preserves_order(self, mock_fetch):
        mock_fetch.side_effect = ["First content", "Second content"]

        result = fetch_batch(
            urls=[
                ("https://first.com", "First"),
                ("https://second.com", "Second"),
            ]
        )

        # Check that First appears before Second
        first_pos = result.find("First")
        second_pos = result.find("Second")
        assert first_pos < second_pos

    @patch("ot_tools.web_fetch.fetch")
    def test_passes_options(self, mock_fetch):
        mock_fetch.return_value = "Content"

        fetch_batch(
            urls=["https://example.com"],
            output_format="text",
            include_links=True,
            fast=True,
        )

        call_args = mock_fetch.call_args
        assert call_args.kwargs["output_format"] == "text"
        assert call_args.kwargs["include_links"] is True
        assert call_args.kwargs["fast"] is True

    @patch("ot_tools.web_fetch.fetch")
    def test_handles_errors_gracefully(self, mock_fetch):
        mock_fetch.side_effect = [
            "Good content",
            "Error: Failed to fetch URL",
        ]

        result = fetch_batch(
            urls=[
                "https://good.com",
                "https://bad.com",
            ]
        )

        # Both results should be included
        assert "Good content" in result
        assert "Error" in result

    @patch("ot_tools.web_fetch.fetch")
    def test_passes_all_options(self, mock_fetch):
        """Verify fetch_batch passes all parameters to fetch."""
        mock_fetch.return_value = "Content"

        fetch_batch(
            urls=["https://example.com"],
            output_format="text",
            include_links=True,
            include_images=True,
            include_tables=False,
            include_comments=True,
            include_formatting=False,
            favor_precision=True,
            favor_recall=False,
            fast=True,
            target_language="en",
            max_length=1000,
            timeout=10.0,
            use_cache=False,
        )

        call_args = mock_fetch.call_args
        assert call_args.kwargs["output_format"] == "text"
        assert call_args.kwargs["include_links"] is True
        assert call_args.kwargs["include_images"] is True
        assert call_args.kwargs["include_tables"] is False
        assert call_args.kwargs["include_comments"] is True
        assert call_args.kwargs["include_formatting"] is False
        assert call_args.kwargs["favor_precision"] is True
        assert call_args.kwargs["favor_recall"] is False
        assert call_args.kwargs["fast"] is True
        assert call_args.kwargs["target_language"] == "en"
        assert call_args.kwargs["max_length"] == 1000
        assert call_args.kwargs["timeout"] == 10.0
        assert call_args.kwargs["use_cache"] is False

    def test_raises_on_conflicting_options(self):
        with pytest.raises(ValueError, match="Cannot set both"):
            fetch_batch(
                urls=["https://example.com"],
                favor_precision=True,
                favor_recall=True,
            )


# -----------------------------------------------------------------------------
# Cache Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFetchCache:
    """Test fetch caching behavior."""

    @patch("ot_tools.web_fetch._fetch_url_cached")
    @patch("ot_tools.web_fetch.trafilatura")
    def test_uses_cache_by_default(self, mock_trafilatura, mock_cached, mock_web_config):
        mock_cached.return_value = "<html>cached</html>"
        mock_trafilatura.extract.return_value = "Cached content"

        fetch(url="https://example.com")

        mock_cached.assert_called_once()

    @patch("ot_tools.web_fetch.trafilatura")
    def test_bypasses_cache_when_disabled(self, mock_trafilatura, mock_web_config):
        mock_trafilatura.fetch_url.return_value = "<html>fresh</html>"
        mock_trafilatura.extract.return_value = "Fresh content"

        fetch(url="https://example.com", use_cache=False)

        mock_trafilatura.fetch_url.assert_called_once()
