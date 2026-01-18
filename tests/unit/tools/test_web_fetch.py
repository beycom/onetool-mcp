"""Tests for web content extraction tools.

Tests trafilatura mocks for fetch functionality.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if dependencies are not available
pytest.importorskip("trafilatura")

from ot_tools.web_fetch import (
    fetch,
    fetch_batch,
)


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
    @patch("ot_tools.web_fetch.get_config")
    def test_successful_fetch(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html><body>Content</body></html>"
        mock_trafilatura.extract.return_value = "Extracted content from page."

        result = fetch(url="https://example.com", use_cache=False)

        assert "Extracted content" in result

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_returns_error_on_fetch_failure(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = None

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "Failed to fetch" in result

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_returns_error_on_no_content(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html></html>"
        mock_trafilatura.extract.return_value = None

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "No content" in result

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_text_output_format(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "Plain text"

        fetch(url="https://example.com", output_format="text", use_cache=False)

        # Should convert "text" to "txt" for trafilatura
        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["output_format"] == "txt"

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_markdown_output_format(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "# Heading\n\nParagraph"

        result = fetch(
            url="https://example.com", output_format="markdown", use_cache=False
        )

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["output_format"] == "markdown"

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_include_links_option(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", include_links=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["include_links"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_fast_option(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", fast=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["fast"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.truncate")
    @patch("ot_tools.web_fetch.get_config")
    def test_truncates_long_content(self, mock_config, mock_truncate, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 100,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "x" * 200
        mock_truncate.return_value = "x" * 100 + "...[Content truncated...]"

        result = fetch(url="https://example.com", max_length=100, use_cache=False)

        mock_truncate.assert_called_once()

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_handles_exception(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.side_effect = Exception("Network error")

        result = fetch(url="https://example.com", use_cache=False)

        assert "Error" in result
        assert "Network error" in result

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_favor_precision(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", favor_precision=True, use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["favor_precision"] is True

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_target_language(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>content</html>"
        mock_trafilatura.extract.return_value = "content"

        fetch(url="https://example.com", target_language="en", use_cache=False)

        call_args = mock_trafilatura.extract.call_args
        assert call_args.kwargs["target_language"] == "en"


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


# -----------------------------------------------------------------------------
# Cache Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFetchCache:
    """Test fetch caching behavior."""

    @patch("ot_tools.web_fetch._fetch_url_cached")
    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_uses_cache_by_default(self, mock_config, mock_trafilatura, mock_cached):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_cached.return_value = "<html>cached</html>"
        mock_trafilatura.extract.return_value = "Cached content"

        fetch(url="https://example.com")

        mock_cached.assert_called_once()

    @patch("ot_tools.web_fetch.trafilatura")
    @patch("ot_tools.web_fetch.get_config")
    def test_bypasses_cache_when_disabled(self, mock_config, mock_trafilatura):
        mock_config.side_effect = lambda k: {
            "tools.web_fetch.timeout": 30.0,
            "tools.web_fetch.max_length": 50000,
        }.get(k)

        mock_trafilatura.fetch_url.return_value = "<html>fresh</html>"
        mock_trafilatura.extract.return_value = "Fresh content"

        fetch(url="https://example.com", use_cache=False)

        mock_trafilatura.fetch_url.assert_called_once()
