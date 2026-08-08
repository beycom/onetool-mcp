"""Bounded adapters for backend-aware shared generation."""

from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger

from ot.generation.domain import (
    GenerationError,
    GenerationRequest,
    GenerationResult,
    GenerationUsage,
    ResolvedGeneration,
)
from ot.logging import LogEntry
from ot.utils.factory import lazy_client

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_REQUEST_BYTES = 16 * 1_048_576
_MAX_RESPONSE_BYTES = 8 * 1_048_576
_DATA_URL_PREFIX_BYTES = len("data:image/png;base64,")
_REQUEST_OVERHEAD_BYTES = 4096


def _create_http_client() -> httpx.Client:
    """Create the shared generation connection pool."""
    global _http_client
    _http_client = httpx.Client()
    return _http_client


_http_client: httpx.Client | None = None
_get_http_client = lazy_client(_create_http_client)


def reset_http_client() -> None:
    """Close and reset the shared generation connection pool."""
    global _http_client
    client = _http_client
    _http_client = None
    _get_http_client.reset()  # type: ignore[attr-defined]
    if client is not None:
        client.close()


def _data_url(payload: bytes) -> str:
    """Encode one PNG payload as an inline image data URL."""
    return f"data:image/png;base64,{base64.b64encode(payload).decode('ascii')}"


def _json_string_bytes(value: str) -> int:
    """Return the encoded size of a JSON string without allocating it."""
    size = 2  # surrounding quotes
    for character in value:
        codepoint = ord(character)
        if character in {'"', "\\"} or character in "\b\f\n\r\t":
            size += 2
        elif codepoint < 0x20 or codepoint <= 0xFFFF:
            size += 6 if codepoint >= 0x80 or codepoint < 0x20 else 1
        else:
            size += 12
    return size


def _json_value_bytes(value: Any, *, seen: set[int] | None = None) -> int:
    """Return compact JSON size without materializing container serialization."""
    if isinstance(value, str):
        return _json_string_bytes(value)
    if value is None:
        return 4
    if value is True:
        return 4
    if value is False:
        return 5
    if isinstance(value, (int, float)):
        return len(json.dumps(value))

    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        raise ValueError("Circular reference detected")

    if isinstance(value, (list, tuple)):
        seen.add(identity)
        try:
            return 2 + max(0, len(value) - 1) + sum(
                _json_value_bytes(item, seen=seen) for item in value
            )
        finally:
            seen.remove(identity)

    if isinstance(value, dict):
        seen.add(identity)
        try:
            size = 2 + max(0, len(value) - 1)
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON schema object keys must be strings")
                size += _json_string_bytes(key) + 1
                size += _json_value_bytes(item, seen=seen)
            return size
        finally:
            seen.remove(identity)

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _preflight_request_size(
    *,
    route: ResolvedGeneration,
    request: GenerationRequest,
) -> None:
    """Reject oversized requests before allocating image data URLs."""
    estimated = _REQUEST_OVERHEAD_BYTES + _json_string_bytes(route.model_id)
    estimated += _json_string_bytes(request.prompt)
    if request.system is not None:
        estimated += _json_string_bytes(request.system)
    if request.json_schema is not None:
        try:
            estimated += _json_value_bytes(request.json_schema)
        except (RecursionError, TypeError, ValueError) as exc:
            raise GenerationError("Generation JSON schema is not serializable") from exc
    estimated += sum(
        _DATA_URL_PREFIX_BYTES + 4 * ((len(image) + 2) // 3) + 128
        for image in request.images
    )
    if estimated > _MAX_REQUEST_BYTES:
        raise GenerationError("Generation request exceeded the 16 MiB limit")


def _output_token_limit(
    route: ResolvedGeneration,
    request: GenerationRequest,
) -> int | None:
    """Resolve a positive request ceiling bounded by the configured route."""
    requested = request.max_output_tokens
    if requested is not None and requested <= 0:
        raise GenerationError("Generation max_output_tokens must be positive")
    if requested is None:
        return route.max_output_tokens
    if route.max_output_tokens is None:
        return requested
    return min(requested, route.max_output_tokens)


def _structured_format(
    request: GenerationRequest, *, responses: bool
) -> dict[str, Any]:
    """Build an interface-specific structured-output format."""
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
) -> dict[str, Any]:
    """Build one bounded Responses request payload."""
    content: list[dict[str, Any]] = [{"type": "input_text", "text": request.prompt}]
    content.extend(
        {"type": "input_image", "image_url": _data_url(image)}
        for image in request.images
    )
    payload: dict[str, Any] = {
        "model": route.model_id,
        "input": [{"role": "user", "content": content}],
    }
    if request.system:
        payload["instructions"] = request.system
    if route.effort is not None:
        payload["reasoning"] = {"effort": route.effort}
    max_output_tokens = _output_token_limit(route, request)
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    output_format = _structured_format(request, responses=True)
    if output_format:
        payload["text"] = {"format": output_format}
    return payload


def _chat_payload(
    route: ResolvedGeneration,
    request: GenerationRequest,
) -> dict[str, Any]:
    """Build one bounded Chat Completions request payload."""
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
    payload: dict[str, Any] = {"model": route.model_id, "messages": messages}
    if route.effort is not None:
        payload["reasoning_effort"] = route.effort
    max_output_tokens = _output_token_limit(route, request)
    if max_output_tokens is not None:
        payload["max_completion_tokens"] = max_output_tokens
    output_format = _structured_format(request, responses=False)
    if output_format:
        payload["response_format"] = output_format
    return payload


def _read_bounded(response: httpx.Response) -> bytes:
    """Read a streamed response without exceeding the fixed body limit."""
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
    """Send exactly one authenticated generation request."""
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    if len(encoded) > _MAX_REQUEST_BYTES:
        raise GenerationError("Generation request exceeded the 16 MiB limit")
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        active_client = client or _get_http_client()
        if active_client is None:
            raise GenerationError("Generation HTTP client could not be initialized")
        resource = "responses" if route.interface == "responses" else "chat/completions"
        with active_client.stream(
            "POST",
            f"{route.base_url}/{resource}",
            headers=headers,
            content=encoded,
            timeout=httpx.Timeout(route.timeout),
        ) as response:
            return response.status_code, _read_bounded(response)
    except GenerationError:
        raise
    except httpx.HTTPError as exc:
        raise GenerationError(
            f"Generation endpoint is unavailable at {route.base_url}"
        ) from exc


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_responses(payload: Any) -> tuple[str, GenerationUsage]:
    """Normalize Responses content and usage without exposing raw payloads."""
    if not isinstance(payload, dict):
        raise GenerationError("Responses generation returned an invalid object")
    content = payload.get("output_text")
    if not isinstance(content, str):
        texts: list[str] = []
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or not isinstance(
                    item.get("content"), list
                ):
                    continue
                for part in item["content"]:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str):
                            texts.append(text)
        if not texts:
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
    """Normalize Chat Completions content and usage."""
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
) -> GenerationResult:
    """Generate once through the selected interface with no fallback."""
    secret = secret_resolver(route.secret_name)
    if not secret:
        raise GenerationError(
            f"Generation secret {route.secret_name!r} is not configured"
        )
    _preflight_request_size(route=route, request=request)
    payload = (
        _responses_payload(route, request)
        if route.interface == "responses"
        else _chat_payload(route, request)
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
            f"Generation request failed with HTTP {status} at {route.base_url}",
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
            model=route.model_id,
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


__all__ = ["generate", "reset_http_client"]
