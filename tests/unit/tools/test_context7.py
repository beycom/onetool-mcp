"""Tests for Context7 API tools.

Tests normalization functions and main functions with HTTP mocks.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Try to import the module - skip all tests if it fails due to missing config
try:
    from ot_tools.context7 import (
        _normalize_library_key,
        _normalize_topic,
        _pick_best_library,
        doc,
        search,
    )
except (ImportError, TypeError) as e:
    pytestmark = pytest.mark.skip(reason=f"context7 module import failed: {e}")


# -----------------------------------------------------------------------------
# Pure Function Tests (No Mocking Required)
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestNormalizeLibraryKey:
    """Test _normalize_library_key path parsing function."""

    def test_strips_leading_slash(self):
        assert _normalize_library_key("/vercel/next.js") == "vercel/next.js"

    def test_strips_version_suffix(self):
        assert _normalize_library_key("/vercel/next.js/v16.0.3") == "vercel/next.js"

    def test_handles_no_leading_slash(self):
        assert _normalize_library_key("vercel/next.js") == "vercel/next.js"

    def test_extracts_from_github_url(self):
        result = _normalize_library_key("https://github.com/vercel/next.js")
        assert result == "vercel/next.js"

    def test_extracts_from_github_url_with_path(self):
        result = _normalize_library_key("https://github.com/vercel/next.js/tree/main")
        assert result == "vercel/next.js"

    def test_extracts_from_context7_url(self):
        result = _normalize_library_key("https://context7.com/vercel/next.js")
        assert result == "vercel/next.js"

    def test_strips_quotes(self):
        assert _normalize_library_key('"vercel/next.js"') == "vercel/next.js"
        assert _normalize_library_key("'vercel/next.js'") == "vercel/next.js"

    def test_fixes_double_slashes(self):
        assert _normalize_library_key("vercel//next.js") == "vercel/next.js"

    def test_strips_trailing_slash(self):
        assert _normalize_library_key("vercel/next.js/") == "vercel/next.js"

    def test_handles_simple_name(self):
        # Single name without slash should pass through
        assert _normalize_library_key("next.js") == "next.js"

    def test_version_pattern_v_prefix(self):
        result = _normalize_library_key("vercel/next.js/v14")
        assert result == "vercel/next.js"

    def test_version_pattern_numeric(self):
        result = _normalize_library_key("vercel/next.js/14.0.0")
        assert result == "vercel/next.js"


@pytest.mark.unit
@pytest.mark.tools
class TestNormalizeTopic:
    """Test _normalize_topic cleaning function."""

    def test_strips_whitespace(self):
        assert _normalize_topic("  routing  ") == "routing"

    def test_strips_quotes(self):
        assert _normalize_topic('"PPR"') == "PPR"
        assert _normalize_topic("'hooks'") == "hooks"

    def test_removes_escaped_quotes(self):
        # Escaped quotes within a string (not at boundaries) are removed
        assert _normalize_topic('foo\\"bar') == "foobar"
        assert _normalize_topic("foo\\'bar") == "foobar"

    def test_removes_placeholder_markers(self):
        assert _normalize_topic("<relevant topic>") == ""

    def test_handles_placeholder_text(self):
        assert _normalize_topic("relevant topic") == ""
        assert _normalize_topic("topic") == ""
        assert _normalize_topic("extract from question") == ""

    def test_converts_path_to_search_term(self):
        result = _normalize_topic("app/partial-pre-rendering/index")
        # Should extract the most specific part and convert kebab-case
        assert "partial pre rendering" in result

    def test_converts_kebab_case(self):
        assert _normalize_topic("server-side-rendering") == "server side rendering"

    def test_converts_snake_case(self):
        assert _normalize_topic("server_side_rendering") == "server side rendering"

    def test_normalizes_whitespace(self):
        assert _normalize_topic("multiple   spaces") == "multiple spaces"

    def test_empty_string(self):
        assert _normalize_topic("") == ""


@pytest.mark.unit
@pytest.mark.tools
class TestPickBestLibrary:
    """Test _pick_best_library scoring function."""

    def test_returns_none_for_empty_results(self):
        assert _pick_best_library([], "react") is None
        assert _pick_best_library({"results": []}, "react") is None

    def test_returns_none_for_invalid_data(self):
        assert _pick_best_library("invalid", "react") is None
        assert _pick_best_library(None, "react") is None

    def test_prefers_exact_title_match(self):
        """Exact title match should win over VIP/verified."""
        data = [
            {"id": "/reactjs/react-window", "title": "React Window", "vip": True},
            {"id": "/reactjs/react.dev", "title": "React", "verified": True},
        ]
        assert _pick_best_library(data, "react") == "reactjs/react.dev"

    def test_prefers_vip_over_verified(self):
        """VIP libraries should rank higher than just verified."""
        data = [
            {"id": "/org/lib-a", "title": "Other", "verified": True},
            {"id": "/org/lib-b", "title": "Other2", "vip": True},
        ]
        assert _pick_best_library(data, "something") == "org/lib-b"

    def test_trust_score_contributes(self):
        """Higher trust scores should rank higher."""
        data = [
            {"id": "/org/lib-a", "title": "Lib", "trustScore": 5},
            {"id": "/org/lib-b", "title": "Lib", "trustScore": 10},
        ]
        assert _pick_best_library(data, "lib") == "org/lib-b"

    def test_handles_results_wrapper(self):
        """Should handle {"results": [...]} format."""
        data = {"results": [{"id": "/vercel/next.js", "title": "Next.js"}]}
        assert _pick_best_library(data, "next.js") == "vercel/next.js"

    def test_strips_leading_slash(self):
        """Should strip leading slash from id."""
        data = [{"id": "/facebook/react", "title": "React"}]
        assert _pick_best_library(data, "react") == "facebook/react"

    def test_returns_none_for_id_without_slash(self):
        """Should return None if id doesn't have org/repo format."""
        data = [{"id": "react", "title": "React"}]
        assert _pick_best_library(data, "react") is None

    def test_react_scenario(self):
        """React search should pick reactjs/react.dev over react-window."""
        data = [
            {
                "id": "/reactjs/react-window",
                "title": "react-window",
                "vip": False,
                "verified": False,
                "trustScore": 5,
            },
            {
                "id": "/reactjs/react.dev",
                "title": "React",
                "vip": True,
                "verified": True,
                "trustScore": 10,
            },
        ]
        assert _pick_best_library(data, "react") == "reactjs/react.dev"

    def test_nextjs_scenario(self):
        """Next.js search should pick vercel/next.js."""
        data = [
            {"id": "/vercel/next.js", "title": "Next.js", "vip": True, "trustScore": 10},
            {"id": "/other/nextjs-clone", "title": "nextjs-clone", "trustScore": 3},
        ]
        assert _pick_best_library(data, "next.js") == "vercel/next.js"

    def test_fastapi_scenario(self):
        """FastAPI search should pick fastapi/fastapi."""
        data = [
            {"id": "/fastapi/fastapi", "title": "FastAPI", "verified": True, "trustScore": 9},
            {"id": "/other/fastapi-utils", "title": "fastapi-utils", "trustScore": 4},
        ]
        assert _pick_best_library(data, "fastapi") == "fastapi/fastapi"


