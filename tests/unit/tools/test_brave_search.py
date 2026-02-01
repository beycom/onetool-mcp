"""Tests for Brave Search API tools.

Tests pure functions (validators, formatters) and main functions with HTTP mocks.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ot_tools.brave_search import (
    _clamp,
    _format_image_results,
    _format_local_results_from_web,
    _format_news_results,
    _format_video_results,
    _format_web_results,
    _validate_query,
    image,
    local,
    news,
    search,
    search_batch,
    video,
)

# -----------------------------------------------------------------------------
# Pure Function Tests (No Mocking Required)
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestClamp:
    """Test _clamp value clamping function."""

    def test_value_within_range(self):
        assert _clamp(5, 1, 10) == 5

    def test_value_below_min(self):
        assert _clamp(-5, 1, 10) == 1

    def test_value_above_max(self):
        assert _clamp(15, 1, 10) == 10

    def test_value_equals_min(self):
        assert _clamp(1, 1, 10) == 1

    def test_value_equals_max(self):
        assert _clamp(10, 1, 10) == 10


@pytest.mark.unit
@pytest.mark.tools
class TestValidateQuery:
    """Test _validate_query validation function."""

    def test_valid_query(self):
        assert _validate_query("python best practices") is None

    def test_query_too_long(self):
        long_query = "x" * 401
        result = _validate_query(long_query)
        assert result is not None
        assert "400 character" in result

    def test_query_at_limit(self):
        query = "x" * 400
        assert _validate_query(query) is None

    def test_too_many_words(self):
        many_words = " ".join(["word"] * 51)
        result = _validate_query(many_words)
        assert result is not None
        assert "50 word" in result

    def test_words_at_limit(self):
        fifty_words = " ".join(["word"] * 50)
        assert _validate_query(fifty_words) is None

    def test_empty_query(self):
        result = _validate_query("")
        assert result is not None
        assert "empty" in result.lower()

    def test_whitespace_only_query(self):
        result = _validate_query("   ")
        assert result is not None
        assert "empty" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
class TestFormatWebResults:
    """Test _format_web_results formatting function."""

    def test_formats_results(self):
        data = {
            "web": {
                "results": [
                    {
                        "title": "Python Tutorial",
                        "url": "https://example.com/python",
                        "description": "Learn Python",
                    }
                ]
            }
        }

        result = _format_web_results(data)

        assert "Python Tutorial" in result
        assert "https://example.com/python" in result
        assert "Learn Python" in result

    def test_handles_empty_results(self):
        data = {"web": {"results": []}}

        result = _format_web_results(data)

        assert "No results found" in result

    def test_handles_missing_web_key(self):
        data = {}

        result = _format_web_results(data)

        assert "No results found" in result

    def test_numbers_results(self):
        data = {
            "web": {
                "results": [
                    {"title": "First", "url": "https://1.com", "description": ""},
                    {"title": "Second", "url": "https://2.com", "description": ""},
                ]
            }
        }

        result = _format_web_results(data)

        assert "1. First" in result
        assert "2. Second" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFormatNewsResults:
    """Test _format_news_results formatting function."""

    def test_formats_results(self):
        data = {
            "results": [
                {
                    "title": "Breaking News",
                    "url": "https://news.com/story",
                    "meta_url": {"hostname": "news.com"},
                    "age": "2 hours ago",
                    "breaking": False,
                }
            ]
        }

        result = _format_news_results(data)

        assert "Breaking News" in result
        assert "news.com" in result
        assert "2 hours ago" in result

    def test_marks_breaking_news(self):
        data = {
            "results": [
                {
                    "title": "Important Story",
                    "url": "https://news.com",
                    "breaking": True,
                }
            ]
        }

        result = _format_news_results(data)

        assert "[BREAKING]" in result

    def test_handles_empty_results(self):
        data = {"results": []}

        result = _format_news_results(data)

        assert "No news results found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFormatLocalResults:
    """Test _format_local_results_from_web formatting function."""

    def test_formats_location_results(self):
        data = {
            "locations": {
                "results": [
                    {
                        "title": "Coffee Shop",
                        "address": {
                            "streetAddress": "123 Main St",
                            "addressLocality": "City",
                            "addressRegion": "State",
                        },
                        "rating": {"ratingValue": "4.5", "ratingCount": "100"},
                        "phone": "555-1234",
                    }
                ]
            }
        }

        result = _format_local_results_from_web(data)

        assert "Coffee Shop" in result
        assert "123 Main St" in result
        assert "4.5" in result
        assert "555-1234" in result

    def test_falls_back_to_web_results_with_warning(self):
        data = {
            "locations": {"results": []},
            "web": {
                "results": [
                    {
                        "title": "Web Result",
                        "url": "https://example.com",
                        "description": "",
                    }
                ]
            },
        }

        result = _format_local_results_from_web(data)

        assert "No local business data found" in result
        assert "Web Result" in result

    def test_falls_back_no_warning_when_no_results(self):
        data = {
            "locations": {"results": []},
            "web": {"results": []},
        }

        result = _format_local_results_from_web(data)

        assert result == "No results found."


@pytest.mark.unit
@pytest.mark.tools
class TestFormatImageResults:
    """Test _format_image_results formatting function."""

    def test_formats_results(self):
        data = {
            "results": [
                {
                    "title": "Python Logo",
                    "url": "https://example.com/python.png",
                    "source": "example.com",
                    "properties": {"width": 800, "height": 600},
                }
            ]
        }

        result = _format_image_results(data)

        assert "Python Logo" in result
        assert "800x600" in result
        assert "example.com" in result

    def test_handles_empty_results(self):
        data = {"results": []}

        result = _format_image_results(data)

        assert "No image results found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFormatVideoResults:
    """Test _format_video_results formatting function."""

    def test_formats_results(self):
        data = {
            "results": [
                {
                    "title": "Python Tutorial",
                    "url": "https://youtube.com/watch",
                    "description": "Learn Python basics",
                    "meta_url": {"hostname": "youtube.com"},
                    "video": {"duration": "10:30", "views": "1M"},
                }
            ]
        }

        result = _format_video_results(data)

        assert "Python Tutorial" in result
        assert "youtube.com" in result
        assert "10:30" in result
        assert "1M" in result

    def test_truncates_long_description(self):
        long_desc = "x" * 200
        data = {
            "results": [
                {
                    "title": "Video",
                    "url": "https://example.com",
                    "description": long_desc,
                }
            ]
        }

        result = _format_video_results(data)

        # Should be truncated with "..."
        assert "..." in result

    def test_handles_empty_results(self):
        data = {"results": []}

        result = _format_video_results(data)

        assert "No video results found" in result


# -----------------------------------------------------------------------------
# HTTP Mock Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test search function with mocked HTTP."""

    @patch("ot_tools.brave_search._make_request")
    def test_successful_search(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "web": {
                    "results": [
                        {
                            "title": "Result",
                            "url": "https://example.com",
                            "description": "Description",
                        }
                    ]
                }
            },
        )

        result = search(query="test query")

        assert "Result" in result
        mock_request.assert_called_once()

    @patch("ot_tools.brave_search._make_request")
    def test_returns_error_on_failure(self, mock_request):
        mock_request.return_value = (False, "API error")

        result = search(query="test")

        assert "API error" in result

    def test_validates_query_length(self):
        long_query = "x" * 401

        result = search(query=long_query)

        assert "400 character" in result

    @patch("ot_tools.brave_search._make_request")
    def test_clamps_count(self, mock_request):
        mock_request.return_value = (True, {"web": {"results": []}})

        search(query="test", count=100)  # Above max of 20

        call_args = mock_request.call_args
        assert call_args[0][1]["count"] == 20

    @patch("ot_tools.brave_search._make_request")
    def test_includes_freshness(self, mock_request):
        mock_request.return_value = (True, {"web": {"results": []}})

        search(query="test", freshness="pw")

        call_args = mock_request.call_args
        assert call_args[0][1]["freshness"] == "pw"


