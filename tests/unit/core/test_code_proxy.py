"""Tests for bounded inference-only CLIProxyAPI discovery."""

from __future__ import annotations

import json

import httpx
import pytest

from onetool.code.proxy import ModelDiscovery, ProxyDiscoveryError
from ot.config.routing import CLIProxyConnectionConfig

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _config() -> CLIProxyConnectionConfig:
    """Return a loopback inference connection."""
    return CLIProxyConnectionConfig(
        base_url="http://127.0.0.1:8317",
        secret_name="CLIPROXY_INFERENCE_KEY",
        connect_timeout=1,
        request_timeout=2,
        model_cache_ttl=30,
    )


def test_discovery_uses_exact_inference_path_and_bearer_auth() -> None:
    """Discovery calls only the authenticated inference models endpoint."""
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["authorization"] = request.headers["Authorization"]
        return httpx.Response(200, json={"data": [{"id": "sol"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    discovery = ModelDiscovery(config=_config(), secret="fixture-secret", client=client)

    assert discovery.validate("sol") == "sol"
    assert observed == {
        "path": "/v1/models",
        "authorization": "Bearer fixture-secret",
    }


def test_discovery_cache_is_finite_and_reusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh results are cached only within the configured TTL."""
    calls = 0
    clock = 100.0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": [{"id": "sol"}]})

    monkeypatch.setattr("onetool.code.proxy.time.monotonic", lambda: clock)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    discovery = ModelDiscovery(config=_config(), secret="secret", client=client)

    assert discovery.models() == ("sol",)
    assert discovery.models() == ("sol",)
    assert calls == 1

    clock = 131.0
    assert discovery.models() == ("sol",)
    assert calls == 2


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401), "HTTP 401"),
        (httpx.Response(200, text="not-json"), "invalid JSON"),
        (httpx.Response(200, json={"models": []}), "data list"),
        (httpx.Response(200, json={"data": [{}]}), "invalid id"),
    ],
)
def test_invalid_responses_are_bounded_and_redacted(
    response: httpx.Response,
    message: str,
) -> None:
    """Errors expose status or shape, not response bodies or credentials."""
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: response))
    discovery = ModelDiscovery(
        config=_config(),
        secret="never-display-this",
        client=client,
    )

    with pytest.raises(ProxyDiscoveryError, match=message) as raised:
        discovery.models()
    assert "never-display-this" not in str(raised.value)
    assert "not-json" not in str(raised.value)


def test_oversized_response_is_rejected() -> None:
    """Discovery never parses an unbounded response body."""
    payload = json.dumps({"data": [], "padding": "x" * 1_048_576})
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=payload)
        )
    )

    with pytest.raises(ProxyDiscoveryError, match="1 MiB"):
        ModelDiscovery(config=_config(), secret="secret", client=client).models()


def test_ambiguous_alias_is_rejected() -> None:
    """Duplicate advertised aliases never authorize a route."""
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"id": "sol"}, {"id": "sol"}]},
            )
        )
    )

    with pytest.raises(ProxyDiscoveryError, match="ambiguous"):
        ModelDiscovery(config=_config(), secret="secret", client=client).validate("sol")


def test_missing_model_does_not_fallback() -> None:
    """An absent selected model fails without provider or model substitution."""
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"id": "other"}]},
            )
        )
    )

    with pytest.raises(ProxyDiscoveryError, match="does not advertise"):
        ModelDiscovery(config=_config(), secret="secret", client=client).validate(
            "sol",
            "gpt-5.6-sol",
        )