# -----------------------------------------------------------------------------
# HTTP Mock Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked HTTP."""

    @patch("ot_tools.context7._make_request")
    def test_successful_search(self, mock_request):
        mock_request.return_value = (
            True,
            [
                {"id": "/vercel/next.js", "name": "Next.js"},
                {"id": "/facebook/react", "name": "React"},
            ],
        )

        result = search(query="nextjs")

        assert "next.js" in result.lower()
        mock_request.assert_called_once()

    @patch("ot_tools.context7._make_request")
    def test_returns_error_on_failure(self, mock_request):
        mock_request.return_value = (False, "[Context7 API key not configured]")

        result = search(query="test")

        assert "Context7" in result

    @patch("ot_tools.context7._make_request")
    def test_passes_query_param(self, mock_request):
        mock_request.return_value = (True, [])

        search(query="fastapi")

        call_args = mock_request.call_args
        assert call_args[1]["params"]["query"] == "fastapi"


@pytest.mark.unit
@pytest.mark.tools
class TestDoc:
    """Test doc function with mocked HTTP."""

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_successful_doc_fetch(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "# Documentation\n\nThis is the docs.")

        result = doc(library_key="next.js")

        assert "Documentation" in result

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_returns_error_on_failure(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (False, "API error")

        result = doc(library_key="next.js")

        assert "API error" in result

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_handles_no_content(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "No content available")

        result = doc(library_key="next.js")

        assert "No info documentation available" in result

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_info_mode_uses_info_endpoint(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "docs content")

        doc(library_key="next.js", mode="info")

        call_args = mock_request.call_args
        assert "info" in call_args[0][0]

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_code_mode_uses_code_endpoint(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "code examples")

        doc(library_key="next.js", mode="code")

        call_args = mock_request.call_args
        assert "code" in call_args[0][0]

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_normalizes_topic(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "docs")

        doc(library_key="next.js", topic="server-side-rendering")

        call_args = mock_request.call_args
        # Topic should be normalized (kebab-case to spaces)
        params = call_args[1]["params"]
        if "topic" in params:
            assert "server side rendering" in params["topic"]

    @patch("ot_tools.context7._make_request")
    @patch("ot_tools.context7._resolve_library_key")
    def test_clamps_page_and_limit(self, mock_resolve, mock_request):
        mock_resolve.return_value = "vercel/next.js"
        mock_request.return_value = (True, "docs")

        doc(library_key="next.js", page=100, limit=1000)

        call_args = mock_request.call_args
        params = call_args[1]["params"]
        assert params["page"] <= 10  # Max page is 10


@pytest.mark.unit
@pytest.mark.tools
class TestResolveLibraryKey:
    """Test _resolve_library_key function."""

    @patch("ot_tools.context7._make_request")
    def test_returns_valid_org_repo_directly(self, mock_request):
        from ot_tools.context7 import _resolve_library_key

        # Should not make a request for valid org/repo
        result = _resolve_library_key("vercel/next.js")

        assert result == "vercel/next.js"
        mock_request.assert_not_called()

    @patch("ot_tools.context7._make_request")
    def test_searches_for_simple_name(self, mock_request):
        from ot_tools.context7 import _resolve_library_key

        mock_request.return_value = (
            True,
            [{"id": "/fastapi/fastapi", "name": "FastAPI"}],
        )

        result = _resolve_library_key("fastapi")

        assert result == "fastapi/fastapi"
        mock_request.assert_called_once()

    @patch("ot_tools.context7._make_request")
    def test_returns_original_on_search_failure(self, mock_request):
        from ot_tools.context7 import _resolve_library_key

        mock_request.return_value = (False, "API error")

        result = _resolve_library_key("unknown")

        assert result == "unknown"


# -----------------------------------------------------------------------------
# API Key Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestMakeRequest:
    """Test _make_request function."""

    @patch("ot_tools.context7._get_api_key")
    def test_returns_error_without_api_key(self, mock_key):
        from ot_tools.context7 import _make_request

        mock_key.return_value = ""

        success, result = _make_request("https://context7.com/api/test")

        assert success is False
        assert "Context7 API key not configured" in result
