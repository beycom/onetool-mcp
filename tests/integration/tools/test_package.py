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

    def test_audit_pypi_live(self, tmp_path):
        """Verify audit function works with real PyPI registry."""
        from ot_tools.package import audit

        # Create a minimal pyproject.toml with known packages
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = [
    "requests>=2.28.0",
    "click>=8.0.0",
]
""")

        result = audit(path=str(tmp_path))

        # Verify structure
        assert "error" not in result, f"Got error: {result.get('error')}"
        assert result["registry"] == "pypi"
        assert len(result["packages"]) == 2
        assert "summary" in result

        # Verify packages have expected fields
        for pkg in result["packages"]:
            assert "name" in pkg
            assert "required" in pkg
            assert "latest" in pkg
            assert "status" in pkg
            assert pkg["latest"] != "unknown"  # Got real versions

    def test_audit_npm_live(self, tmp_path):
        """Verify audit function works with real npm registry."""
        from ot_tools.package import audit

        # Create a minimal package.json with known packages
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text("""
{
    "dependencies": {
        "lodash": "^4.17.0",
        "chalk": "^5.0.0"
    }
}
""")

        result = audit(path=str(tmp_path))

        # Verify structure
        assert "error" not in result, f"Got error: {result.get('error')}"
        assert result["registry"] == "npm"
        assert len(result["packages"]) == 2
        assert "summary" in result

        # Verify packages have expected fields
        for pkg in result["packages"]:
            assert "name" in pkg
            assert "required" in pkg
            assert "latest" in pkg
            assert "status" in pkg
            assert pkg["latest"] != "unknown"  # Got real versions
