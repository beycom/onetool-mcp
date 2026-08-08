"""Opt-in live CLIProxyAPI generation requests."""

from __future__ import annotations

import base64
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


@pytest.mark.parametrize(
    "generation_request",
    [
        GenerationRequest(prompt="Return exactly: onetool-live-ok"),
        GenerationRequest(
            prompt="Return an object with ok=true",
            structured_output="json_object",
        ),
        GenerationRequest(
            prompt="Describe the attached one-pixel image in one word",
            images=(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
                    "/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
                ),
            ),
        ),
    ],
)
def test_live_responses_request_shapes(generation_request: GenerationRequest) -> None:
    """Exercise text, structured, and image input through one shared client."""
    result = generate(
        route=resolve_generation(config=get_config()),
        request=generation_request,
        secret_resolver=get_secret,
    )
    assert result.content
