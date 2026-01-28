"""Tests for Firecrawl web scraping tools.

Tests main functions with mocked Firecrawl SDK client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ot_tools.firecrawl import (
    crawl,
    crawl_status,
    deep_research,
    extract,
    map_urls,
    scrape,
    scrape_batch,
    search,
)

# -----------------------------------------------------------------------------
# Client Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestClientInitialization:
    """Test client initialization and API key handling."""

    @patch("ot_tools.firecrawl._get_client")
    def test_returns_error_without_api_key(self, mock_client):
        mock_client.return_value = None

        result = scrape(url="https://example.com")

        assert "FIRECRAWL_API_KEY" in result


# -----------------------------------------------------------------------------
# Scrape Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestScrape:
    """Test scrape function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_scrape(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.scrape.return_value = {
            "markdown": "# Hello World\n\nContent here.",
            "metadata": {"title": "Example"},
        }
        mock_get_client.return_value = mock_client

        result = scrape(url="https://example.com")

        assert isinstance(result, dict)
        assert "markdown" in result
        mock_client.scrape.assert_called_once()

    @patch("ot_tools.firecrawl._get_client")
    def test_scrape_with_formats(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.scrape.return_value = {"markdown": "content", "links": []}
        mock_get_client.return_value = mock_client

        scrape(url="https://example.com", formats=["markdown", "links"])

        call_args = mock_client.scrape.call_args
        assert call_args[1]["formats"] == ["markdown", "links"]

    @patch("ot_tools.firecrawl._get_client")
    def test_scrape_with_options(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.scrape.return_value = {"markdown": "content"}
        mock_get_client.return_value = mock_client

        scrape(
            url="https://example.com",
            only_main_content=False,
            include_tags=["article"],
            mobile=True,
        )

        call_args = mock_client.scrape.call_args
        assert call_args[1]["only_main_content"] is False
        assert call_args[1]["include_tags"] == ["article"]
        assert call_args[1]["mobile"] is True

    @patch("ot_tools.firecrawl._get_client")
    def test_scrape_handles_exception(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.scrape.side_effect = Exception("Network error")
        mock_get_client.return_value = mock_client

        result = scrape(url="https://example.com")

        assert isinstance(result, str)
        assert "Scrape failed" in result
        assert "Network error" in result


# -----------------------------------------------------------------------------
# Scrape Batch Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestScrapeBatch:
    """Test scrape_batch function."""

    @patch("ot_tools.firecrawl.scrape")
    def test_executes_multiple_urls(self, mock_scrape):
        mock_scrape.return_value = {"markdown": "content"}

        result = scrape_batch(urls=["https://1.com", "https://2.com"])

        assert mock_scrape.call_count == 2
        assert "https://1.com" in result
        assert "https://2.com" in result

    @patch("ot_tools.firecrawl.scrape")
    def test_handles_tuples_with_labels(self, mock_scrape):
        mock_scrape.return_value = {"markdown": "content"}

        result = scrape_batch(urls=[("https://example.com", "Example Site")])

        assert "Example Site" in result

    @patch("ot_tools.firecrawl.scrape")
    def test_isolates_errors(self, mock_scrape):
        mock_scrape.side_effect = [
            {"markdown": "success"},
            "Error: Failed",
        ]

        result = scrape_batch(urls=["https://1.com", "https://2.com"])

        assert isinstance(result["https://1.com"], dict)
        assert isinstance(result["https://2.com"], str)


# -----------------------------------------------------------------------------
# Map Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestMapUrls:
    """Test map_urls function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_map_urls(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.map.return_value = [
            "https://example.com/page1",
            "https://example.com/page2",
        ]
        mock_get_client.return_value = mock_client

        result = map_urls(url="https://example.com")

        assert isinstance(result, list)
        assert len(result) == 2

    @patch("ot_tools.firecrawl._get_client")
    def test_map_urls_with_search(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.map.return_value = []
        mock_get_client.return_value = mock_client

        map_urls(url="https://example.com", search="python")

        call_args = mock_client.map.call_args
        assert call_args[1]["search"] == "python"

    @patch("ot_tools.firecrawl._get_client")
    def test_map_urls_with_limit(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.map.return_value = []
        mock_get_client.return_value = mock_client

        map_urls(url="https://example.com", limit=100)

        call_args = mock_client.map.call_args
        assert call_args[1]["limit"] == 100

    @patch("ot_tools.firecrawl._get_client")
    def test_map_urls_handles_response_object(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.links = ["https://example.com/a", "https://example.com/b"]
        mock_client.map.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = map_urls(url="https://example.com")

        assert result == ["https://example.com/a", "https://example.com/b"]


# -----------------------------------------------------------------------------
# Search Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestSearch:
    """Test search function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_search(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {"url": "https://result.com", "title": "Result"},
        ]
        mock_get_client.return_value = mock_client

        result = search(query="python tutorials")

        assert isinstance(result, list)
        assert len(result) == 1

    @patch("ot_tools.firecrawl._get_client")
    def test_search_with_limit(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        search(query="test", limit=10)

        call_args = mock_client.search.call_args
        assert call_args[1]["limit"] == 10

    @patch("ot_tools.firecrawl._get_client")
    def test_search_with_scrape_options(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        search(query="test", scrape_options={"formats": ["markdown"]})

        call_args = mock_client.search.call_args
        assert call_args[1]["scrape_options"] == {"formats": ["markdown"]}


# -----------------------------------------------------------------------------
# Crawl Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestCrawl:
    """Test crawl function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_crawl_start(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.crawl.return_value = {
            "id": "job123",
            "status": "started",
        }
        mock_get_client.return_value = mock_client

        result = crawl(url="https://example.com")

        assert isinstance(result, dict)
        assert result.get("id") == "job123"

    @patch("ot_tools.firecrawl._get_client")
    def test_crawl_with_options(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.crawl.return_value = {"id": "job123"}
        mock_get_client.return_value = mock_client

        crawl(
            url="https://example.com",
            max_depth=2,
            limit=100,
            include_paths=["/docs/*"],
        )

        call_args = mock_client.crawl.call_args
        assert call_args[1]["max_discovery_depth"] == 2
        assert call_args[1]["limit"] == 100
        assert call_args[1]["include_paths"] == ["/docs/*"]

    @patch("ot_tools.firecrawl._get_client")
    def test_crawl_handles_response_object(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.id = "job456"
        mock_response.status = "started"
        mock_client.crawl.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = crawl(url="https://example.com")

        assert result["id"] == "job456"


# -----------------------------------------------------------------------------
# Crawl Status Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestCrawlStatus:
    """Test crawl_status function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_status_check(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_crawl_status.return_value = {
            "status": "completed",
            "completed": 10,
            "total": 10,
            "data": [{"url": "https://example.com/1"}],
        }
        mock_get_client.return_value = mock_client

        result = crawl_status(id="job123")

        assert result["status"] == "completed"

    @patch("ot_tools.firecrawl._get_client")
    def test_status_in_progress(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_crawl_status.return_value = {
            "status": "scraping",
            "completed": 5,
            "total": 10,
        }
        mock_get_client.return_value = mock_client

        result = crawl_status(id="job123")

        assert result["status"] == "scraping"


# -----------------------------------------------------------------------------
# Extract Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestExtract:
    """Test extract function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_extract_with_prompt(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "data": {"products": [{"name": "Widget", "price": 9.99}]}
        }
        mock_get_client.return_value = mock_client

        result = extract(
            urls=["https://example.com/products"],
            prompt="Extract product names and prices",
        )

        assert isinstance(result, dict)
        assert "data" in result

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_extract_with_schema(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.extract.return_value = {"data": {"name": "Test"}}
        mock_get_client.return_value = mock_client

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        extract(urls=["https://example.com"], schema=schema)

        call_args = mock_client.extract.call_args
        assert call_args[1]["schema"] == schema

    @patch("ot_tools.firecrawl._get_client")
    def test_extract_requires_prompt_or_schema(self, mock_get_client):
        mock_get_client.return_value = MagicMock()

        result = extract(urls=["https://example.com"])

        assert "Either prompt or schema is required" in result


# -----------------------------------------------------------------------------
# Deep Research Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.core
class TestDeepResearch:
    """Test deep_research function with mocked SDK."""

    @patch("ot_tools.firecrawl._get_client")
    def test_successful_research(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.agent.return_value = {
            "data": "Research findings about quantum computing...",
            "sources": ["https://source1.com", "https://source2.com"],
        }
        mock_get_client.return_value = mock_client

        result = deep_research(prompt="What are recent quantum computing advances?")

        assert isinstance(result, dict)

    @patch("ot_tools.firecrawl._get_client")
    def test_research_with_urls(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.agent.return_value = {"data": "findings"}
        mock_get_client.return_value = mock_client

        deep_research(
            prompt="Compare pricing",
            urls=["https://a.com/pricing", "https://b.com/pricing"],
        )

        call_args = mock_client.agent.call_args
        assert call_args[1]["urls"] == [
            "https://a.com/pricing",
            "https://b.com/pricing",
        ]

    @patch("ot_tools.firecrawl._get_client")
    def test_research_with_limits(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.agent.return_value = {"data": "findings"}
        mock_get_client.return_value = mock_client

        deep_research(prompt="test", max_depth=3, max_urls=20, time_limit=300)

        call_args = mock_client.agent.call_args
        assert call_args[1]["maxDepth"] == 3
        assert call_args[1]["maxUrls"] == 20
        assert call_args[1]["timeout"] == 300
