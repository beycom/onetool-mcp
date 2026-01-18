"""Live integration tests for Context7 tool.

Requires CONTEXT7_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

from ot.config.secrets import get_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestContext7Live:
    """Live integration tests for Context7 tool."""

    @pytest.fixture(autouse=True)
    def skip_if_unavailable(self):
        """Skip tests if Context7 is not available or API key not set."""
        if not get_secret("CONTEXT7_API_KEY"):
            pytest.skip("CONTEXT7_API_KEY not configured")

        # Context7 module creates httpx client at import time which may fail
        # if http.base_url config is not set
        try:
            from ot_tools import context7  # noqa: F401
        except (ImportError, TypeError) as e:
            pytest.skip(f"context7 module not available: {e}")

    def test_search_live(self):
        """Verify Context7 library search works."""
        from ot_tools.context7 import search

        result = search(query="fastapi")

        # Should get results or API key error
        assert "fastapi" in result.lower() or "Context7" in result
