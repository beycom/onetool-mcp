"""Live integration tests for grounding search tool.

Requires GEMINI_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

from ot.config.secrets import get_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestGroundingSearchLive:
    """Live integration tests for grounding search tool."""

    @pytest.fixture(autouse=True)
    def skip_if_no_api_key(self):
        """Skip tests if GEMINI_API_KEY is not set."""
        if not get_secret("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not configured")

    def test_search_live(self):
        """Verify grounding search works."""
        from ot_tools.grounding_search import search

        result = search(query="what is python programming language")

        # Should get results or an error about the API key
        assert len(result) > 0
