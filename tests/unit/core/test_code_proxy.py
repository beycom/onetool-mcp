"""Tests for bounded doctor-only CLIProxyAPI discovery."""

from __future__ import annotations

import httpx
import pytest

from onetool.code.proxy import ModelDiscovery, ProxyDiscoveryError
from ot.config.routing import CodeProxyConfig

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _config() -> CodeProxyConfig:
    return CodeProxyConfig(
        routes={"codex_subscription": [{"id": "gpt-5.6-sol"}]}
    )


def test_discovery_uses_exact_inference_path_and_bearer_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:8317/v1/models"
        assert request.headers["Authorization"] == "Bearer private-key"
        return httpx.Response(
            200,
            json={"data": [{"id": "gpt-5.6-sol"}, {"id": "gpt-5.6-sol"}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        models = ModelDiscovery(
            config=_config(),
            secret="private-key",
            client=client,
        ).models()

    assert models == ("gpt-5.6-sol", "gpt-5.6-sol")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401, text="private-key"), "HTTP 401"),
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (httpx.Response(200, json={"models": []}), "data list"),
        (httpx.Response(200, json={"data": [{"name": "bad"}]}), "invalid id"),
    ],
)
def test_discovery_failures_are_bounded_and_redacted(
    response: httpx.Response,
    message: str,
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: response)
    ) as client:
        discovery = ModelDiscovery(
            config=_config(),
            secret="private-key",
            client=client,
        )
        with pytest.raises(ProxyDiscoveryError, match=message) as error:
            discovery.models()

    assert "private-key" not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            200,
            headers={"Content-Length": str(1_048_577)},
            content=b"{}",
        ),
        httpx.Response(
            200,
            stream=httpx.ByteStream(b"x" * 1_048_577),
        ),
    ],
)
def test_discovery_rejects_oversized_body_before_parsing(
    response: httpx.Response,
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: response)
    ) as client, pytest.raises(ProxyDiscoveryError, match="1 MiB"):
        ModelDiscovery(config=_config(), secret="key", client=client).models()
