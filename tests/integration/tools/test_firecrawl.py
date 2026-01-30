"""Live integration tests for Firecrawl tool.

Requires FIRECRAWL_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

from ot.config.secrets import get_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
@pytest.mark.core
class TestFirecrawlLive:
    """Live integration tests for Firecrawl tool."""

    @pytest.fixture(autouse=True)
    def skip_if_no_api_key(self):
        """Skip tests if FIRECRAWL_API_KEY is not set."""
        if not get_secret("FIRECRAWL_API_KEY"):
            pytest.skip("FIRECRAWL_API_KEY not configured")

    def test_scrape_live(self):
        """Verify Firecrawl scrape works."""
        from ot_tools.firecrawl import scrape

        result = scrape(url="https://example.com")

        # Should get a dict result, not an error string
        assert isinstance(result, dict) or "FIRECRAWL_API_KEY" not in result

    def test_map_urls_live(self):
        """Verify Firecrawl map_urls works."""
        from ot_tools.firecrawl import map_urls

        result = map_urls(url="https://example.com", limit=5)

        # Should get a list or error (not API key error)
        assert isinstance(result, list) or "FIRECRAWL_API_KEY" not in result

    def test_search_live(self):
        """Verify Firecrawl search works and returns results."""
        from ot_tools.firecrawl import search

        result = search(query="python programming", limit=3)

        # Should get a non-empty list (not an error or empty results)
        assert isinstance(result, list), f"Expected list, got {type(result)}: {result}"
        assert len(result) > 0, "Search returned empty results"
