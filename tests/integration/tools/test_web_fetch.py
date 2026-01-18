"""Live integration tests for web fetch tool.

Requires trafilatura to be installed.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestWebFetchLive:
    """Live integration tests for web fetch tool."""

    @pytest.fixture(autouse=True)
    def skip_if_trafilatura_missing(self):
        """Skip tests if trafilatura is not available."""
        pytest.importorskip("trafilatura")

    def test_fetch_live(self):
        """Verify web fetch works with a real URL."""
        from ot_tools.web_fetch import fetch

        # Use GitHub's about page - an HTML page that trafilatura can parse
        result = fetch(
            url="https://github.com/about",
            output_format="text",
            timeout=15.0,
            use_cache=False,
        )

        # Skip if network error (DNS resolution, connection refused, etc.)
        if "Error" in result and (
            "Failed to fetch" in result or "resolve" in result.lower()
        ):
            pytest.skip("Network not available")

        # GitHub about page should have some content about GitHub
        assert "GitHub" in result or "github" in result.lower() or len(result) > 100
