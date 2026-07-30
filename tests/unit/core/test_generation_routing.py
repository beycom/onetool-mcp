"""Behavioral tests for shared generation routing and HTTP adapters."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ot.config import OneToolConfig
from ot.generation.client import generate, reset_http_client
from ot.generation.domain import GenerationError, GenerationRequest
from ot.generation.resolver import resolve_generation
from tests.unit.core.routing_fixtures import generation_config

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _config() -> OneToolConfig:
    return OneToolConfig.model_validate(generation_config())


def _responses_result() -> dict[str, Any]:
    return {
        "output_text": "ok",
        "usage": {
            "input_tokens": 2,
            "output_tokens": 1,
            "total_tokens": 3,
        },
    }


def test_resolution_uses_configured_wire_identity_without_discovery() -> None:
    route = resolve_generation(config=_config())

    assert route.model_id == "gpt-5.6-sol"
    assert route.request_model_id == "sol-wire"
    assert route.base_url == "http://127.0.0.1:8317"
    assert route.secret_name == "CLIPROXY_INFERENCE_KEY"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"required_modalities": frozenset({"image"})}, "modalities"),
        ({"structured_output": "json_schema", "model": "terra"}, "json_schema"),
        ({"effort": "low", "model": "terra"}, "does not support"),
    ],
)
def test_capability_failures_happen_before_network(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(GenerationError, match=message):
        resolve_generation(config=_config(), **kwargs)


def test_responses_request_is_bounded_normalized_and_discovery_free() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = json.loads(request.content)
        assert request.url == "http://127.0.0.1:8317/v1/responses"
        assert request.headers["Authorization"] == "Bearer secret-value"
        assert payload["model"] == "sol-wire"
        assert payload["reasoning"] == {"effort": "low"}
        assert payload["max_output_tokens"] == 4096
        return httpx.Response(200, json=_responses_result())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = generate(
            route=resolve_generation(config=_config()),
            request=GenerationRequest(prompt="Return ok"),
            secret_resolver=lambda _name: "secret-value",
            client=client,
        )

    assert result.content == "ok"
    assert result.usage.total_tokens == 3
    assert [request.method for request in seen] == ["POST"]


def test_chat_images_and_structured_output_use_verified_shape() -> None:
    data = generation_config()
    data["llm"].update(
        {
            "backend": "openai_compatible",
            "interface": "chat_completions",
            "model": "terra",
            "base_url": "https://llm.internal.test/api",
            "secret_name": "DIRECT_LLM_KEY",
        }
    )
    config = OneToolConfig.model_validate(data)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://llm.internal.test/api/v1/chat/completions"
        assert payload["model"] == "gpt-5.6-terra"
        assert payload["response_format"] == {"type": "json_object"}
        content = payload["messages"][-1]["content"]
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = generate(
            route=resolve_generation(
                config=config,
                required_modalities=frozenset({"text", "image"}),
                structured_output="json_object",
            ),
            request=GenerationRequest(
                prompt="Inspect",
                images=(b"png",),
                structured_output="json_object",
            ),
            secret_resolver=lambda name: (
                "direct-secret" if name == "DIRECT_LLM_KEY" else None
            ),
            client=client,
        )

    assert result.content == '{"ok":true}'


def test_missing_secret_and_transport_failure_are_redacted() -> None:
    route = resolve_generation(config=_config())
    with pytest.raises(GenerationError, match="CLIPROXY_INFERENCE_KEY"):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: None,
        )

    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-value")

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(GenerationError, match="unavailable") as error,
    ):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "secret-value",
            client=client,
        )
    assert "secret-value" not in str(error.value)


def test_response_size_and_json_shape_are_rejected() -> None:
    route = resolve_generation(config=_config())
    oversized = httpx.Response(
        200,
        headers={"Content-Length": str(8 * 1_048_576 + 1)},
        content=b"{}",
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: oversized)
    ) as client, pytest.raises(GenerationError, match="8 MiB"):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "key",
            client=client,
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"not-json")
        )
    ) as client, pytest.raises(GenerationError, match="invalid JSON"):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "key",
            client=client,
        )


def test_production_requests_reuse_lazy_http_client() -> None:
    client = MagicMock(spec=httpx.Client)
    stream = client.stream.return_value.__enter__.return_value
    stream.status_code = 200
    stream.headers = {}
    stream.iter_bytes.return_value = [json.dumps(_responses_result()).encode()]
    route = resolve_generation(config=_config())

    reset_http_client()
    try:
        with patch("ot.generation.client.httpx.Client", return_value=client) as factory:
            for _ in range(2):
                result = generate(
                    route=route,
                    request=GenerationRequest(prompt="hello"),
                    secret_resolver=lambda _name: "key",
                )
                assert result.content == "ok"
            assert factory.call_count == 1
    finally:
        reset_http_client()

    assert client.stream.call_count == 2
    client.close.assert_called_once_with()
