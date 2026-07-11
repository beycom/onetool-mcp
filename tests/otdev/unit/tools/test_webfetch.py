"""Unit tests for webfetch tool pack."""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

_skip_no_trafilatura = pytest.mark.skipif(
    importlib.util.find_spec("trafilatura") is None,
    reason="trafilatura not installed ([dev] extra)",
)


@pytest.mark.unit
@pytest.mark.tools
class TestWebfetchPack:
    """Test webfetch pack structure."""

    def test_pack_name(self):
        from otdev.tools import webfetch

        assert webfetch.pack == "webfetch"

    def test_has_all_exports(self):
        from otdev.tools import webfetch

        assert hasattr(webfetch, "__all__")
        assert "fetch" in webfetch.__all__
        assert "fetch_batch" in webfetch.__all__
        assert len(webfetch.__all__) >= 1

    def test_functions_are_callable(self):
        from otdev.tools import webfetch

        for name in webfetch.__all__:
            func = getattr(webfetch, name)
            assert callable(func), f"{name} should be callable"


# -----------------------------------------------------------------------------
# Pure Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestValidateUrl:
    """Test _validate_url."""

    def test_valid_url(self):
        from otdev.tools.webfetch import _validate_url

        assert _validate_url("https://docs.python.org/3/library/test") is None

    def test_empty_url(self):
        from otdev.tools.webfetch import _validate_url

        result = _validate_url("")
        assert result is not None
        assert "empty" in result.lower()

    def test_whitespace_only(self):
        from otdev.tools.webfetch import _validate_url

        result = _validate_url("   ")
        assert result is not None

    def test_missing_scheme(self):
        from otdev.tools.webfetch import _validate_url

        result = _validate_url("docs.python.org/path")
        assert result is not None
        assert "Invalid URL" in result

    def test_missing_netloc(self):
        from otdev.tools.webfetch import _validate_url

        result = _validate_url("https://")
        assert result is not None


@pytest.mark.unit
@pytest.mark.tools
class TestValidateOptions:
    """Test _validate_options."""

    def test_both_false(self):
        from otdev.tools.webfetch import _validate_options

        assert _validate_options(False, False) is None

    def test_precision_only(self):
        from otdev.tools.webfetch import _validate_options

        assert _validate_options(True, False) is None

    def test_recall_only(self):
        from otdev.tools.webfetch import _validate_options

        assert _validate_options(False, True) is None

    def test_both_true(self):
        from otdev.tools.webfetch import _validate_options

        result = _validate_options(True, True)
        assert result is not None
        assert "favor_precision" in result and "favor_recall" in result



@pytest.mark.unit
@pytest.mark.tools
class TestIsHtmlContentType:
    """Test _is_html_content_type."""

    def test_none_defaults_to_html(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type(None) is True

    def test_text_html(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("text/html") is True

    def test_text_html_with_charset(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("text/html; charset=utf-8") is True

    def test_xhtml(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("application/xhtml+xml") is True

    def test_plain_text(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("text/plain") is False

    def test_json(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("application/json") is False

    def test_case_insensitive(self):
        from otdev.tools.webfetch import _is_html_content_type

        assert _is_html_content_type("Text/HTML") is True


# -----------------------------------------------------------------------------
# Mocked fetch() Tests
# -----------------------------------------------------------------------------


def _make_mock_response(html: str, content_type: str = "text/html") -> MagicMock:
    """Create a mock trafilatura response."""
    mock = MagicMock()
    mock.html = html
    mock.headers = {"content-type": content_type}
    return mock


@_skip_no_trafilatura
@pytest.mark.unit
@pytest.mark.tools
class TestFetch:
    """Test fetch() with mocked trafilatura."""

    def test_validation_empty_url(self):
        from otdev.tools.webfetch import fetch

        result = fetch(url="")
        assert "Error" in result

    def test_validation_both_precision_and_recall(self):
        from otdev.tools.webfetch import fetch

        result = fetch(url="https://test.invalid/page", favor_precision=True, favor_recall=True)
        assert "Error" in result

    def test_successful_fetch(self):
        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=("<html>test</html>", "text/html", "http://final.test/")),
            patch("trafilatura.extract", return_value="Extracted content"),
        ):
            result = fetch(url="https://test.invalid/page")

        assert result == "Extracted content"

    def test_fetch_returns_error_on_download_failure(self):
        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=(None, None, "http://final.test/")),
        ):
            result = fetch(url="https://test.invalid/page")

        assert "Error" in result
        assert "fetch" in result.lower()

    def test_fetch_returns_error_on_no_content(self):
        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=("<html></html>", "text/html", "http://final.test/")),
            patch("trafilatura.extract", return_value=None),
        ):
            result = fetch(url="https://test.invalid/page")

        assert "Error" in result
        assert "No content" in result

    def test_fetch_non_html_returns_raw(self):
        from otdev.tools.webfetch import fetch

        raw = '{"key": "value"}'
        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=(raw, "application/json", "http://final.test/")),
        ):
            result = fetch(url="https://test.invalid/data.json")

        assert result == raw

    def test_fetch_html_format(self):
        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=("<html><body><p>Hello</p></body></html>", "text/html", "http://final.test/")),
            patch("trafilatura.extract", return_value="<p>Hello</p>") as mock_extract,
        ):
            result = fetch(url="https://test.invalid/page", output_format="html")

        assert result == "<p>Hello</p>"
        mock_extract.assert_called_once()
        call_kwargs = mock_extract.call_args.kwargs
        assert call_kwargs["output_format"] == "html"

    def test_fetch_metadata_uses_actual_content_type(self):
        import json

        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=("<html>hi</html>", "text/html; charset=utf-8", "http://final.test/")),
            patch("trafilatura.extract", return_value='{"title": "Hi"}'),
        ):
            result = fetch(url="https://test.invalid/page", output_format="json", include_metadata=True)

        data = json.loads(result)
        assert data["metadata"]["content_type"] == "text/html; charset=utf-8"

    def test_fetch_metadata_includes_extracted_article_fields(self):
        import json

        from otdev.tools.webfetch import fetch

        payload = '{"title":"Hello","author":"Ada","date":"2026-01-01","text":"Body"}'
        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch(
                "otdev.tools.webfetch._fetch_url_cached",
                return_value=("<html><body>Hello</body></html>", "text/html", "http://final.test/"),
            ),
            patch("trafilatura.extract", return_value=payload),
        ):
            result = fetch(
                url="https://test.invalid/page",
                output_format="json",
                include_metadata=True,
            )

        data = json.loads(result)
        assert data["metadata"]["title"] == "Hello"
        assert data["metadata"]["author"] == "Ada"
        assert data["metadata"]["date"] == "2026-01-01"

    def test_fetch_loopback_failure_has_actionable_message(self):
        from otdev.tools.webfetch import fetch

        with (
            patch("otdev.tools.webfetch._require_trafilatura"),
            patch("otdev.tools.webfetch._fetch_url_cached", return_value=(None, None, "http://final.test/")),
        ):
            result = fetch(url="http://127.0.0.1:18888/injection-web.html")

        assert "loopback" in result.lower()
        assert "restricted" in result.lower() or "block" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_create_config_applies_download_cap():
    from otdev.tools.webfetch import _create_config

    config = _create_config(10.0)
    assert config.get("DEFAULT", "MAX_FILE_SIZE") == "20000000"
    assert config.get("DEFAULT", "DOWNLOAD_TIMEOUT") == "10"
