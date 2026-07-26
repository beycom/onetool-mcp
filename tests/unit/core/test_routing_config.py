"""Tests for strict model and code-launch routing configuration."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
import yaml
from pydantic import ValidationError

from ot.config import OneToolConfig
from ot.config.loader import load_config
from tests.unit.core.routing_fixtures import valid_routing_config

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_valid_direct_and_proxy_routes() -> None:
    """A complete verified route matrix validates."""
    config = OneToolConfig.model_validate(valid_routing_config())

    assert config.code is not None
    assert config.code.defaults.claude_route == "claude-native"
    assert config.code.routes["codex-openrouter"].secret_name == "OPENROUTER_API_KEY"


def test_code_configuration_is_optional() -> None:
    """Normal server configuration remains valid without launcher setup."""
    config = OneToolConfig.model_validate({"version": 2})

    assert config.models == {}
    assert config.code is None


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("code", "unexpected"), True),
        (("code", "routes", "claude-native", "command"), "claude --model sol"),
        (("models", "sol", "legacy_alias"), "gpt"),
    ],
)
def test_strict_routing_fields_are_rejected(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
) -> None:
    """Unknown typed routing fields fail through normal validation."""
    data = valid_routing_config()
    target = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    config_path = tmp_path / "onetool.yaml"
    config_path.write_text(yaml.safe_dump(data))

    with pytest.raises(ValueError, match="extra_forbidden"):
        load_config(config_path)


def test_duplicate_model_identity_is_rejected() -> None:
    """Shortcuts, ids, and aliases are globally unambiguous."""
    data = valid_routing_config()
    data["models"]["glm52"]["proxy_alias"] = "sol"

    with pytest.raises(ValidationError, match="ambiguous"):
        OneToolConfig.model_validate(data)


def test_unknown_route_model_is_rejected() -> None:
    """Routes cannot rely on a hidden runtime registry."""
    data = valid_routing_config()
    data["code"]["routes"]["claude-sol"]["model"] = "missing"

    with pytest.raises(ValidationError, match="unknown model"):
        OneToolConfig.model_validate(data)


def test_route_source_must_match_model() -> None:
    """Route selection cannot substitute the configured provider source."""
    data = valid_routing_config()
    data["code"]["routes"]["claude-sol"]["source"] = "openrouter"

    with pytest.raises(ValidationError, match="does not match model source"):
        OneToolConfig.model_validate(data)


def test_unsupported_route_combination_is_rejected() -> None:
    """Only the verified harness/source/transport matrix is accepted."""
    data = valid_routing_config()
    data["code"]["routes"]["codex-openrouter"]["transport"] = "cliproxy"
    data["code"]["routes"]["codex-openrouter"].pop("base_url")
    data["code"]["routes"]["codex-openrouter"].pop("secret_name")

    with pytest.raises(ValidationError, match="unsupported"):
        OneToolConfig.model_validate(data)


def test_proxy_route_requires_external_connection() -> None:
    """A proxied route requires explicit bounded inference connection data."""
    data = valid_routing_config()
    data["code"].pop("cliproxy")

    with pytest.raises(ValidationError, match=r"code\.cliproxy is required"):
        OneToolConfig.model_validate(data)


def test_claude_subscription_proxy_requires_opt_in() -> None:
    """Claude consumer-subscription proxying is disabled by default."""
    data = valid_routing_config()
    data["code"]["routes"]["claude-subscription-proxy"] = {
        "harness": "claude",
        "source": "claude_subscription",
        "transport": "cliproxy",
        "model": "sonnet",
    }

    with pytest.raises(ValidationError, match="proxy_enabled"):
        OneToolConfig.model_validate(data)

    data["code"]["claude_subscription_proxy_enabled"] = True
    config = OneToolConfig.model_validate(data)
    assert config.code is not None
    assert config.code.routes["claude-subscription-proxy"].enabled


@pytest.mark.parametrize(
    "executable",
    ["claude --model sol", "bin/claude", "./claude", " claude"],
)
def test_invalid_executable_forms_are_rejected(executable: str) -> None:
    """Executable values never become shell command templates."""
    data = valid_routing_config()
    data["code"]["clients"]["claude"]["executable"] = executable

    with pytest.raises(ValidationError, match="executable"):
        OneToolConfig.model_validate(data)


def test_absolute_executable_path_may_contain_spaces() -> None:
    """An absolute path remains one subprocess token even when it has spaces."""
    data = valid_routing_config()
    executable = "/Applications/Claude Code/claude"
    data["code"]["clients"]["claude"]["executable"] = executable

    config = OneToolConfig.model_validate(data)

    assert config.code is not None
    assert config.code.clients.claude is not None
    assert config.code.clients.claude.executable == executable


@pytest.mark.parametrize(
    ("client", "argument"),
    [
        ("claude", "--model=sol"),
        ("claude", "--settings"),
        ("codex", "-m"),
        ("codex", "exec"),
        ("codex", "--config=model_provider='other'"),
    ],
)
def test_configured_route_owned_arguments_are_rejected(
    client: str,
    argument: str,
) -> None:
    """Configured arguments cannot make route precedence order-dependent."""
    data = valid_routing_config()
    data["code"]["clients"][client]["additional_arguments"] = [argument]

    with pytest.raises(ValidationError, match=r"launcher-owned|launch-mode"):
        OneToolConfig.model_validate(data)


def test_invalid_default_route_is_rejected() -> None:
    """Defaults must name an enabled route for the requested harness."""
    data = deepcopy(valid_routing_config())
    data["code"]["defaults"]["codex_route"] = "claude-native"

    with pytest.raises(ValidationError, match="enabled codex route"):
        OneToolConfig.model_validate(data)
