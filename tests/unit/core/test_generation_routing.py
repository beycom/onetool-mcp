"""Behavioral tests for backend-aware direct-model generation."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock, patch

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


def _responses_result(content: str = "ok") -> dict[str, Any]:
    return {
        "output_text": content,
        "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
    }


def _chat_result(content: str = "ok") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }


def test_resolution_uses_call_pack_root_precedence_and_direct_ids() -> None:
    root = resolve_generation(config=_config())
    pack = resolve_generation(
        config=_config(),
        pack_model="z-ai/glm-5.2",
        pack_effort="medium",
    )
    call = resolve_generation(
        config=_config(),
        pack_model="z-ai/glm-5.2",
        pack_effort="medium",
        model="new/direct-model",
        effort="high",
    )

    assert (root.model_id, root.effort) == ("gpt-5.6-sol", "low")
    assert (root.backend, root.interface) == ("cliproxy", "responses")
    assert root.secret_name == "CLIPROXY_INFERENCE_KEY"
    assert (pack.model_id, pack.effort) == ("z-ai/glm-5.2", "medium")
    assert (call.model_id, call.effort) == ("new/direct-model", "high")


def test_explicit_empty_model_does_not_fall_back() -> None:
    with pytest.raises(GenerationError, match="direct generation model ID"):
        resolve_generation(config=_config(), model="")


def test_responses_text_image_json_object_and_schema_shapes() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:8317/v1/responses"
        assert request.headers["Authorization"] == "Bearer secret-value"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_responses_result())

    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    generation_requests = (
        GenerationRequest(prompt="text"),
        GenerationRequest(prompt="image", images=(b"png",)),
        GenerationRequest(prompt="object", structured_output="json_object"),
        GenerationRequest(
            prompt="schema",
            structured_output="json_schema",
            json_schema=schema,
        ),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for request in generation_requests:
            generate(
                route=resolve_generation(config=_config()),
                request=request,
                secret_resolver=lambda _name: "secret-value",
                client=client,
            )

    assert len(requests) == 4
    assert requests[0]["model"] == "gpt-5.6-sol"
    assert requests[0]["reasoning"] == {"effort": "low"}
    assert requests[0]["max_output_tokens"] == 4096
    image_part = requests[1]["input"][0]["content"][1]
    assert image_part["image_url"].startswith("data:image/png;base64,")
    assert requests[2]["text"]["format"] == {"type": "json_object"}
    assert requests[3]["text"]["format"]["schema"] == schema


def test_default_openai_chat_text_image_json_object_and_schema_shapes() -> None:
    config = OneToolConfig.model_validate({"version": 2})
    route = resolve_generation(config=config)
    requests: list[dict[str, Any]] = []
    resolved_names: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/chat/completions"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_chat_result())

    def secret_resolver(name: str) -> str:
        resolved_names.append(name)
        return "openai-secret"

    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    generation_requests = (
        GenerationRequest(prompt="text", system="system"),
        GenerationRequest(prompt="image", images=(b"png",)),
        GenerationRequest(prompt="object", structured_output="json_object"),
        GenerationRequest(
            prompt="schema", structured_output="json_schema", json_schema=schema
        ),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for request in generation_requests:
            generate(
                route=route,
                request=request,
                secret_resolver=secret_resolver,
                client=client,
            )

    assert resolved_names == ["OPENAI_API_KEY"] * 4
    assert requests[0]["messages"][0] == {"role": "system", "content": "system"}
    assert requests[0]["max_completion_tokens"] == 4096
    image_part = requests[1]["messages"][0]["content"][1]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    assert requests[2]["response_format"] == {"type": "json_object"}
    assert requests[3]["response_format"]["json_schema"]["schema"] == schema


def test_explicit_openai_responses_uses_configured_credential_only() -> None:
    config = OneToolConfig.model_validate(
        {
            "version": 2,
            "llm": {
                "backend": "openai_compatible",
                "interface": "responses",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.4-nano",
                "secret_name": "COMPATIBLE_API_KEY",
            },
        }
    )
    names: list[str] = []

    def resolve_secret(name: str) -> str | None:
        names.append(name)
        return "compatible-secret" if name == "COMPATIBLE_API_KEY" else None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/responses"
        return httpx.Response(200, json=_responses_result())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        generate(
            route=resolve_generation(config=config),
            request=GenerationRequest(prompt="hello"),
            secret_resolver=resolve_secret,
            client=client,
        )
    assert names == ["COMPATIBLE_API_KEY"]


def test_omitted_effort_and_output_limit_stay_omitted() -> None:
    config = OneToolConfig.model_validate(
        {
            "version": 2,
            "llm": {"model": "opaque-model", "max_tokens": None},
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "reasoning_effort" not in payload
        assert "max_completion_tokens" not in payload
        return httpx.Response(200, json=_chat_result())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        generate(
            route=resolve_generation(config=config),
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "secret",
            client=client,
        )


def test_request_output_limit_is_bounded_by_route() -> None:
    config = OneToolConfig.model_validate(
        {"version": 2, "llm": {"model": "opaque-model", "max_tokens": 50}}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 50
        return httpx.Response(200, json=_chat_result())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        generate(
            route=resolve_generation(config=config),
            request=GenerationRequest(prompt="hello", max_output_tokens=100),
            secret_resolver=lambda _name: "secret",
            client=client,
        )


def test_oversized_image_is_rejected_before_base64_allocation() -> None:
    route = resolve_generation(config=_config())
    with (
        patch("ot.generation.client._MAX_REQUEST_BYTES", 64),
        patch("ot.generation.client._data_url") as data_url,
        pytest.raises(GenerationError, match="16 MiB"),
    ):
        generate(
            route=route,
            request=GenerationRequest(prompt="x", images=(b"x" * 64,)),
            secret_resolver=lambda _name: "secret",
        )

    data_url.assert_not_called()


def test_oversized_schema_is_rejected_without_serializing_container() -> None:
    route = resolve_generation(config=_config())
    schema = {"description": "x" * 64}
    with (
        patch("ot.generation.client._MAX_REQUEST_BYTES", 64),
        patch("ot.generation.client.json.dumps") as dumps,
        pytest.raises(GenerationError, match="16 MiB"),
    ):
        generate(
            route=route,
            request=GenerationRequest(
                prompt="x",
                structured_output="json_schema",
                json_schema=schema,
            ),
            secret_resolver=lambda _name: "secret",
        )

    dumps.assert_not_called()


def test_missing_fixed_secret_and_transport_failure_are_redacted() -> None:
    route = resolve_generation(config=_config())
    resolver = Mock(return_value=None)
    with pytest.raises(GenerationError, match="CLIPROXY_INFERENCE_KEY"):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=resolver,
        )
    resolver.assert_called_once_with("CLIPROXY_INFERENCE_KEY")

    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-value")

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(GenerationError, match="unavailable") as error,
    ):
        generate(
            route=route,
            request=GenerationRequest(prompt="private prompt"),
            secret_resolver=lambda _name: "secret-value",
            client=client,
        )
    assert "secret-value" not in str(error.value)
    assert "private prompt" not in str(error.value)


def test_upstream_failure_is_authoritative_and_not_retried() -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(400, content=b"raw secret response")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(GenerationError, match="HTTP 400") as error,
    ):
        generate(
            route=resolve_generation(config=_config()),
            request=GenerationRequest(prompt="unsupported image", images=(b"png",)),
            secret_resolver=lambda _name: "secret",
            client=client,
        )
    assert requests == 1
    assert "raw secret response" not in str(error.value)


def test_request_response_bounds_and_normalized_usage() -> None:
    route = resolve_generation(config=_config())
    oversized = httpx.Response(
        200,
        headers={"Content-Length": str(8 * 1_048_576 + 1)},
        content=b"{}",
    )
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: oversized)
        ) as client,
        pytest.raises(GenerationError, match="8 MiB"),
    ):
        generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "key",
            client=client,
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=_responses_result())
        )
    ) as client:
        result = generate(
            route=route,
            request=GenerationRequest(prompt="hello"),
            secret_resolver=lambda _name: "key",
            client=client,
        )
    assert result.usage.total_tokens == 3


def test_reset_closes_shared_http_pool() -> None:
    client = Mock()
    with patch("ot.generation.client._http_client", client):
        reset_http_client()
    client.close.assert_called_once_with()
