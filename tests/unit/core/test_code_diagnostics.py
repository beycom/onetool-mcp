"""Tests for bounded read-only code-launcher diagnostics."""

from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest

from onetool.code.diagnostics import (
    _probe_executable,
    collect_code_status,
    open_management_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_executable_probe_bounds_captured_output() -> None:
    def write_large_output(*_args: object, **kwargs: object) -> Mock:
        kwargs["stdout"].write(b"x" * 4097)
        return Mock(returncode=0)

    with (
        patch("onetool.code.diagnostics.shutil.which", return_value="/bin/tool"),
        patch("onetool.code.diagnostics.subprocess.run", side_effect=write_large_output),
    ):
        status = _probe_executable(name="tool", arguments=("--version",))

    assert status.version is None
    assert status.error == "version probe output exceeded the 4 KiB limit"


def test_status_collects_models_management_and_executable_versions() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            assert request.headers["Authorization"] == "Bearer secret-value"
            return httpx.Response(200, json={"data": [{"id": "gpt-5.6-sol"}]})
        assert request.url.path == "/management.html"
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"management")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    executable = Mock(path="/bin/tool", version="1.0", error=None)
    with (
        client,
        patch(
            "onetool.code.diagnostics._probe_executable",
            return_value=executable,
        ),
    ):
        status = collect_code_status(
            environment={
                "CLIPROXY_BASE_URL": "http://proxy.test/",
                "CLIPROXY_INFERENCE_KEY": "secret-value",
            },
            client=client,
        )

    assert status.ready
    assert status.proxy_origin == "http://proxy.test"
    assert status.origin_source == "environment"
    assert status.models == ("gpt-5.6-sol",)
    assert status.management_url == "http://proxy.test/management.html"
    assert status.management_reachable
    assert [request.url.path for request in requests] == [
        "/v1/models",
        "/management.html",
    ]


def test_status_missing_key_continues_without_inventory_request() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with (
        client,
        patch("onetool.code.diagnostics._probe_executable"),
    ):
        status = collect_code_status(environment={}, client=client)

    assert not status.ready
    assert not status.credential_present
    assert status.inventory_error == "CLIPROXY_INFERENCE_KEY is required"
    assert paths == ["/management.html"]


def test_status_redacts_unauthorized_inventory_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(401, content=b"secret-value")
        return httpx.Response(404, content=b"other-secret")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with (
        client,
        patch("onetool.code.diagnostics._probe_executable"),
    ):
        status = collect_code_status(
            environment={"CLIPROXY_INFERENCE_KEY": "secret-value"},
            client=client,
        )

    assert not status.ready
    assert status.inventory_error == (
        "CLIProxyAPI model discovery failed with HTTP 401"
    )
    assert "secret-value" not in repr(status)
    assert status.management_error == (
        "management page returned an unsuccessful HTTP status"
    )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (
            httpx.Response(
                200,
                headers={"Content-Length": str(1_048_577)},
                content=b"{}",
            ),
            "1 MiB",
        ),
    ],
)
def test_status_reports_malformed_and_oversized_inventory(
    response: httpx.Response,
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return response
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client, patch("onetool.code.diagnostics._probe_executable"):
        status = collect_code_status(
            environment={"CLIPROXY_INFERENCE_KEY": "secret-value"},
            client=client,
        )

    assert not status.ready
    assert status.inventory_error is not None
    assert message in status.inventory_error


def test_status_reports_unreachable_inventory_and_continues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            raise httpx.ConnectError("secret-value", request=request)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client, patch("onetool.code.diagnostics._probe_executable"):
        status = collect_code_status(
            environment={"CLIPROXY_INFERENCE_KEY": "secret-value"},
            client=client,
        )

    assert not status.ready
    assert status.management_reachable
    assert status.inventory_error == (
        "CLIProxyAPI inference endpoint is unavailable at http://127.0.0.1:8317"
    )
    assert "secret-value" not in repr(status)


def test_management_url_open_is_explicit_and_handles_browser_errors() -> None:
    with patch(
        "onetool.code.diagnostics.webbrowser.open",
        return_value=True,
    ) as browser:
        assert open_management_url("http://proxy.test/management.html")
    browser.assert_called_once_with("http://proxy.test/management.html", new=2)

    with patch(
        "onetool.code.diagnostics.webbrowser.open",
        side_effect=webbrowser_error(),
    ):
        assert not open_management_url("http://proxy.test/management.html")


def webbrowser_error() -> Exception:
    """Return the concrete browser exception without importing platform code."""
    import webbrowser

    return webbrowser.Error("failed")
