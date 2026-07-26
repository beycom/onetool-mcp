"""Explicitly confirmed live checks for configured generation routes."""

from __future__ import annotations

import os

import pytest

from ot.config import get_config, get_secret
from ot.config.routing import (
    CLIProxyGenerationConfig,
    OpenAICompatibleGenerationConfig,
)
from ot.generation import GenerationRequest, generate, resolve_generation

pytestmark = [pytest.mark.integration, pytest.mark.serve]


def _generate_once() -> str:
    config = get_config()
    route = resolve_generation(config=config)
    result = generate(
        route=route,
        request=GenerationRequest(
            system="Return only the requested token.",
            prompt="Return exactly: onetool-live-ok",
        ),
        secret_resolver=get_secret,
        proxy_config=config.code.cliproxy if config.code is not None else None,
    )
    return result.content


def test_confirmed_subscription_generation_route() -> None:
    """Exercise CLIProxyAPI only after allowance consumption is confirmed."""
    if os.environ.get("ONETOOL_LIVE_CLIPROXY_LLM") != "confirmed":
        pytest.skip(
            "Set ONETOOL_LIVE_CLIPROXY_LLM=confirmed to consume configured "
            "subscription capacity for one bounded generation request"
        )
    if not isinstance(get_config().llm, CLIProxyGenerationConfig):
        pytest.skip("Top-level llm is not configured for CLIProxyAPI")

    assert "onetool-live-ok" in _generate_once().lower()


def test_confirmed_direct_provider_generation_route() -> None:
    """Exercise a direct provider only after possible charges are confirmed."""
    if os.environ.get("ONETOOL_LIVE_DIRECT_LLM") != "confirmed":
        pytest.skip(
            "Set ONETOOL_LIVE_DIRECT_LLM=confirmed to allow one bounded request "
            "that may incur direct provider charges"
        )
    if not isinstance(get_config().llm, OpenAICompatibleGenerationConfig):
        pytest.skip("Top-level llm is not configured for a direct provider")

    assert "onetool-live-ok" in _generate_once().lower()
