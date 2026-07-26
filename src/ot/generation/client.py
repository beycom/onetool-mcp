"""Bounded direct-HTTP adapters for verified generation interfaces."""

from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING, Any, Protocol

import httpx
from loguru import logger

from onetool.code.proxy import ModelDiscovery, ProxyDiscoveryError
from ot.generation.domain import (
    GenerationError,
    GenerationRequest,
    GenerationResult,
    GenerationUsage,
    ResolvedGeneration,
)
from ot.logging import LogEntry

if TYPE_CHECKING:
    from collections.abc import Callable

    from ot.config.routing import CLIProxyConnectionConfig

_MAX_REQUEST_BYTES = 16 * 1_048_576
_MAX_RESPONSE_BYTES = 8 * 1_048_576


class DiscoveryFactory(Protocol):
    """Factory for the p11 inference-only model discovery service."""

    def __call__(
        self,
        *,
        config: CLIProxyConnectionConfig,
        secret: str,
        client: httpx.Client | None = None,
    ) -> ModelDiscovery: ...


def _data_url(payload: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(payload).decode('ascii')}"


def _structured_format(request: GenerationRequest, *, responses: bool) -> dict[str, Any]:
    mode = request.structured_output
    if mode is None:
        return {}
    if mode == "json_object":
        return {"type": "json_object"}
    if request.json_schema is None:
        raise GenerationError("json_schema output requires a JSON schema")
    value = {
        "type": "json_schema",
        "name": "result",
        "schema": request.json_schema,
        "strict": True,
    }
    if responses:
        return value
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "result",
            "schema": request.json_schema,
            "strict": True,
        },
    }


def _responses_payload(
    route: ResolvedGeneration,
    request: GenerationRequest,
    model: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": request.prompt}
    ]
    content.extend(
        {"type": "input_image", "image_url": _data_url(image)}
        for image in request.images
    )
    payload: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": content}],
    }
    if request.system:
        payload["instructions"] = request.system
    if route.effort is not None:
        payload["reasoning"] = {"effort": route.effort}
    if route.max_output_tokens is not None:
        payload["max_output_tokens"] = route.max_output_tokens
    output_format = _structured_format(request, responses=True)
    if output_format:
        payload["text"] = {"format": output_format}
    return payload


def _chat_payload(
    route: ResolvedGeneration,
    request: GenerationRequest,
    model: str,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    if request.images:
        content: str | list[dict[str, Any]] = [
            {"type": "text", "text": request.prompt},
            *[
                {"type": "image_url", "image_url": {"url": _data_url(image)}}
                for image in request.images
            ],
        ]
    else:
        content = request.prompt
    messages.append({"role": "user", "content": content})
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if route.effort is not None:
        payload["reasoning_effort"] = route.effort
    if route.max_output_tokens is not None:
        payload["max_completion_tokens"] = route.max_output_tokens
    output_format = _structured_format(request, responses=False)
    if output_format:
        payload["response_format"] = output_format
    return payload


def _read_bounded(response: httpx.Response) -> bytes:
    declared = response.headers.get("Content-Length")
    if (
        declared is not None
        and declared.isdigit()
        and int(declared) > _MAX_RESPONSE_BYTES
    ):
        raise GenerationError("Generation response exceeded the 8 MiB limit")
    content = bytearray()
    for chunk in response.iter_bytes():
        content.extend(chunk)
        if len(content) > _MAX_RESPONSE_BYTES:
            raise GenerationError("Generation response exceeded the 8 MiB limit")
    return bytes(content)


def _request(
    *,
    route: ResolvedGeneration,
    payload: dict[str, Any],
    secret: str,
    client: httpx.Client | None,
) -> tuple[int, bytes]:
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    if len(encoded) > _MAX_REQUEST_BYTES:
        raise GenerationError("Generation request exceeded the 16 MiB limit")
    resource = "responses" if route.interface == "responses" else "chat/completions"
    versioned_base = (
        route.base_url
        if route.base_url.rstrip("/").endswith("/v1")
        else f"{route.base_url}/v1"
    )
    timeout = httpx.Timeout(route.timeout)
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def send(active: httpx.Client) -> tuple[int, bytes]:
        with active.stream(
            "POST",
            f"{versioned_base}/{resource}",
            headers=headers,
            content=encoded,
            timeout=timeout,
        ) as response:
            return response.status_code, _read_bounded(response)

    try:
        if client is not None:
            return send(client)
        with httpx.Client(timeout=timeout) as owned:
            return send(owned)
    except GenerationError:
        raise
    except httpx.HTTPError as exc:
        raise GenerationError(
            f"Generation endpoint is unavailable at {route.base_url}; "
            "check the selected external route"
        ) from exc


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_responses(payload: Any) -> tuple[str, GenerationUsage]:
    if not isinstance(payload, dict):
        raise GenerationError("Responses generation returned an invalid object")
    content = payload.get("output_text")
    if not isinstance(content, str):
        texts: list[str] = []
        has_text = False
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or not isinstance(item.get("content"), list):
                    continue
                for part in item["content"]:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str):
                            has_text = True
                            texts.append(text)
        if not has_text:
            raise GenerationError("Responses generation returned no text content")
        content = "".join(texts)
    usage = payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return content, GenerationUsage(
        input_tokens=_integer(usage.get("input_tokens")),
        output_tokens=_integer(usage.get("output_tokens")),
        total_tokens=_integer(usage.get("total_tokens")),
    )


