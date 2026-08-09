"""Opt-in live CLIProxyAPI generation requests."""

from __future__ import annotations

import os

import pytest

from ot.config import get_config, get_secret
from ot.generation import GenerationRequest, generate, resolve_generation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.core,
    pytest.mark.network,
    pytest.mark.api,
]


@pytest.fixture(scope="module", autouse=True)
def require_live_generation_opt_in() -> None:
    """Require explicit confirmation before consuming proxy capacity."""
    if os.environ.get("ONETOOL_LIVE_CLIPROXY_LLM") != "confirmed":
        pytest.skip("Set ONETOOL_LIVE_CLIPROXY_LLM=confirmed to run live generation")


def test_live_responses_text_request() -> None:
    """Exercise the configured CLIProxy model through the shared client."""
    result = generate(
        route=resolve_generation(config=get_config()),
        request=GenerationRequest(prompt="Return exactly: onetool-live-ok"),
        secret_resolver=get_secret,
    )
    assert "onetool-live-ok" in result.content.lower()
