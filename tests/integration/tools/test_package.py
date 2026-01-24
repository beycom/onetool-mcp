"""Live integration tests for package version tool.

Tests npm, PyPI, and OpenRouter models API endpoints.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestPackageLive:
    """Live integration tests for package version tool."""

    def test_npm_live(self):
        """Verify npm registry integration works."""
        from ot_tools.package import npm

        result = npm(packages=["lodash"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "lodash"
        assert result[0]["latest"] != "unknown"  # Got a real version

    def test_pypi_live(self):
        """Verify PyPI integration works."""
        from ot_tools.package import pypi

        result = pypi(packages=["requests"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "requests"
        assert result[0]["latest"] != "unknown"  # Got a real version

    def test_openrouter_models_live(self):
        """Verify OpenRouter models API works."""
        from ot_tools.package import models

        result = models(query="claude", limit=3)

        # Result is now a list of dicts (or empty list if API unavailable)
        assert isinstance(result, list)
        if len(result) > 0:
            # Check that we got claude models
            assert any("claude" in m.get("id", "").lower() for m in result)