def _normalize_chat(payload: Any) -> tuple[str, GenerationUsage]:
    if not isinstance(payload, dict):
        raise GenerationError("Chat completion returned an invalid object")
    choices = payload.get("choices")
    if (
        not isinstance(choices, list)
        or not choices
        or not isinstance(choices[0], dict)
        or not isinstance(choices[0].get("message"), dict)
        or not isinstance(choices[0]["message"].get("content"), str)
    ):
        raise GenerationError("Chat completion returned no text content")
    usage = payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return choices[0]["message"]["content"], GenerationUsage(
        input_tokens=_integer(usage.get("prompt_tokens")),
        output_tokens=_integer(usage.get("completion_tokens")),
        total_tokens=_integer(usage.get("total_tokens")),
    )


def generate(
    *,
    route: ResolvedGeneration,
    request: GenerationRequest,
    secret_resolver: Callable[[str], str | None],
    client: httpx.Client | None = None,
    discovery_factory: DiscoveryFactory = ModelDiscovery,
    proxy_config: CLIProxyConnectionConfig | None = None,
) -> GenerationResult:
    """Generate once through the selected route with no retry or fallback."""
    secret = secret_resolver(route.secret_name)
    if not secret:
        raise GenerationError(
            f"Named generation secret {route.secret_name!r} is not configured"
        )
    model = route.model_id
    if route.backend == "cliproxy":
        if proxy_config is None:
            raise GenerationError("CLIProxyAPI generation requires code.cliproxy")
        discovery = discovery_factory(
            config=proxy_config,
            secret=secret,
            client=client,
        )
        try:
            model = discovery.validate(route.proxy_identity, route.model_id)
        except ProxyDiscoveryError as exc:
            raise GenerationError(
                f"CLIProxyAPI generation route is unavailable at {route.base_url}; "
                "check the external service and model alias"
            ) from exc

    payload = (
        _responses_payload(route, request, model)
        if route.interface == "responses"
        else _chat_payload(route, request, model)
    )
    started = time.monotonic()
    status, body = _request(
        route=route,
        payload=payload,
        secret=secret,
        client=client,
    )
    latency = time.monotonic() - started
    if status < 200 or status >= 300:
        raise GenerationError(
            f"Generation request failed with HTTP {status} at {route.base_url}; "
            "check the selected route and external service",
            status_code=status,
        )
    try:
        parsed: Any = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationError("Generation endpoint returned invalid JSON") from exc
    content, usage = (
        _normalize_responses(parsed)
        if route.interface == "responses"
        else _normalize_chat(parsed)
    )
    logger.info(
        LogEntry(
            event="generation.completed",
            backend=route.backend,
            interface=route.interface,
            model=route.shortcut,
            source=route.source,
            effort=route.effort,
            latencySeconds=round(latency, 3),
            outputBytes=len(content.encode()),
            inputTokens=usage.input_tokens,
            outputTokens=usage.output_tokens,
            totalTokens=usage.total_tokens,
        ).success(status)
    )
    return GenerationResult(
        content=content,
        usage=usage,
        latency_seconds=latency,
        route=route,
    )


__all__ = ["generate"]
