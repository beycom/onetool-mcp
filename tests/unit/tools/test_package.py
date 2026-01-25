"""Tests for package version tools.

Tests pure functions directly and main functions with HTTP mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from ot_tools.package import (
    _clean_version,
    _compare_versions,
    _fetch_model,
    _fetch_package,
    _format_created,
    _format_price,
    _parse_dependency_string,
    _parse_package_json,
    _parse_pyproject_toml,
    _parse_requirements_txt,
    _parse_version_constraint,
    audit,
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


# -----------------------------------------------------------------------------
# Manifest Parsing Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.serve
class TestParseDependencyString:
    """Test _parse_dependency_string PEP 508 parsing."""

    def test_simple_name(self):
        name, ver = _parse_dependency_string("requests")
        assert name == "requests"
        assert ver == ""

    def test_name_with_version(self):
        name, ver = _parse_dependency_string("requests>=2.28.0")
        assert name == "requests"
        assert ver == ">=2.28.0"

    def test_name_with_extras(self):
        name, ver = _parse_dependency_string("requests[security]>=2.28.0")
        assert name == "requests"
        assert ver == ">=2.28.0"

    def test_name_with_environment_marker(self):
        name, ver = _parse_dependency_string("requests>=2.28.0; python_version >= '3.8'")
        assert name == "requests"
        assert ver == ">=2.28.0"

    def test_normalizes_underscores(self):
        name, ver = _parse_dependency_string("some_package>=1.0.0")
        assert name == "some-package"

    def test_uppercase_normalized(self):
        name, ver = _parse_dependency_string("Requests>=1.0.0")
        assert name == "requests"


@pytest.mark.unit
@pytest.mark.serve
class TestParseVersionConstraint:
    """Test _parse_version_constraint extraction."""

    def test_gte_constraint(self):
        ver = _parse_version_constraint(">=2.28.0")
        assert ver == "2.28.0"

    def test_eq_constraint(self):
        ver = _parse_version_constraint("==1.0.0")
        assert ver == "1.0.0"

    def test_caret_constraint(self):
        ver = _parse_version_constraint("^18.0.0")
        assert ver == "18.0.0"

    def test_tilde_constraint(self):
        ver = _parse_version_constraint("~=3.0")
        assert ver == "3.0"

    def test_bare_version(self):
        ver = _parse_version_constraint("2.28.0")
        assert ver == "2.28.0"

    def test_full_dependency_string(self):
        ver = _parse_version_constraint("requests>=2.28.0")
        assert ver == "2.28.0"

    def test_no_version(self):
        ver = _parse_version_constraint("*")
        assert ver is None

    def test_empty_string(self):
        ver = _parse_version_constraint("")
        assert ver is None


@pytest.mark.unit
@pytest.mark.serve
class TestCompareVersions:
    """Test _compare_versions status classification."""

    def test_current_exact_match(self):
        status = _compare_versions("1.0.0", "1.0.0")
        assert status == "current"

    def test_current_with_prefix(self):
        status = _compare_versions("^1.0.0", "1.0.0")
        assert status == "current"

    def test_update_available_minor(self):
        status = _compare_versions("1.0.0", "1.1.0")
        assert status == "update_available"

    def test_update_available_patch(self):
        status = _compare_versions("1.0.0", "1.0.1")
        assert status == "update_available"

    def test_major_update(self):
        status = _compare_versions("1.0.0", "2.0.0")
        assert status == "major_update"

    def test_unknown_no_current(self):
        status = _compare_versions(None, "1.0.0")
        assert status == "unknown"

    def test_unknown_latest_unknown(self):
        status = _compare_versions("1.0.0", "unknown")
        assert status == "unknown"


@pytest.mark.unit
@pytest.mark.serve
class TestParsePyprojectToml:
    """Test _parse_pyproject_toml manifest parsing."""

    def test_parses_project_dependencies(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = [
    "requests>=2.28.0",
    "click>=8.0.0",
]
""")
        deps = _parse_pyproject_toml(pyproject)
        assert "requests" in deps
        assert "click" in deps
        assert deps["requests"] == ">=2.28.0"

    def test_parses_optional_dependencies(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "ruff>=0.1.0"]
""")
        deps = _parse_pyproject_toml(pyproject)
        assert "requests" in deps
        assert "pytest" in deps
        assert "ruff" in deps

    def test_parses_dependency_groups(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]

[dependency-groups]
test = ["pytest>=7.0.0"]
""")
        deps = _parse_pyproject_toml(pyproject)
        assert "requests" in deps
        assert "pytest" in deps

    def test_skips_include_group(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]

[dependency-groups]
all = [
    {include-group = "test"},
    "mypy>=1.0.0",
]
test = ["pytest>=7.0.0"]
""")
        deps = _parse_pyproject_toml(pyproject)
        assert "requests" in deps
        assert "mypy" in deps
        # include-group dicts are skipped
        assert "include-group" not in str(deps)


@pytest.mark.unit
@pytest.mark.serve
class TestParseRequirementsTxt:
    """Test _parse_requirements_txt manifest parsing."""

    def test_parses_simple(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("""