@pytest.mark.unit
@pytest.mark.tools
class TestNews:
    """Test news function with mocked HTTP."""

    @patch("ot_tools.brave_search._make_request")
    def test_successful_news_search(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "results": [
                    {
                        "title": "News Story",
                        "url": "https://news.com",
                        "breaking": False,
                    }
                ]
            },
        )

        result = news(query="tech news")

        assert "News Story" in result

    @patch("ot_tools.brave_search._make_request")
    def test_uses_news_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        news(query="test")

        call_args = mock_request.call_args
        assert "/news/search" in call_args[0][0]


@pytest.mark.unit
@pytest.mark.tools
class TestLocal:
    """Test local function with mocked HTTP."""

    @patch("ot_tools.brave_search._make_request")
    def test_successful_local_search(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "locations": {
                    "results": [{"title": "Coffee Shop", "address": {}, "rating": {}}]
                }
            },
        )

        result = local(query="coffee near me")

        assert "Coffee Shop" in result


@pytest.mark.unit
@pytest.mark.tools
class TestImage:
    """Test image function with mocked HTTP."""

    @patch("ot_tools.brave_search._make_request")
    def test_successful_image_search(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "results": [
                    {"title": "Image", "url": "https://img.com/1.png", "properties": {}}
                ]
            },
        )

        result = image(query="python logo")

        assert "Image" in result

    @patch("ot_tools.brave_search._make_request")
    def test_uses_images_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        image(query="test")

        call_args = mock_request.call_args
        assert "/images/search" in call_args[0][0]


@pytest.mark.unit
@pytest.mark.tools
class TestVideo:
    """Test video function with mocked HTTP."""

    @patch("ot_tools.brave_search._make_request")
    def test_successful_video_search(self, mock_request):
        mock_request.return_value = (
            True,
            {"results": [{"title": "Tutorial", "url": "https://yt.com", "video": {}}]},
        )

        result = video(query="python tutorial")

        assert "Tutorial" in result

    @patch("ot_tools.brave_search._make_request")
    def test_uses_videos_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        video(query="test")

        call_args = mock_request.call_args
        assert "/videos/search" in call_args[0][0]


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatch:
    """Test search_batch function."""

    @patch("ot_tools.brave_search.search")
    def test_executes_multiple_queries(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(queries=["query1", "query2"])

        assert mock_search.call_count == 2
        assert "query1" in result
        assert "query2" in result

    @patch("ot_tools.brave_search.search")
    def test_handles_tuples_with_labels(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(queries=[("actual query", "Custom Label")])

        assert "Custom Label" in result

    @patch("ot_tools.brave_search.search")
    def test_preserves_order(self, mock_search):
        mock_search.side_effect = ["First result", "Second result"]

        result = search_batch(queries=["first", "second"])

        # Check that first appears before second
        first_pos = result.find("first")
        second_pos = result.find("second")
        assert first_pos < second_pos

    def test_empty_queries_returns_error(self):
        result = search_batch(queries=[])

        assert "Error" in result
        assert "No queries provided" in result


# -----------------------------------------------------------------------------
# API Key Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestMakeRequest:
    """Test _make_request function."""

    @patch("ot_tools.brave_search._get_api_key")
    def test_returns_error_without_api_key(self, mock_key):
        from ot_tools.brave_search import _make_request

        mock_key.return_value = ""

        success, result = _make_request("/web/search", {"q": "test"})

        assert success is False
        assert "BRAVE_API_KEY" in result
