"""Tests for Tavily AI search tools.

Tests pure functions (validators, formatters) and main functions with HTTP mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from otpack import format_sources as _format_sources
from otutil.tools.tavily import (
    Config,
    _EXTRACT_DEPTH_VALUES,
    _EXTRACT_FORMAT_VALUES,
    _OUTPUT_FORMAT_VALUES,
    _RESEARCH_MODEL_VALUES,
    _SEARCH_DEPTH_VALUES,
    _TIME_RANGE_VALUES,
    _TOPIC_VALUES,
    _format_extract_results,
    _format_search_results,
    _validate_days,
    _validate_extract_depth,
    _validate_extract_format,
    _validate_max_results,
    _validate_output_format,
    _validate_query,
    _validate_research_model,
    _validate_search_depth,
    _validate_time_range,
    _validate_topic,
    _validate_urls,
    extract,
    extract_batch,
    research,
    search,
    search_batch,
)

# -----------------------------------------------------------------------------
# Pure Function Tests (No Mocking Required)
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestValidateQuery:
    def test_default_timeout_is_180(self):
        assert Config().timeout == 180.0

    def test_valid_query(self):
        assert _validate_query("python best practices") is None

    def test_empty_query(self):
        result = _validate_query("")
        assert result is not None
        assert "empty" in result

    def test_whitespace_only_query(self):
        result = _validate_query("   ")
        assert result is not None
        assert "empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateMaxResults:
    def test_valid_max_results(self):
        assert _validate_max_results(5) is None

    def test_max_results_at_min(self):
        assert _validate_max_results(1) is None

    def test_max_results_at_max(self):
        assert _validate_max_results(20) is None

    def test_max_results_too_low(self):
        result = _validate_max_results(0)
        assert result is not None
        assert "1" in result and "20" in result

    def test_max_results_too_high(self):
        result = _validate_max_results(21)
        assert result is not None
        assert "1" in result and "20" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateSearchDepth:
    def test_valid_basic(self):
        assert _validate_search_depth("basic") is None

    def test_valid_advanced(self):
        assert _validate_search_depth("advanced") is None

    def test_invalid_depth(self):
        result = _validate_search_depth("deep")
        assert result is not None
        assert "deep" in result

    def test_all_valid_values(self):
        for val in _SEARCH_DEPTH_VALUES:
            assert _validate_search_depth(val) is None


@pytest.mark.unit
@pytest.mark.tools
class TestValidateTopic:
    def test_valid_general(self):
        assert _validate_topic("general") is None

    def test_valid_news(self):
        assert _validate_topic("news") is None

    def test_valid_finance(self):
        assert _validate_topic("finance") is None

    def test_invalid_topic(self):
        result = _validate_topic("sports")
        assert result is not None
        assert "sports" in result

    def test_all_valid_values(self):
        for val in _TOPIC_VALUES:
            assert _validate_topic(val) is None


@pytest.mark.unit
@pytest.mark.tools
class TestValidateTimeRange:
    def test_none_is_valid(self):
        assert _validate_time_range(None) is None

    def test_all_valid_values(self):
        for val in _TIME_RANGE_VALUES:
            assert _validate_time_range(val) is None

    def test_invalid_time_range(self):
        result = _validate_time_range("hour")
        assert result is not None
        assert "hour" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateDays:
    def test_valid_days(self):
        assert _validate_days(3) is None

    def test_days_at_min(self):
        assert _validate_days(1) is None

    def test_days_at_max(self):
        assert _validate_days(30) is None

    def test_days_too_low(self):
        result = _validate_days(0)
        assert result is not None
        assert "1" in result and "30" in result

    def test_days_too_high(self):
        result = _validate_days(31)
        assert result is not None
        assert "1" in result and "30" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateUrls:
    def test_valid_urls(self):
        assert _validate_urls(["https://docs.python.org/3/library/test"]) is None

    def test_empty_urls(self):
        result = _validate_urls([])
        assert result is not None
        assert "empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateOutputFormat:
    def test_all_valid_values(self):
        for val in _OUTPUT_FORMAT_VALUES:
            assert _validate_output_format(val) is None

    def test_invalid_format(self):
        result = _validate_output_format("xml")
        assert result is not None
        assert "xml" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateExtractFormat:
    def test_all_valid_values(self):
        for val in _EXTRACT_FORMAT_VALUES:
            assert _validate_extract_format(val) is None

    def test_invalid_format(self):
        result = _validate_extract_format("html")
        assert result is not None
        assert "html" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateExtractDepth:
    def test_all_valid_values(self):
        for val in _EXTRACT_DEPTH_VALUES:
            assert _validate_extract_depth(val) is None

    def test_invalid_depth(self):
        result = _validate_extract_depth("deep")
        assert result is not None
        assert "deep" in result


@pytest.mark.unit
@pytest.mark.tools
class TestValidateResearchModel:
    def test_all_valid_values(self):
        for val in _RESEARCH_MODEL_VALUES:
            assert _validate_research_model(val) is None

    def test_invalid_model(self):
        result = _validate_research_model("turbo")
        assert result is not None
        assert "turbo" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFormatSources:
    def test_basic_sources(self):
        results = [
            {"url": "https://a.com", "title": "Site A"},
            {"url": "https://b.com", "title": "Site B"},
        ]
        output = _format_sources(results)
        assert "1. [Site A](https://a.com)" in output
        assert "2. [Site B](https://b.com)" in output

    def test_deduplication(self):
        results = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://a.com", "title": "A duplicate"},
        ]
        output = _format_sources(results)
        assert output.count("https://a.com") == 1

    def test_title_fallback_to_url(self):
        results = [{"url": "https://a.com", "title": ""}]
        output = _format_sources(results)
        assert "https://a.com" in output

    def test_empty_results(self):
        assert _format_sources([]) == ""


@pytest.mark.unit
@pytest.mark.tools
class TestFormatSearchResults:
    def test_full_format_with_results(self):
        data = {
            "answer": "Python is great.",
            "results": [
                {"title": "Python Docs", "url": "https://python.org", "content": "Official docs", "score": 0.9}
            ],
        }
        result = _format_search_results(data, "full", None)
        assert "Python is great." in result
        assert "Python Docs" in result
        assert "https://python.org" in result
        assert "## Sources" in result

    def test_full_format_with_credits(self):
        data = {
            "results": [{"title": "X", "url": "https://x.com", "content": ""}],
            "usage": {"credits": 2},
        }
        result = _format_search_results(data, "full", None)
        assert "[Credits: 2]" in result

    def test_full_format_no_results(self):
        result = _format_search_results({"results": []}, "full", None)
        assert "No results found." in result

    def test_text_only_returns_answer(self):
        data = {
            "answer": "The answer is 42.",
            "results": [{"title": "X", "url": "https://x.com", "content": ""}],
        }
        result = _format_search_results(data, "text_only", None)
        assert result == "The answer is 42."
        assert "X" not in result

    def test_text_only_no_answer(self):
        result = _format_search_results({"results": []}, "text_only", None)
        assert "No answer available." in result

    def test_sources_only(self):
        data = {
            "results": [
                {"title": "A", "url": "https://a.com", "content": ""},
                {"title": "B", "url": "https://b.com", "content": ""},
            ]
        }
        result = _format_search_results(data, "sources_only", None)
        assert "https://a.com" in result
        assert "https://b.com" in result
        assert "## Sources" not in result

    def test_sources_only_no_results(self):
        result = _format_search_results({"results": []}, "sources_only", None)
        assert "No sources found." in result

    def test_min_score_filtering(self):
        data = {
            "results": [
                {"title": "High", "url": "https://high.com", "content": "", "score": 0.9},
                {"title": "Low", "url": "https://low.com", "content": "", "score": 0.2},
            ]
        }
        result = _format_search_results(data, "full", 0.5)
        assert "https://high.com" in result
        assert "https://low.com" not in result

    def test_min_score_all_filtered(self):
        data = {
            "results": [
                {"title": "Low", "url": "https://low.com", "content": "", "score": 0.1},
            ]
        }
        result = _format_search_results(data, "full", 0.5)
        assert "No results found." in result


@pytest.mark.unit
@pytest.mark.tools
class TestFormatExtractResults:
    def test_empty_results(self):
        result = _format_extract_results({"results": [], "failed_results": []})
        assert "No content extracted." in result

    def test_successful_extraction(self):
        data = {
            "results": [
                {"url": "https://test.invalid", "raw_content": "Page content here."}
            ],
            "failed_results": [],
        }
        result = _format_extract_results(data)
        assert "https://test.invalid" in result
        assert "Page content here." in result

    def test_failed_extraction(self):
        data = {
            "results": [],
            "failed_results": [{"url": "https://bad.com", "error": "404 Not Found"}],
        }
        result = _format_extract_results(data)
        assert "Failed" in result
        assert "https://bad.com" in result
        assert "404 Not Found" in result

    def test_mixed_results(self):
        data = {
            "results": [{"url": "https://ok.com", "raw_content": "OK content"}],
            "failed_results": [{"url": "https://fail.com", "error": "timeout"}],
        }
        result = _format_extract_results(data)
        assert "https://ok.com" in result
        assert "OK content" in result
        assert "https://fail.com" in result
        assert "timeout" in result


# -----------------------------------------------------------------------------
# Mocked HTTP Tests
# -----------------------------------------------------------------------------


def _make_mock_response(data: dict) -> MagicMock:
    """Create a mock httpx response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    def test_basic_search(self):
        response_data = {
            "results": [
                {
                    "title": "Python Docs",
                    "url": "https://docs.python.org",
                    "content": "Official Python documentation",
                    "score": 0.95,
                }
            ],
            "answer": "Python is a programming language.",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(query="python documentation")

        assert "Python Docs" in result
        assert "https://docs.python.org" in result
        assert "Python is a programming language." in result

    def test_validation_error_empty_query(self):
        result = search(query="")
        assert "Error" in result
        assert "empty" in result

    def test_validation_error_invalid_depth(self):
        result = search(query="test", search_depth="invalid")
        assert "Error" in result

    def test_validation_error_invalid_topic(self):
        result = search(query="test", topic="bogus")
        assert "Error" in result

    def test_validation_error_invalid_output_format(self):
        result = search(query="test", output_format="xml")  # type: ignore[arg-type]
        assert "Error" in result

    def test_missing_api_key(self):
        with patch("otutil.tools.tavily.require_api_key", return_value=("", "Error: TAVILY_API_KEY secret not configured")):
            result = search(query="test")
        assert "TAVILY_API_KEY" in result

    def test_output_format_text_only(self):
        response_data = {
            "answer": "Python was created by Guido van Rossum.",
            "results": [
                {"title": "Python History", "url": "https://x.com", "content": "...", "score": 0.9}
            ],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(query="who created python", output_format="text_only")

        assert result == "Python was created by Guido van Rossum."
        assert "Python History" not in result

    def test_output_format_sources_only(self):
        response_data = {
            "answer": "Some answer.",
            "results": [
                {"title": "Source A", "url": "https://a.com", "content": "...", "score": 0.9}
            ],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(query="test", output_format="sources_only")

        assert "https://a.com" in result
        assert "Some answer." not in result

    def test_min_score_filtering(self):
        response_data = {
            "results": [
                {"title": "High", "url": "https://high.com", "content": "Good", "score": 0.9},
                {"title": "Low", "url": "https://low.com", "content": "Bad", "score": 0.1},
            ]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(query="test", min_score=0.5)

        assert "https://high.com" in result
        assert "https://low.com" not in result

    def test_domain_filters_sent_in_payload(self):
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            search(
                query="test",
                include_domains=["docs.python.org"],
                exclude_domains=["spam.com"],
            )

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["include_domains"] == ["docs.python.org"]
        assert payload["exclude_domains"] == ["spam.com"]

    def test_api_key_sent_as_bearer_header(self):
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            search(query="test")

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert "api_key" not in call_kwargs["json"]

    def test_include_answer_sent_to_api(self):
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            search(query="test")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["include_answer"] is True

    def test_sources_section_in_full_output(self):
        response_data = {
            "results": [{"title": "A", "url": "https://a.com", "content": "content", "score": 0.9}],
            "answer": "The answer.",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(query="test", output_format="full")

        assert "## Sources" in result
        assert "[A](https://a.com)" in result

    def test_search_extract_schema_with_provenance(self):
        response_data = {
            "answer": "name: Alice email: alice@example.com",
            "results": [
                {
                    "title": "Profile",
                    "url": "https://people.invalid/alice",
                    "content": "name: Alice email: alice@example.com",
                    "score": 0.87,
                }
            ],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(
                query="alice contact",
                extract_schema={
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "email", "type": "string", "required": True},
                    ]
                },
                return_provenance=True,
            )

        assert result["mode"] == "structured_extraction"
        assert result["data"]["email"] == "alice@example.com"
        assert result["provenance"]["email"]["source_url"] == "https://people.invalid/alice"

    def test_search_extract_schema_required_field_missing(self):
        response_data = {
            "answer": "No contact info available.",
            "results": [{"title": "X", "url": "https://x.invalid", "content": "No email", "score": 0.2}],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search(
                query="missing email",
                extract_schema={"fields": [{"name": "email", "type": "string", "required": True}]},
            )

        assert result["errors"]
        assert result["errors"][0]["error_code"] == "required_field_missing"

    def test_search_extract_schema_validation_error(self):
        result = search(query="x", extract_schema={"fields": []})
        assert "extract_schema.fields must be a non-empty list" in result

    def test_extract_schema_skips_result_formatting(self):
        response_data = {
            "answer": "name: Alice",
            "results": [{"title": "X", "url": "https://x.invalid", "content": "name: Alice", "score": 0.9}],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily._format_search_results") as mock_fmt,
        ):
            result = search(
                query="alice",
                extract_schema={"fields": [{"name": "name", "type": "string"}]},
            )

        assert result["mode"] == "structured_extraction"
        mock_fmt.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
class TestExtract:
    def test_basic_extraction(self):
        response_data = {
            "results": [
                {
                    "url": "https://test.invalid/page",
                    "raw_content": "This is the page content.",
                }
            ],
            "failed_results": [],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = extract(urls=["https://test.invalid/page"])

        assert "https://test.invalid/page" in result
        assert "This is the page content." in result

    def test_validation_error_empty_urls(self):
        result = extract(urls=[])
        assert "Error" in result
        assert "empty" in result

    def test_validation_error_invalid_format(self):
        result = extract(urls=["https://test.invalid"], format="html")
        assert "Error" in result

    def test_validation_error_invalid_depth(self):
        result = extract(urls=["https://test.invalid"], extract_depth="deep")
        assert "Error" in result

    def test_extract_depth_sent_in_payload(self):
        response_data = {"results": [{"url": "https://a.com", "raw_content": "x"}], "failed_results": []}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            extract(urls=["https://a.com"], extract_depth="advanced")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["extract_depth"] == "advanced"

    def test_format_sent_in_payload(self):
        response_data = {"results": [{"url": "https://a.com", "raw_content": "x"}], "failed_results": []}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            extract(urls=["https://a.com"], format="text")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["format"] == "text"

    def test_default_format_sent_in_payload(self):
        response_data = {"results": [{"url": "https://a.com", "raw_content": "x"}], "failed_results": []}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            extract(urls=["https://a.com"])

        payload = mock_client.post.call_args[1]["json"]
        assert payload["format"] == "markdown"

    def test_missing_api_key(self):
        with patch("otutil.tools.tavily.require_api_key", return_value=("", "Error: TAVILY_API_KEY secret not configured")):
            result = extract(urls=["https://test.invalid"])
        assert "TAVILY_API_KEY" in result


@pytest.mark.unit
@pytest.mark.tools
class TestExtractBatch:
    def test_basic_batch(self):
        response_data = {
            "results": [{"url": "https://a.com", "raw_content": "Content A"}],
            "failed_results": [],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = extract_batch(url_sets=[
                ["https://a.com"],
                ["https://b.com"],
            ])

        assert isinstance(result, dict)
        assert result["meta"]["query_count"] == 2
        assert result["results"][0]["label"] == "https://a.com"
        assert result["results"][0]["status"] == "ok"
        assert "Content A" in result["results"][0]["data"]

    def test_labeled_sets(self):
        response_data = {
            "results": [{"url": "https://docs.react.dev", "raw_content": "React docs"}],
            "failed_results": [],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = extract_batch(url_sets=[
                (["https://docs.react.dev"], "React Docs"),
            ])

        assert result["results"][0]["label"] == "React Docs"
        assert "React docs" in result["results"][0]["data"]

    def test_multi_url_set_forwarded_to_extract(self):
        response_data = {
            "results": [{"url": "https://a.com/1", "raw_content": "x"}],
            "failed_results": [],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = extract_batch(url_sets=[
                (["https://a.com/1", "https://a.com/2"], "Docs"),
            ])

        payload = mock_client.post.call_args[1]["json"]
        assert payload["urls"] == ["https://a.com/1", "https://a.com/2"]
        assert result["results"][0]["status"] == "ok"

    def test_empty_url_sets(self):
        result = extract_batch(url_sets=[])
        assert "Error" in result

    def test_empty_urls_in_set(self):
        result = extract_batch(url_sets=[[]])
        assert "Error" in result

    def test_validation_error_invalid_format(self):
        result = extract_batch(url_sets=[["https://a.com"]], format="html")
        assert "Error" in result

    def test_rejects_invalid_retry_controls(self):
        result = extract_batch(url_sets=[["https://a.com"]], retries=-1)
        assert "retries must be between 0 and 3" in result

        result = extract_batch(url_sets=[["https://a.com"]], retry_delay_ms=10_001)
        assert "retry_delay_ms must be between 0 and 10000" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSearchBatch:
    def test_basic_batch(self):
        response_data = {
            "results": [{"title": "Result", "url": "https://x.com", "content": "..."}],
            "answer": "An answer.",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search_batch(queries=["python", "javascript"])

        assert isinstance(result, dict)
        assert result["meta"]["query_count"] == 2
        assert result["results"][0]["query"] == "python"
        assert result["results"][1]["query"] == "javascript"

    def test_validation_error_invalid_depth(self):
        result = search_batch(queries=["test"], search_depth="bad")
        assert "Error" in result

    def test_validation_error_invalid_days(self):
        result = search_batch(queries=["test"], days=0)
        assert "days must be between 1 and 30" in result

    def test_days_and_domain_filters_forwarded(self):
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            search_batch(
                queries=["q"],
                days=7,
                include_domains=["docs.python.org"],
                exclude_domains=["spam.com"],
            )

        payload = mock_client.post.call_args[1]["json"]
        assert payload["days"] == 7
        assert payload["include_domains"] == ["docs.python.org"]
        assert payload["exclude_domains"] == ["spam.com"]

    def test_empty_queries(self):
        result = search_batch(queries=[])
        assert "Error" in result

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

    def test_tuple_queries_with_labels(self):
        response_data = {
            "results": [{"title": "R", "url": "https://x.com", "content": "..."}],
            "answer": "",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search_batch(
                queries=[("Python 3.13 features", "Python 3.13")]
            )

        assert result["results"][0]["label"] == "Python 3.13"

    def test_empty_label_falls_back_to_query(self):
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search_batch(queries=[("some query", "")])

        assert result["results"][0]["label"] == "some query"

    def test_output_format_forwarded(self):
        response_data = {
            "answer": "The answer.",
            "results": [{"title": "X", "url": "https://x.com", "content": "x", "score": 0.9}],
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search_batch(queries=["q"], output_format="text_only")

        assert result["results"][0]["status"] == "ok"
        assert result["results"][0]["data"] == "The answer."

    @patch("otutil.tools.tavily.search")
    def test_accepts_retry_control_upper_bounds(self, mock_search):
        mock_search.return_value = "Result"

        result = search_batch(
            queries=["q"],
            retries=3,
            retry_delay_ms=10_000,
        )

        assert result["meta"]["retries"] == 3

    def test_retry_envelope_on_transient_error(self):
        mock_client = MagicMock()
        fail = MagicMock()
        fail.raise_for_status.side_effect = Exception("timeout")
        ok = _make_mock_response({"answer": "ok", "results": []})
        mock_client.post.side_effect = [fail, ok]

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = search_batch(queries=["q"], retries=1, retry_delay_ms=0)

        assert result["results"][0]["status"] == "ok"
        assert result["results"][0]["attempts"] == 2


@pytest.mark.unit
@pytest.mark.tools
class TestResearch:
    def test_validation_error_empty_input(self):
        result = research(input="")
        assert "Error" in result
        assert "empty" in result

    def test_validation_error_invalid_model(self):
        result = research(input="some topic", model="turbo")
        assert "Error" in result
        assert "turbo" in result

    def test_validation_error_invalid_timeout(self):
        result = research(input="some topic", timeout_seconds=0)
        assert "timeout_seconds must be between 10 and 1800" in result

    def test_validation_error_non_integer_timeout(self):
        result = research(input="some topic", timeout_seconds="x")  # type: ignore[arg-type]
        assert "timeout_seconds must be between 10 and 1800" in result

        result = research(input="some topic", timeout_seconds=True)  # type: ignore[arg-type]
        assert "timeout_seconds must be between 10 and 1800" in result

    def test_missing_api_key(self):
        with patch("otutil.tools.tavily.require_api_key", return_value=("", "Error: TAVILY_API_KEY secret not configured")):
            result = research(input="some topic")
        assert "TAVILY_API_KEY" in result

    def test_synchronous_completion(self):
        """Research completes immediately (synchronous response)."""
        response_data = {
            "status": "completed",
            "content": "Detailed research report about FastAPI.",
        }
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
        ):
            result = research(input="How does FastAPI work?")

        assert "Detailed research report" in result

    def test_polling_completion(self):
        """Research requires polling before completing."""
        start_response = {"id": "task-123", "status": "processing"}
        poll_response = {"status": "completed", "content": "Research complete."}

        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(start_response)
        mock_client.get.return_value = _make_mock_response(poll_response)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.time.sleep"),
        ):
            result = research(input="Some topic", timeout_seconds=60)

        assert "Research complete." in result
        get_kwargs = mock_client.get.call_args.kwargs
        assert get_kwargs["headers"]["Authorization"] == "Bearer test-key"

    def test_poll_failure_cap(self):
        """Research aborts after 5 consecutive polling failures."""
        start_response = {"id": "task-999", "status": "processing"}

        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(start_response)
        mock_client.get.side_effect = Exception("connection reset")

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.time.sleep"),
        ):
            result = research(input="Some topic", timeout_seconds=300)

        assert "Error: research polling failed 5 consecutive times" in result
        assert mock_client.get.call_count == 5

    def test_timeout_exceeded(self):
        """Research times out when polling never completes."""
        start_response = {"id": "task-456", "status": "processing"}
        poll_response = {"status": "processing"}

        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(start_response)
        mock_client.get.return_value = _make_mock_response(poll_response)

        # Make time.monotonic advance rapidly to trigger timeout
        time_values = iter([0.0, 0.0, 10000.0])

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.time.sleep"),
            patch("otutil.tools.tavily.time.monotonic", side_effect=time_values),
        ):
            result = research(input="Some topic", timeout_seconds=10)

        assert "timed out" in result
        assert "10" in result

    def test_polling_uses_remaining_budget_for_sleep_and_get_timeout(self):
        """Research polling should clamp sleep and GET timeout to remaining budget."""
        start_response = {"id": "task-123", "status": "processing"}
        poll_response = {"status": "completed", "content": "Research complete."}
        monotonic_values = iter([0.0, 58.0, 59.5, 59.5, 59.5])

        with (
            patch(
                "otutil.tools.tavily._make_request",
                side_effect=[(True, start_response), (True, poll_response)],
            ) as mock_request,
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.time.sleep") as mock_sleep,
            patch("otutil.tools.tavily.time.monotonic", side_effect=monotonic_values),
        ):
            result = research(input="Some topic", timeout_seconds=60)

        assert "Research complete." in result
        mock_sleep.assert_called_once_with(2.0)
        assert mock_request.call_args.kwargs["timeout"] == 0.5
        assert mock_request.call_args.kwargs["method"] == "GET"

    def test_research_task_failed(self):
        """Research task fails on server side."""
        start_response = {"id": "task-789", "status": "processing"}
        poll_response = {"status": "failed", "error": "internal server error"}

        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(start_response)
        mock_client.get.return_value = _make_mock_response(poll_response)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.time.sleep"),
        ):
            result = research(input="Some topic", timeout_seconds=60)

        assert "Error" in result
        assert "failed" in result


@pytest.mark.unit
@pytest.mark.tools
class TestLogSpans:
    def test_search_spans_truncate_query(self):
        long_query = "q" * 200
        response_data = {"results": [], "answer": ""}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.LogSpan") as mock_span,
        ):
            search(query=long_query)

        assert mock_span.call_args_list
        for call in mock_span.call_args_list:
            assert len(call.kwargs.get("query", "")) <= 80

    def test_batch_span_names_are_distinct(self):
        response_data = {"results": [], "answer": "", "failed_results": []}
        mock_client = MagicMock()
        mock_client.post.return_value = _make_mock_response(response_data)

        with (
            patch("otutil.tools.tavily._get_http_client", return_value=mock_client),
            patch("otutil.tools.tavily.require_api_key", return_value=("test-key", None)),
            patch("otutil.tools.tavily.LogSpan") as mock_span,
        ):
            search_batch(queries=["q"])
            extract_batch(url_sets=[["https://a.com"]])

        spans = [c.kwargs.get("span") for c in mock_span.call_args_list]
        assert "tavily.search_batch" in spans
        assert "tavily.extract_batch" in spans