requests>=2.28.0
click>=8.0.0
""")
        deps = _parse_requirements_txt(req)
        assert "requests" in deps
        assert "click" in deps

    def test_skips_comments(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("""
# This is a comment
requests>=2.28.0
""")
        deps = _parse_requirements_txt(req)
        assert "requests" in deps
        assert len(deps) == 1

    def test_skips_options(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("""
-r base.txt
--index-url https://pypi.org/simple
requests>=2.28.0
""")
        deps = _parse_requirements_txt(req)
        assert "requests" in deps
        assert len(deps) == 1

    def test_skips_git_urls(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("""
requests>=2.28.0
git+https://github.com/user/repo.git
""")
        deps = _parse_requirements_txt(req)
        assert "requests" in deps
        assert len(deps) == 1


@pytest.mark.unit
@pytest.mark.serve
class TestParsePackageJson:
    """Test _parse_package_json manifest parsing."""

    def test_parses_dependencies(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text("""
{
    "dependencies": {
        "react": "^18.0.0",
        "lodash": "^4.17.0"
    }
}
""")
        deps = _parse_package_json(pkg)
        assert "react" in deps
        assert "lodash" in deps
        assert deps["react"] == "^18.0.0"

    def test_parses_dev_dependencies(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text("""
{
    "dependencies": {
        "react": "^18.0.0"
    },
    "devDependencies": {
        "typescript": "^5.0.0"
    }
}
""")
        deps = _parse_package_json(pkg)
        assert "react" in deps
        assert "typescript" in deps

    def test_empty_sections(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"name": "test"}')
        deps = _parse_package_json(pkg)
        assert deps == {}


# -----------------------------------------------------------------------------
# Audit Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.serve
class TestAudit:
    """Test audit function with mocked HTTP."""

    @patch("ot_tools.package._fetch")
    def test_auto_detect_pyproject(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (True, {"info": {"version": "2.31.0"}})

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["requests>=2.28.0"]
""")

        result = audit(path=str(tmp_path))

        assert "error" not in result
        assert result["registry"] == "pypi"
        assert "pyproject.toml" in result["manifest"]
        assert len(result["packages"]) == 1
        assert result["packages"][0]["name"] == "requests"
        assert result["packages"][0]["latest"] == "2.31.0"

    @patch("ot_tools.package._fetch")
    def test_auto_detect_package_json(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})

        pkg = tmp_path / "package.json"
        pkg.write_text('{"dependencies": {"react": "^18.0.0"}}')

        result = audit(path=str(tmp_path))

        assert "error" not in result
        assert result["registry"] == "npm"
        assert "package.json" in result["manifest"]
        assert len(result["packages"]) == 1
        assert result["packages"][0]["name"] == "react"

    @patch("ot_tools.package._fetch")
    def test_explicit_registry(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (True, {"dist-tags": {"latest": "18.2.0"}})

        # Create both manifests
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["requests>=2.28.0"]')

        pkg = tmp_path / "package.json"
        pkg.write_text('{"dependencies": {"react": "^18.0.0"}}')

        # Explicit npm should use package.json
        result = audit(path=str(tmp_path), registry="npm")

        assert result["registry"] == "npm"
        assert "package.json" in result["manifest"]

    def test_no_manifest_error(self, tmp_path):
        result = audit(path=str(tmp_path))

        assert "error" in result
        assert "No manifest found" in result["error"]

    def test_invalid_registry_error(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["requests>=2.28.0"]')

        result = audit(path=str(tmp_path), registry="invalid")

        assert "error" in result
        assert "Invalid registry" in result["error"]

    @patch("ot_tools.package._fetch")
    def test_status_classification(self, mock_fetch, tmp_path):
        # Simulate different version scenarios
        def mock_version(url, **kwargs):
            if "requests" in url:
                return (True, {"info": {"version": "2.28.0"}})  # current
            elif "flask" in url:
                return (True, {"info": {"version": "2.1.0"}})  # minor update
            elif "django" in url:
                return (True, {"info": {"version": "5.0.0"}})  # major update
            return (False, "Not found")

        mock_fetch.side_effect = mock_version

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = [
    "requests>=2.28.0",
    "flask>=2.0.0",
    "django>=4.0.0",
]
""")

        result = audit(path=str(tmp_path))

        assert "error" not in result

        # Find each package and check status
        packages_by_name = {p["name"]: p for p in result["packages"]}

        assert packages_by_name["requests"]["status"] == "current"
        assert packages_by_name["flask"]["status"] == "update_available"
        assert packages_by_name["django"]["status"] == "major_update"

        # Check summary
        assert result["summary"]["current"] == 1
        assert result["summary"]["update_available"] == 1
        assert result["summary"]["major_update"] == 1

    @patch("ot_tools.package._fetch")
    def test_requirements_txt_support(self, mock_fetch, tmp_path):
        mock_fetch.return_value = (True, {"info": {"version": "2.31.0"}})

        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.28.0\nclick>=8.0.0")

        result = audit(path=str(tmp_path))

        assert "error" not in result
        assert result["registry"] == "pypi"
        assert "requirements.txt" in result["manifest"]
        assert len(result["packages"]) == 2
