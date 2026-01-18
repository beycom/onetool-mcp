"""Unit tests for the shared HTTP client.

Tests the http_get() function for:
- Successful JSON responses
- Successful text responses
- HTTP error handling
- Request error handling
- LogSpan integration
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


@pytest.mark.unit
@pytest.mark.core
def test_http_get_json_response() -> None:
    """http_get returns parsed JSON for application/json content type."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"key": "value"}
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        success, result = http_get("https://api.example.com/data")

        assert success is True
        assert result == {"key": "value"}


@pytest.mark.unit
@pytest.mark.core
def test_http_get_text_response() -> None:
    """http_get returns text for non-JSON content types."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = "Hello, World!"
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        success, result = http_get("https://api.example.com/text")

        assert success is True
        assert result == "Hello, World!"


@pytest.mark.unit
@pytest.mark.core
def test_http_get_with_params_and_headers() -> None:
    """http_get passes params and headers to httpx."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {}
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_get = mock_client.return_value.__enter__.return_value.get
        mock_get.return_value = mock_response

        http_get(
            "https://api.example.com/search",
            params={"q": "test"},
            headers={"Authorization": "Bearer token"},
        )

        mock_get.assert_called_once_with(
            "https://api.example.com/search",
            params={"q": "test"},
            headers={"Authorization": "Bearer token"},
        )


@pytest.mark.unit
@pytest.mark.core
def test_http_get_http_status_error() -> None:
    """http_get returns error message for HTTP status errors."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_get = mock_client.return_value.__enter__.return_value.get
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        success, result = http_get("https://api.example.com/missing")

        assert success is False
        assert "HTTP error (404)" in result
        assert "Not Found" in result


@pytest.mark.unit
@pytest.mark.core
def test_http_get_request_error() -> None:
    """http_get returns error message for request errors."""
    from ot.http_client import http_get

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_get = mock_client.return_value.__enter__.return_value.get
        mock_get.side_effect = httpx.RequestError("Connection refused")

        success, result = http_get("https://api.example.com/data")

        assert success is False
        assert "Request failed" in result


@pytest.mark.unit
@pytest.mark.core
def test_http_get_with_timeout() -> None:
    """http_get uses provided timeout."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {}
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        http_get("https://api.example.com/data", timeout=60.0)

        mock_client.assert_called_once_with(timeout=60.0)


@pytest.mark.unit
@pytest.mark.core
def test_http_get_default_timeout() -> None:
    """http_get uses default 30s timeout when not specified."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {}
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        http_get("https://api.example.com/data")

        mock_client.assert_called_once_with(timeout=30.0)


@pytest.mark.unit
@pytest.mark.core
def test_http_get_with_log_span() -> None:
    """http_get creates LogSpan when log_span is provided."""
    from ot.http_client import http_get

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"result": "ok"}
    mock_response.status_code = 200

    with patch("ot.http_client.httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        with patch("ot.logging.LogSpan") as mock_span_class:
            mock_span = MagicMock()
            mock_span_class.return_value = mock_span

            success, _ = http_get(
                "https://api.example.com/data",
                log_span="test.fetch",
                log_data={"key": "value"},
            )

            assert success is True
            mock_span_class.assert_called_once_with(span="test.fetch", key="value")
            mock_span.__enter__.assert_called_once()
            mock_span.__exit__.assert_called_once()
