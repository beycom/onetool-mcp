"""Tests for Brave Search API tools.

Tests pure functions (validators, formatters) and main functions with HTTP mocks.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from otutil.tools.brave import (
    Config,
    _FRESHNESS_VALUES,
    _SAFESEARCH_IMAGE_VALUES,
    _SAFESEARCH_WEB_VALUES,
    _clamp,
    _format_image_results,
    _format_news_results,
    _format_video_results,
    _format_web_results,
    _validate_max_results,
    _validate_country,
    _validate_freshness,
    _validate_offset,
    _validate_query,
    _validate_safesearch,
    image,
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

    def test_default_timeout_is_180(self):
        assert Config().timeout == 180.0

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
class TestValidateFreshness:
    """Test _validate_freshness validation function."""

    def test_none_is_valid(self):
        assert _validate_freshness(None) is None

    def test_enum_values_valid(self):
        for v in _FRESHNESS_VALUES:
            assert _validate_freshness(v) is None

    def test_date_range_valid(self):
        assert _validate_freshness("2024-01-01to2024-06-30") is None

    def test_invalid_value_returns_error(self):
        result = _validate_freshness("yesterday")
        assert result is not None
        assert "Invalid freshness" in result

    def test_malformed_date_range_returns_error(self):
        result = _validate_freshness("2024-01-01-2024-06-30")
        assert result is not None


@pytest.mark.unit
@pytest.mark.tools
class TestValidateSafesearch:
    """Test _validate_safesearch validation function."""

    def test_valid_web_values(self):
        for v in _SAFESEARCH_WEB_VALUES:
            assert _validate_safesearch(v, _SAFESEARCH_WEB_VALUES) is None

    def test_valid_image_values(self):
        for v in _SAFESEARCH_IMAGE_VALUES:
            assert _validate_safesearch(v, _SAFESEARCH_IMAGE_VALUES) is None

    def test_moderate_invalid_for_image(self):
        result = _validate_safesearch("moderate", _SAFESEARCH_IMAGE_VALUES)
        assert result is not None
        assert "Invalid safesearch" in result

    def test_invalid_value_returns_error(self):
        result = _validate_safesearch("invalid", _SAFESEARCH_WEB_VALUES)
        assert result is not None
        assert "Invalid safesearch" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateMaxResults:
    """Test _validate_max_results validation function."""

    def test_valid_count(self):
        assert _validate_max_results(10) is None

    def test_min_count(self):
        assert _validate_max_results(1) is None

    def test_max_count(self):
        assert _validate_max_results(20) is None

    def test_zero_returns_error(self):
        result = _validate_max_results(0)
        assert result is not None
        assert "max_results" in result

    def test_negative_returns_error(self):
        result = _validate_max_results(-5)
        assert result is not None
        assert "max_results" in result

    def test_over_max_returns_error(self):
        result = _validate_max_results(21)
        assert result is not None
        assert "max_results" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateOffset:
    """Test _validate_offset validation function."""

    def test_valid_offset(self):
        assert _validate_offset(0) is None
        assert _validate_offset(9) is None

    def test_negative_returns_error(self):
        result = _validate_offset(-1)
        assert result is not None
        assert "offset" in result

    def test_over_max_returns_error(self):
        result = _validate_offset(10)
        assert result is not None
        assert "offset" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateCountry:
    """Test _validate_country validation function."""

    def test_valid_country(self):
        assert _validate_country("US") is None
        assert _validate_country("GB") is None

    def test_lowercase_returns_error(self):
        result = _validate_country("us")
        assert result is not None
        assert "Invalid country" in result

    def test_too_long_returns_error(self):
        result = _validate_country("USA")
        assert result is not None

    def test_empty_returns_error(self):
        result = _validate_country("")
        assert result is not None

    def test_non_str_returns_clean_error_not_typeerror(self):
        """Reachable via legacy count=5 prefix-binding to country. Must return
        the standard error string, not raise TypeError."""
        result = _validate_country(5)
        assert result is not None
        assert "Invalid country" in result


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
                        "url": "https://docs.python.org/3/tutorial",
                        "description": "Learn Python",
                    }
                ]
            }
        }

        result = _format_web_results(data)

        assert "Python Tutorial" in result
        assert "https://docs.python.org/3/tutorial" in result
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

    def test_text_only_omits_sources_and_urls(self):
        data = {
            "web": {
                "results": [
                    {
                        "title": "Python Tutorial",
                        "url": "https://docs.python.org/3/tutorial",
                        "description": "Learn Python",
                    }
                ]
            }
        }

        result = _format_web_results(data, output_format="text_only")

        assert "Python Tutorial" in result
        assert "Learn Python" in result
        assert "https://docs.python.org/3/tutorial" not in result
        assert "## Sources" not in result


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

    def test_sorts_by_page_age_descending(self):
        data = {
            "results": [
                {"title": "Older", "url": "https://a.com", "page_age": "2024-01-01T00:00:00"},
                {"title": "Newest", "url": "https://b.com", "page_age": "2024-06-01T00:00:00"},
                {"title": "Middle", "url": "https://c.com", "page_age": "2024-03-01T00:00:00"},
            ]
        }

        result = _format_news_results(data)

        newest_pos = result.find("Newest")
        middle_pos = result.find("Middle")
        older_pos = result.find("Older")
        assert newest_pos < middle_pos < older_pos

    def test_items_without_page_age_go_last(self):
        data = {
            "results": [
                {"title": "No Date", "url": "https://a.com"},
                {"title": "Has Date", "url": "https://b.com", "page_age": "2024-01-01T00:00:00"},
            ]
        }

        result = _format_news_results(data)

        assert result.find("Has Date") < result.find("No Date")



@pytest.mark.unit
@pytest.mark.tools
class TestFormatImageResults:
    """Test _format_image_results formatting function."""

    def test_formats_results(self):
        data = {
            "results": [
                {
                    "title": "Python Logo",
                    "url": "https://docs.python.org/3/tutorial.png",
                    "source": "test.invalid",
                    "properties": {"width": 800, "height": 600},
                }
            ]
        }

        result = _format_image_results(data)

        assert "Python Logo" in result
        assert "800x600" in result
        assert "test.invalid" in result

    def test_handles_empty_results(self):
        data = {"results": []}

        result = _format_image_results(data)

        assert "No image results found" in result

    def test_blank_title_shows_no_title(self):
        data = {
            "results": [
                {"title": "", "url": "https://test.invalid/img.jpg", "properties": {}}
            ]
        }

        result = _format_image_results(data)

        assert "No title" in result

    def test_includes_direct_image_url(self):
        data = {
            "results": [
                {
                    "title": "Photo",
                    "url": "https://test.invalid/page",
                    "source": "test.invalid",
                    "properties": {
                        "url": "https://cdn.test.invalid/photo.jpg",
                        "width": 800,
                        "height": 600,
                    },
                }
            ]
        }

        result = _format_image_results(data)

        assert "Image: https://cdn.test.invalid/photo.jpg" in result
        assert "https://test.invalid/page" in result


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
                    "url": "https://en.wikipedia.org/wiki/Test",
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

    @patch("otutil.tools.brave._make_request")
    def test_successful_search(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "web": {
                    "results": [
                        {
                            "title": "Result",
                            "url": "https://en.wikipedia.org/wiki/Test",
                            "description": "Description",
                        }
                    ]
                }
            },
        )

        result = search(query="test query")

        assert "Result" in result
        mock_request.assert_called_once()

    @patch("otutil.tools.brave._make_request")
    def test_returns_error_on_failure(self, mock_request):
        mock_request.return_value = (False, "API error")

        result = search(query="test")

        assert "API error" in result

    def test_validates_query_length(self):
        long_query = "x" * 401

        result = search(query=long_query)

        assert "400 character" in result

    def test_rejects_count_too_high(self):
        result = search(query="test", max_results=21)
        assert "max_results" in result

    def test_rejects_count_zero(self):
        result = search(query="test", max_results=0)
        assert "max_results" in result

    def test_rejects_count_negative(self):
        result = search(query="test", max_results=-1)
        assert "max_results" in result

    def test_rejects_invalid_safesearch(self):
        result = search(query="test", safesearch="invalid")
        assert "Invalid safesearch" in result

    def test_rejects_invalid_country(self):
        result = search(query="test", country="INVALID")
        assert "Invalid country" in result

    @patch("otutil.tools.brave._make_request")
    def test_includes_freshness(self, mock_request):
        mock_request.return_value = (True, {"web": {"results": []}})

        search(query="test", freshness="pw")

        call_args = mock_request.call_args
        assert call_args[0][1]["freshness"] == "pw"

    @patch("otutil.tools.brave._make_request")
    def test_accepts_date_range_freshness(self, mock_request):
        mock_request.return_value = (True, {"web": {"results": []}})

        search(query="test", freshness="2024-01-01to2024-06-30")

        call_args = mock_request.call_args
        assert call_args[0][1]["freshness"] == "2024-01-01to2024-06-30"

    def test_rejects_invalid_freshness(self):
        result = search(query="test", freshness="yesterday")
        assert "Invalid freshness" in result

    @patch("otutil.tools.brave._make_request")
    def test_output_format_text_only(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "web": {
                    "results": [
                        {
                            "title": "Result",
                            "url": "https://en.wikipedia.org/wiki/Test",
                            "description": "Description",
                        }
                    ]
                }
            },
        )

        result = search(query="test query", output_format="text_only")

        assert "Result" in result
        assert "Description" in result
        assert "https://en.wikipedia.org/wiki/Test" not in result
        assert "## Sources" not in result


@pytest.mark.unit
@pytest.mark.tools
class TestNews:
    """Test news function with mocked HTTP."""

    @patch("otutil.tools.brave._make_request")
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

    @patch("otutil.tools.brave._make_request")
    def test_uses_news_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        news(query="test")

        call_args = mock_request.call_args
        assert "/news/search" in call_args[0][0]

    @patch("otutil.tools.brave._make_request")
    def test_accepts_py_freshness(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        news(query="test", freshness="py")

        call_args = mock_request.call_args
        assert call_args[0][1]["freshness"] == "py"

    @patch("otutil.tools.brave._make_request")
    def test_accepts_date_range_freshness(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        news(query="test", freshness="2024-01-01to2024-06-30")

        call_args = mock_request.call_args
        assert call_args[0][1]["freshness"] == "2024-01-01to2024-06-30"

    def test_rejects_invalid_freshness(self):
        result = news(query="test", freshness="last_week")
        assert "Invalid freshness" in result



@pytest.mark.unit
@pytest.mark.tools
class TestImage:
    """Test image function with mocked HTTP."""

    @patch("otutil.tools.brave._make_request")
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

    @patch("otutil.tools.brave._make_request")
    def test_uses_images_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        image(query="test")

        call_args = mock_request.call_args
        assert "/images/search" in call_args[0][0]

    def test_rejects_moderate_safesearch(self):
        result = image(query="test", safesearch="moderate")
        assert "Invalid safesearch" in result

    def test_rejects_invalid_safesearch(self):
        result = image(query="test", safesearch="invalid")
        assert "Invalid safesearch" in result


@pytest.mark.unit
@pytest.mark.tools
class TestVideo:
    """Test video function with mocked HTTP."""

    @patch("otutil.tools.brave._make_request")
    def test_successful_video_search(self, mock_request):
        mock_request.return_value = (
            True,
            {"results": [{"title": "Tutorial", "url": "https://yt.com", "video": {}}]},
        )

        result = video(query="python tutorial")

        assert "Tutorial" in result

    @patch("otutil.tools.brave._make_request")
    def test_uses_videos_endpoint(self, mock_request):
        mock_request.return_value = (True, {"results": []})

        video(query="test")

        call_args = mock_request.call_args
        assert "/videos/search" in call_args[0][0]


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatch:
    """Test search_batch function."""

    @patch("otutil.tools.brave.search")
    def test_executes_multiple_queries(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(queries=["query1", "query2"])

        assert mock_search.call_count == 2
        assert isinstance(result, dict)
        assert result["meta"]["query_count"] == 2
        assert result["results"][0]["query"] == "query1"
        assert result["results"][1]["query"] == "query2"

    @patch("otutil.tools.brave.search")
    def test_handles_tuples_with_labels(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(queries=[("actual query", "Custom Label")])

        assert result["results"][0]["label"] == "Custom Label"

    @patch("otutil.tools.brave.search")
    def test_preserves_order(self, mock_search):
        mock_search.side_effect = ["First result", "Second result"]

        result = search_batch(queries=["first", "second"])

        assert result["results"][0]["query"] == "first"
        assert result["results"][1]["query"] == "second"

    def test_empty_queries_returns_error(self):
        result = search_batch(queries=[])

        assert "Error" in result
        assert "No queries provided" in result

    @patch("otutil.tools.brave.search")
    def test_forwards_safesearch(self, mock_search):
        mock_search.return_value = "Result"

        search_batch(queries=["test"], safesearch="strict")

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["safesearch"] == "strict"

    @patch("otutil.tools.brave.search")
    def test_forwards_freshness(self, mock_search):
        mock_search.return_value = "Result"

        search_batch(queries=["test"], freshness="pw")

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["freshness"] == "pw"

    def test_rejects_invalid_freshness(self):
        result = search_batch(queries=["test"], freshness="yesterday")

        assert "Invalid freshness" in result

    @patch("otutil.tools.brave.search")
    def test_empty_label_falls_back_to_query(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(queries=[("rust programming", "")])

        assert result["results"][0]["label"] == "rust programming"

    def test_rejects_invalid_count(self):
        result = search_batch(queries=["test"], max_results=0)
        assert "max_results" in result

    def test_rejects_invalid_safesearch(self):
        result = search_batch(queries=["test"], safesearch="invalid")
        assert "Invalid safesearch" in result

    def test_rejects_invalid_retry_controls(self):
        result = search_batch(queries=["test"], retries=-1)
        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["test"], retries="x")  # type: ignore[arg-type]
        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["test"], retries=4)
        assert "retries must be between 0 and 3" in result

        result = search_batch(queries=["test"], retry_delay_ms=10_001)
        assert "retry_delay_ms must be between 0 and 10000" in result

        result = search_batch(queries=["test"], retry_delay_ms="x")  # type: ignore[arg-type]
        assert "retry_delay_ms must be between 0 and 10000" in result

    @patch("otutil.tools.brave.search")
    def test_forwards_text_only_output_format(self, mock_search):
        mock_search.return_value = "Result"

        search_batch(queries=["test"], output_format="text_only")

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["output_format"] == "text_only"

    @patch("otutil.tools.brave.search")
    def test_accepts_retry_control_upper_bounds(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(
            queries=["test"],
            retries=3,
            retry_delay_ms=10_000,
        )

        assert result["meta"]["retries"] == 3

    @patch("otutil.tools.brave.search")
    def test_retries_transient_timeout(self, mock_search):
        mock_search.side_effect = [
            "Error: Request timed out. Try again.",
            "Recovered result",
        ]

        result = search_batch(queries=["test"], retries=1, retry_delay_ms=0)

        assert result["results"][0]["status"] == "ok"
        assert result["results"][0]["attempts"] == 2
        assert result["results"][0]["retried"] is True

    @patch("otutil.tools.brave.search")
    def test_error_envelope_after_retries_exhausted(self, mock_search):
        mock_search.return_value = "Error: HTTP 500 Internal Server Error"

        result = search_batch(queries=["test"], retries=1, retry_delay_ms=0)

        item = result["results"][0]
        assert item["status"] == "error"
        assert item["final_failure"] is True
        assert item["error"] is not None
        assert item["error"]["error_code"] == "http_5xx"

    @patch("otutil.tools.brave.search")
    def test_duplicate_labels_preserved(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(
            queries=[("query1", "dup"), ("query2", "dup")],
            retry_delay_ms=0,
        )

        assert len(result["results"]) == 2
        assert result["results"][0]["label"] == "dup"
        assert result["results"][1]["label"] == "dup"

    @patch("otutil.tools.brave.search")
    def test_partial_success_meta(self, mock_search):
        mock_search.side_effect = ["Result", "Error: HTTP 500 Internal Server Error"]

        result = search_batch(queries=["q1", "q2"], retries=0, retry_delay_ms=0)

        assert result["meta"]["success_count"] == 1
        assert result["meta"]["error_count"] == 1
        assert result["meta"]["partial_success"] is True


# -----------------------------------------------------------------------------
# API Key Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestMakeRequest:
    """Test _make_request function."""

    @patch("otutil.tools.brave.require_api_key", return_value=("", "Error: BRAVE_API_KEY secret not configured"))
    def test_returns_error_without_api_key(self, _mock_key):
        from otutil.tools.brave import _make_request

        success, result = _make_request("/web/search", {"q": "test"})

        assert success is False
        assert "BRAVE_API_KEY" in result
