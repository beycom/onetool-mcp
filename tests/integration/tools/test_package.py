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

        assert "lodash" in result
        assert "unknown" not in result.lower()  # Got a real version

    def test_pypi_live(self):
        """Verify PyPI integration works."""
        from ot_tools.package import pypi

        result = pypi(packages=["requests"])

        assert "requests" in result
        assert "unknown" not in result.lower()  # Got a real version

    def test_openrouter_models_live(self):
        """Verify OpenRouter models API works."""
        from ot_tools.package import models

        result = models(query="claude", limit=3)

        assert "claude" in result.lower() or "[]" in result  # Either results or empty
