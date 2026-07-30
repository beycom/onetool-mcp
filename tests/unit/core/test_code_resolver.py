"""Tests for exact code-launch target resolution."""

from __future__ import annotations

import pytest

from onetool.code.resolver import compatible_models, resolve_target
from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import (
    direct_codex_config,
    proxy_launcher_config,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_exact_id_and_shortcut_resolve_without_normalization() -> None:
    config = OneToolConfig.model_validate(proxy_launcher_config())

    exact = resolve_target(
        config=config,
        harness="codex",
        model="gpt-5.6-sol",
        route=None,
        permission=None,
    )
    shortcut = resolve_target(
        config=config,
        harness="claude",
        model="glm",
        route="openrouter",
        permission="bypass",
    )

    assert (exact.kind, exact.name, exact.model.id) == (
        "route",
        "codex_subscription",
        "gpt-5.6-sol",
    )
    assert shortcut.model.claude_context == "1m"
    assert shortcut.permission == "bypass"

    with pytest.raises(ValueError, match="Unknown model"):
        resolve_target(
            config=config,
            harness="codex",
            model="GLM52",
            route=None,
            permission=None,
        )


def test_direct_profile_is_exact_and_codex_only() -> None:
    config = OneToolConfig.model_validate(direct_codex_config())

    resolved = resolve_target(
        config=config,
        harness="codex",
        model="glm",
        route=None,
        profile="openrouter",
        permission=None,
    )
    assert (resolved.kind, resolved.name, resolved.model.id) == (
        "profile",
        "openrouter",
        "z-ai/glm-5.2",
    )

    with pytest.raises(ValueError, match="only by Codex"):
        compatible_models(
            config=config,
            harness="claude",
            profile="openrouter",
        )
    with pytest.raises(ValueError, match="not configured"):
        resolve_target(
            config=config,
            harness="codex",
            model="glm",
            route=None,
            profile="OpenRouter",
            permission=None,
        )


def test_route_and_profile_are_mutually_exclusive() -> None:
    data = proxy_launcher_config()
    data["code"]["direct"] = direct_codex_config()["code"]["direct"]
    data["code"]["direct"]["codex"]["profiles"]["openrouter"][0][
        "shortcut"
    ] = "direct-glm"
    config = OneToolConfig.model_validate(data)

    with pytest.raises(ValueError, match="mutually exclusive"):
        resolve_target(
            config=config,
            harness="codex",
            model="glm",
            route="openrouter",
            profile="openrouter",
            permission=None,
        )


def test_duplicate_id_requires_exact_target() -> None:
    data = proxy_launcher_config()
    data["code"]["direct"] = {
        "codex": {
            "profiles": {
                "work": [{"id": "gpt-5.6-sol", "shortcut": "work-sol"}],
            }
        }
    }
    config = OneToolConfig.model_validate(data)

    with pytest.raises(ValueError, match="multiple targets"):
        resolve_target(
            config=config,
            harness="codex",
            model="gpt-5.6-sol",
            route=None,
            permission=None,
        )

    resolved = resolve_target(
        config=config,
        harness="codex",
        model="gpt-5.6-sol",
        route=None,
        profile="work",
        permission=None,
    )
    assert resolved.kind == "profile"


def test_defaults_and_route_compatibility_are_enforced() -> None:
    proxy = OneToolConfig.model_validate(proxy_launcher_config())
    default = resolve_target(
        config=proxy,
        harness="codex",
        model=None,
        route=None,
        permission=None,
    )
    assert default.model.id == "gpt-5.6-sol"

    with pytest.raises(ValueError, match="not supported"):
        resolve_target(
            config=proxy,
            harness="codex",
            model="sonnet",
            route="claude_subscription",
            permission=None,
        )


def test_claude_subscription_warning_is_bound_to_that_proxy_route() -> None:
    config = OneToolConfig.model_validate(proxy_launcher_config())

    warned = resolve_target(
        config=config,
        harness="claude",
        model="sonnet",
        route=None,
        permission=None,
    )
    ordinary = resolve_target(
        config=config,
        harness="claude",
        model="glm",
        route=None,
        permission=None,
    )

    assert warned.warning is not None
    assert ordinary.warning is None
