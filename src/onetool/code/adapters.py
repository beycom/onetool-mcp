"""Minimal invocation-scoped adapters for Claude Code and Codex."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import NoReturn
from urllib.parse import urlsplit

from onetool.code.domain import EnvironmentDelta, Harness, LaunchInvocation

DEFAULT_PROXY_ORIGIN = "http://127.0.0.1:8317"
INFERENCE_KEY_ENV = "CLIPROXY_INFERENCE_KEY"
BASE_URL_ENV = "CLIPROXY_BASE_URL"
_PRIVATE_PROVIDER_KEY = "ONETOOL_CODE_PROVIDER_KEY"
_PROVIDER_ID = "onetool_proxy"

_CLAUDE_CLEAN_ENV = frozenset(
    {
        INFERENCE_KEY_ENV,
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION",
        "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL",
        "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        "CLAUDE_CODE_DISABLE_1M_CONTEXT",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "DISABLE_AUTO_COMPACT",
        "DISABLE_COMPACT",
        "ENABLE_TOOL_SEARCH",
    }
)
_CODEX_CLEAN_ENV = frozenset({INFERENCE_KEY_ENV, _PRIVATE_PROVIDER_KEY})


def normalize_proxy_origin(value: str) -> str:
    """Validate and remove trailing slashes from the proxy origin."""
    if any(
        ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value
    ):
        raise ValueError(f"{BASE_URL_ENV} must not contain control characters")
    normalized = value.rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{BASE_URL_ENV} must be an HTTP(S) origin")
    return normalized


def connection_from_environment(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Read the launcher origin and required credential only from the environment."""
    values = os.environ if environment is None else environment
    origin = normalize_proxy_origin(values.get(BASE_URL_ENV, DEFAULT_PROXY_ORIGIN))
    credential = values.get(INFERENCE_KEY_ENV)
    if not credential:
        raise ValueError(f"{INFERENCE_KEY_ENV} is required")
    return origin, credential


def _toml_string(value: str) -> str:
    """Quote one invocation-scoped Codex TOML string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _claude_invocation(
    *,
    model: str,
    proxy_origin: str,
    credential: str,
    context_window: int | None,
    arguments: tuple[str, ...],
) -> LaunchInvocation:
    """Build one proxied Claude Code invocation."""
    if context_window not in {None, 200_000, 1_000_000}:
        raise ValueError("Claude context must be auto, 200k, or 1m")
    selected_model = f"{model}[1m]" if context_window == 1_000_000 else model
    set_values = {
        "ANTHROPIC_BASE_URL": proxy_origin,
        "ANTHROPIC_AUTH_TOKEN": credential,
        "ANTHROPIC_MODEL": selected_model,
        "CLAUDE_CODE_SUBAGENT_MODEL": selected_model,
    }
    if context_window == 200_000:
        set_values["CLAUDE_CODE_DISABLE_1M_CONTEXT"] = "1"
    return LaunchInvocation(
        harness="claude",
        model=model,
        proxy_origin=proxy_origin,
        argv=("claude", "--model", selected_model, *arguments),
        environment=EnvironmentDelta.create(
            remove=_CLAUDE_CLEAN_ENV,
            set_values=set_values,
        ),
    )


def _codex_invocation(
    *,
    model: str,
    proxy_origin: str,
    credential: str,
    context_window: int | None,
    arguments: tuple[str, ...],
) -> LaunchInvocation:
    """Build one invocation-scoped Codex Responses provider."""
    provider_base = f"{proxy_origin}/v1"
    overrides: tuple[tuple[str, str], ...] = (
        ("model_provider", _toml_string(_PROVIDER_ID)),
        (f"model_providers.{_PROVIDER_ID}.name", _toml_string("OneTool Proxy")),
        (f"model_providers.{_PROVIDER_ID}.base_url", _toml_string(provider_base)),
        (
            f"model_providers.{_PROVIDER_ID}.env_key",
            _toml_string(_PRIVATE_PROVIDER_KEY),
        ),
        (f"model_providers.{_PROVIDER_ID}.wire_api", _toml_string("responses")),
    )
    if context_window is not None:
        overrides += (
            ("model_context_window", str(context_window)),
            ("model_auto_compact_token_limit", str(context_window * 9 // 10)),
        )
    generated = tuple(
        token for key, value in overrides for token in ("-c", f"{key}={value}")
    )
    return LaunchInvocation(
        harness="codex",
        model=model,
        proxy_origin=proxy_origin,
        argv=("codex", *generated, "--model", model, *arguments),
        environment=EnvironmentDelta.create(
            remove=_CODEX_CLEAN_ENV,
            set_values={_PRIVATE_PROVIDER_KEY: credential},
        ),
    )


def build_invocation(
    *,
    harness: Harness,
    model: str,
    proxy_origin: str,
    credential: str,
    context_window: int | None = None,
    arguments: tuple[str, ...] = (),
) -> LaunchInvocation:
    """Build a harness invocation without config loading, discovery, or I/O."""
    if not model:
        raise ValueError("MODEL is required")
    if context_window is not None and context_window <= 0:
        raise ValueError("context window must be positive")
    builder = _claude_invocation if harness == "claude" else _codex_invocation
    return builder(
        model=model,
        proxy_origin=normalize_proxy_origin(proxy_origin),
        credential=credential,
        context_window=context_window,
        arguments=arguments,
    )


def replace_process(
    *,
    invocation: LaunchInvocation,
    parent_environment: Mapping[str, str] | None = None,
) -> NoReturn:
    """Replace OneTool with the official harness resolved through PATH."""
    parent = os.environ if parent_environment is None else parent_environment
    environment = invocation.environment.apply(parent)
    os.execvpe(invocation.executable, invocation.argv, environment)


__all__ = [
    "BASE_URL_ENV",
    "DEFAULT_PROXY_ORIGIN",
    "INFERENCE_KEY_ENV",
    "build_invocation",
    "connection_from_environment",
    "normalize_proxy_origin",
    "replace_process",
]
