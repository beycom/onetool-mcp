"""Tests for strict generation and code-routing configuration."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import (
    direct_codex_config,
    generation_config,
    proxy_launcher_config,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_minimal_proxy_and_direct_launchers_are_independently_valid() -> None:
    proxy = OneToolConfig.model_validate(proxy_launcher_config())
    direct = OneToolConfig.model_validate(direct_codex_config())

    assert proxy.code is not None and proxy.code.proxy is not None
    assert proxy.code.proxy.base_url == "http://127.0.0.1:8317"
    assert direct.code is not None and direct.code.proxy is None
    assert direct.code.direct is not None
    assert direct.code.direct.codex.profiles["openrouter"][0].id == "z-ai/glm-5.2"


def test_code_requires_at_least_one_runtime_target() -> None:
    with pytest.raises(ValidationError, match="at least one proxy route"):
        OneToolConfig.model_validate({"version": 2, "code": {}})


@pytest.mark.parametrize(
    "policy",
    [
        {"context": "standard", "auto_compact_window": 100},
        {"context": "1m", "auto_compact_window": 1_000_000},
        {"context": "large"},
    ],
)
def test_invalid_claude_context_policy_is_rejected(policy: object) -> None:
    data = proxy_launcher_config()
    data["code"]["proxy"]["routes"]["openrouter"][0]["claude"] = policy

    with pytest.raises(ValidationError):
        OneToolConfig.model_validate(data)


def test_claude_policy_is_rejected_for_direct_codex_model() -> None:
    data = direct_codex_config()
    model = data["code"]["direct"]["codex"]["profiles"]["openrouter"][0]
    model["claude"] = {"context": "1m"}

    with pytest.raises(ValidationError, match="direct Codex"):
        OneToolConfig.model_validate(data)


def test_shortcuts_are_globally_unique_and_collision_safe() -> None:
    duplicate = proxy_launcher_config()
    duplicate["code"]["proxy"]["routes"]["openrouter"][0]["shortcut"] = "sol"
    with pytest.raises(ValidationError, match="shortcut"):
        OneToolConfig.model_validate(duplicate)

    collision = proxy_launcher_config()
    collision["code"]["proxy"]["routes"]["openrouter"][0]["id"] = "sol"
    with pytest.raises(ValidationError, match="identity"):
        OneToolConfig.model_validate(collision)


def test_duplicate_model_id_within_target_is_rejected() -> None:
    data = direct_codex_config()
    models = data["code"]["direct"]["codex"]["profiles"]["openrouter"]
    models.append({"id": "z-ai/glm-5.2"})

    with pytest.raises(ValidationError, match="duplicate model ids"):
        OneToolConfig.model_validate(data)


def test_ambiguous_default_requires_exact_target() -> None:
    data = proxy_launcher_config()
    data["code"]["direct"] = {
        "codex": {
            "profiles": {
                "work": [{"id": "gpt-5.6-sol"}],
            }
        }
    }
    data["code"]["default"] = {"model": "gpt-5.6-sol"}

    with pytest.raises(ValidationError, match="multiple targets"):
        OneToolConfig.model_validate(data)

    data["code"]["default"]["profile"] = "work"
    OneToolConfig.model_validate(data)


def test_route_and_profile_default_are_mutually_exclusive() -> None:
    data = proxy_launcher_config()
    data["code"]["direct"] = direct_codex_config()["code"]["direct"]
    data["code"]["default"]["profile"] = "openrouter"

    with pytest.raises(ValidationError, match="mutually exclusive"):
        OneToolConfig.model_validate(data)


def test_removed_launcher_and_generation_metadata_fail_strictly() -> None:
    launcher = proxy_launcher_config()
    launcher["code"]["proxy"]["routes"]["openrouter"][0]["modalities"] = ["text"]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OneToolConfig.model_validate(launcher)

    generation = generation_config()
    generation["models"]["sol"]["context_window"] = 1_000_000
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OneToolConfig.model_validate(generation)


def test_cliproxy_generation_requires_proxy_connection() -> None:
    data = generation_config()
    data["code"] = direct_codex_config()["code"]

    with pytest.raises(ValidationError, match=r"requires code\.proxy"):
        OneToolConfig.model_validate(data)


@pytest.mark.parametrize(
    "argument",
    [
        "--profile=work",
        "-p",
        "-pwork",
        "--model=other",
        "-mother",
        "-cmodel_provider='other'",
    ],
)
def test_configured_owned_arguments_are_rejected(argument: str) -> None:
    data = deepcopy(direct_codex_config())
    data["code"]["clients"] = {
        "codex": {"additional_arguments": [argument]},
    }

    with pytest.raises(ValidationError, match="launcher-owned"):
        OneToolConfig.model_validate(data)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://proxy.local/path\nnext",
        "http://proxy.local/path\x01next",
        "http://proxy.local/path\x7fnext",
    ],
)
def test_proxy_base_url_rejects_control_characters(base_url: str) -> None:
    data = proxy_launcher_config()
    data["code"]["proxy"]["base_url"] = base_url

    with pytest.raises(ValidationError, match="control characters"):
        OneToolConfig.model_validate(data)
