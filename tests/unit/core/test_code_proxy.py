"""Tests for bounded authenticated CLIProxyAPI model discovery."""

from __future__ import annotations

import httpx
import pytest

from onetool.code.proxy import DiscoveredModel, ModelDiscovery, ProxyDiscoveryError

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _discovery(handler: httpx.MockTransport) -> tuple[ModelDiscovery, httpx.Client]:
    client = httpx.Client(transport=handler)
    return (
        ModelDiscovery(
            proxy_origin="http://proxy.test/",
            credential="secret-value",
            client=client,
        ),
        client,
    )


def test_discovery_performs_one_authenticated_bounded_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url == "http://proxy.test/v1/models"
        assert request.headers["Authorization"] == "Bearer secret-value"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openrouter/z-ai/glm-5.2", "owned_by": "openrouter"},
                    {"id": "codex-oauth/gpt-5.6-luna", "owned_by": " openai "},
                ]
            },
        )

    discovery, client = _discovery(httpx.MockTransport(handler))
    with client:
        assert discovery.models() == (
            DiscoveredModel(id="codex-oauth/gpt-5.6-luna", provider="openai"),
            DiscoveredModel(
                id="openrouter/z-ai/glm-5.2",
                provider="openrouter",
            ),
        )
    assert len(requests) == 1


@pytest.mark.parametrize("owned_by", [None, "", "   ", 42, "bad\nprovider"])
def test_discovery_treats_invalid_provider_as_unavailable(owned_by: object) -> None:
    response = httpx.Response(
        200,
        json={"data": [{"id": "gpt-5.6-luna", "owned_by": owned_by}]},
    )
    discovery, client = _discovery(httpx.MockTransport(lambda _request: response))

    with client:
        assert discovery.models() == (
            DiscoveredModel(id="gpt-5.6-luna", provider=None),
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401, content=b"secret-value"), "HTTP 401"),
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (httpx.Response(200, json={"models": []}), "data list"),
        (httpx.Response(200, json={"data": [{"id": ""}]}), "invalid id"),
        (httpx.Response(200, json={"data": [{"id": "model\nnext"}]}), "invalid id"),
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
def test_discovery_failures_are_bounded_and_redacted(
    response: httpx.Response,
    message: str,
) -> None:
    discovery, client = _discovery(httpx.MockTransport(lambda _request: response))
    with client, pytest.raises(ProxyDiscoveryError, match=message) as error:
        discovery.models()
    assert "secret-value" not in str(error.value)
