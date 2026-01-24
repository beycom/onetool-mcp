"""Tests for package version tools.

Tests pure functions directly and main functions with HTTP mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from ot_tools.package import (
    _clean_version,
    _fetch_model,
    _fetch_package,
    _format_created,
    _format_price,
    models,
    npm,
    pypi,
    version,
)

# -----------------------------------------------------------------------------
# Pure Function Tests (No Mocking Required)
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.serve
class TestCleanVersion:
    """Test _clean_version semver prefix stripping."""

    def test_strips_caret(self):
        assert _clean_version("^1.0.0") == "1.0.0"

    def test_strips_tilde(self):
        assert _clean_version("~1.0.0") == "1.0.0"

    def test_strips_gte(self):
        assert _clean_version(">=1.0.0") == "1.0.0"

    def test_strips_lte(self):
        assert _clean_version("<=1.0.0") == "1.0.0"

    def test_strips_gt(self):
        assert _clean_version(">1.0.0") == "1.0.0"

    def test_strips_lt(self):
        assert _clean_version("<1.0.0") == "1.0.0"

    def test_no_prefix_unchanged(self):
        assert _clean_version("1.0.0") == "1.0.0"

    def test_complex_version(self):
        assert _clean_version("^18.2.0-rc.1") == "18.2.0-rc.1"

    def test_multiple_prefixes(self):
        assert _clean_version(">=1.0.0") == "1.0.0"


@pytest.mark.unit
@pytest.mark.serve
class TestFormatPrice:
    """Test _format_price conversion to $/MTok."""

    def test_formats_normal_price(self):
        # $0.000001 per token = $1.00/MTok
        result = _format_price(0.000001)
        assert result == "$1.00/MTok"

    def test_formats_small_price(self):
        # $0.0000001 per token = $0.10/MTok
        result = _format_price(0.0000001)
        assert result == "$0.10/MTok"

    def test_formats_very_small_price(self):
        # $0.00000001 per token = $0.01/MTok
        result = _format_price(0.00000001)
        assert result == "$0.01/MTok"

    def test_formats_tiny_price(self):
        # Price that results in less than $0.01/MTok
        result = _format_price(0.000000001)
        assert result == "$0.0010/MTok"

    def test_none_returns_na(self):
        assert _format_price(None) == "N/A"

    def test_string_number(self):
        result = _format_price("0.000001")
        assert result == "$1.00/MTok"

    def test_invalid_string_returns_na(self):
        assert _format_price("invalid") == "N/A"


@pytest.mark.unit
@pytest.mark.serve
class TestFormatCreated:
    """Test _format_created timestamp formatting."""

    def test_formats_timestamp(self):
        # January 15, 2024 00:00:00 UTC
        timestamp = int(datetime(2024, 1, 15, tzinfo=UTC).timestamp())
        result = _format_created(timestamp)
        assert result == "20240115"

    def test_none_returns_unknown(self):
        assert _format_created(None) == "unknown"

    def test_zero_returns_unknown(self):
        assert _format_created(0) == "unknown"


# -----------------------------------------------------------------------------
# HTTP Mock Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.serve
class TestNpm:
    """Test npm function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_fetches_single_package(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})

        result = npm(packages=["react"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "react"
        assert result[0]["latest"] == "18.2.0"

    @patch("ot_tools.package._fetch")
    def test_handles_unknown_package(self, mock_fetch):
        mock_fetch.return_value = (False, "Not found")

        result = npm(packages=["nonexistent-package-xyz"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert result[0]["latest"] == "unknown"

    @patch("ot_tools.package._fetch")
    def test_fetches_multiple_packages(self, mock_fetch):
        mock_fetch.side_effect = [
            (True, {"dist-tags": {"latest": "18.2.0"}}),
            (True, {"dist-tags": {"latest": "4.17.21"}}),
        ]

        result = npm(packages=["react", "lodash"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        names = [r["name"] for r in result]
        assert "react" in names
        assert "lodash" in names


@pytest.mark.unit
@pytest.mark.serve
class TestPypi:
    """Test pypi function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_fetches_single_package(self, mock_fetch):
        mock_fetch.return_value = (True, {"info": {"version": "2.31.0"}})

        result = pypi(packages=["requests"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "requests"
        assert result[0]["latest"] == "2.31.0"

    @patch("ot_tools.package._fetch")
    def test_handles_unknown_package(self, mock_fetch):
        mock_fetch.return_value = (False, "Not found")

        result = pypi(packages=["nonexistent-package-xyz"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert result[0]["latest"] == "unknown"


@pytest.mark.unit
@pytest.mark.serve
class TestModels:
    """Test models function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_searches_by_query(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            {
                "data": [
                    {
                        "id": "anthropic/claude-3-opus",
                        "name": "Claude 3 Opus",
                        "context_length": 200000,
                        "pricing": {"prompt": "0.000015", "completion": "0.000075"},
                        "architecture": {"modality": "text->text"},
                    }
                ]
            },
        )

        result = models(query="claude")

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert "claude" in result[0]["id"].lower()
        assert "anthropic" in result[0]["id"].lower()

    @patch("ot_tools.package._fetch")
    def test_filters_by_provider(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            {
                "data": [
                    {
                        "id": "anthropic/claude-3-opus",
                        "name": "Claude 3 Opus",
                        "context_length": 200000,
                        "pricing": {},
                        "architecture": {},
                    },
                    {
                        "id": "openai/gpt-4",
                        "name": "GPT-4",
                        "context_length": 8192,
                        "pricing": {},
                        "architecture": {},
                    },
                ]
            },
        )

        result = models(provider="anthropic")

        # Should only include anthropic models
        assert isinstance(result, list)
        assert len(result) == 1
        assert "anthropic" in result[0]["id"].lower()

    @patch("ot_tools.package._fetch")
    def test_returns_empty_on_failure(self, mock_fetch):
        mock_fetch.return_value = (False, "API error")

        result = models(query="test")

        # Result is now an empty list
        assert result == []

    @patch("ot_tools.package._fetch")
    def test_limits_results(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            {
                "data": [
                    {
                        "id": f"model/{i}",
                        "name": f"Model {i}",
                        "pricing": {},
                        "architecture": {},
                    }
                    for i in range(50)
                ]
            },
        )

        result = models(limit=5)

        # Result is now a list, check length
        assert isinstance(result, list)
        assert len(result) <= 5


@pytest.mark.unit
@pytest.mark.serve
class TestVersion:
    """Test version function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_npm_with_current_versions(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})

        result = version(registry="npm", packages={"react": "^18.0.0"})

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "react"
        assert result[0]["current"] == "18.0.0"  # current (stripped of ^)
        assert result[0]["latest"] == "18.2.0"  # latest

    @patch("ot_tools.package._fetch")
    def test_pypi_with_list(self, mock_fetch):
        mock_fetch.return_value = (True, {"info": {"version": "2.31.0"}})

        result = version(registry="pypi", packages=["requests"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "requests"
        assert result[0]["latest"] == "2.31.0"

    @patch("ot_tools.package._fetch")
    def test_openrouter_with_wildcard(self, mock_fetch):
        mock_fetch.return_value = (
            True,
            {
                "data": [
                    {
                        "id": "openai/gpt-4-turbo",
                        "name": "GPT-4 Turbo",
                        "created": 1700000000,
                        "context_length": 128000,
                        "pricing": {"prompt": "0.00001", "completion": "0.00003"},
                    },
                ]
            },
        )

        result = version(registry="openrouter", packages=["openai/gpt-4*"])

        # Result is now a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert "openai" in result[0]["id"].lower()
        assert "gpt-4" in result[0]["id"].lower()

    def test_unknown_registry(self):
        result = version(registry="invalid", packages=["test"])

        # This returns a string error message
        assert "Unknown registry" in result


@pytest.mark.unit
@pytest.mark.serve
class TestFetchPackage:
    """Test _fetch_package helper."""

    @patch("ot_tools.package._fetch")
    def test_npm_fetch(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "1.0.0"}})

        result = _fetch_package("npm", "test-pkg")

        assert result["name"] == "test-pkg"
        assert result["registry"] == "npm"
        assert result["latest"] == "1.0.0"

    @patch("ot_tools.package._fetch")
    def test_pypi_fetch(self, mock_fetch):
        mock_fetch.return_value = (True, {"info": {"version": "1.0.0"}})

        result = _fetch_package("pypi", "test-pkg")

        assert result["name"] == "test-pkg"
        assert result["registry"] == "pypi"
        assert result["latest"] == "1.0.0"

    @patch("ot_tools.package._fetch")
    def test_includes_current_version(self, mock_fetch):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "1.0.0"}})

        result = _fetch_package("npm", "test-pkg", current="^0.9.0")

        assert result["current"] == "0.9.0"


@pytest.mark.unit
@pytest.mark.serve
class TestFetchModel:
    """Test _fetch_model helper."""

    def test_exact_match(self):
        models_data = [
            {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "pricing": {}},
        ]

        result = _fetch_model("claude-3-opus", models_data)

        assert result is not None
        assert result["id"] == "anthropic/claude-3-opus"

    def test_wildcard_match(self):
        models_data = [
            {"id": "openai/gpt-4-turbo-2024-01", "name": "GPT-4 Turbo", "pricing": {}},
            {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5", "pricing": {}},
        ]

        result = _fetch_model("openai/gpt-4*", models_data)

        assert result is not None
        assert "gpt-4" in result["id"]

    def test_no_match(self):
        models_data = [
            {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "pricing": {}},
        ]

        result = _fetch_model("nonexistent", models_data)

        assert result["id"] == "unknown"
