"""Tests for deterministic harness resolution and exact child invocations."""

from __future__ import annotations

import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import MagicMock, patch

import pytest
import yaml

from onetool.code.adapters import build_invocation, run_foreground
from onetool.code.domain import EnvironmentDelta, LaunchInvocation
from onetool.code.proxy import ProxyDiscoveryError
from onetool.code.resolver import resolve_route
from ot.config import OneToolConfig
from ot.config.loader import load_config
from tests.unit.core.routing_fixtures import valid_routing_config

if TYPE_CHECKING:
    from collections.abc import Iterator

    from onetool.code.domain import ResolvedRoute
    from ot.config.routing import (
        CLIProxyConnectionConfig,
        Harness,
        PermissionMode,
    )

pytestmark = [pytest.mark.unit, pytest.mark.core]


class FakeDiscovery:
    """Deterministic proxy model fixture."""

    created: ClassVar[list[tuple[str, str]]] = []

    def __init__(
        self,
        *,
        config: CLIProxyConnectionConfig,
        secret: str,
    ) -> None:
        self.created.append((config.base_url, secret))

    def validate(self, *identities: str) -> str:
        """Return the first requested identity."""
        return identities[0]


@pytest.fixture
def routing_config(tmp_path: Path) -> OneToolConfig:
    """Build a config whose user-owned paths exist."""
    data = valid_routing_config()
    settings = tmp_path / "settings.json"
    settings.write_text("{}")
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "openrouter.config.toml").write_text('model = "glm52"\n')
    catalog = tmp_path / "openrouter-models.json"
    catalog.write_text("{}")
    data["code"]["routes"]["claude-sol"]["settings_path"] = str(settings)
    data["code"]["clients"]["codex"]["home_path"] = str(codex_home)
    data["code"]["routes"]["codex-openrouter"]["model_catalog_path"] = str(catalog)
    return OneToolConfig.model_validate(data)


@pytest.fixture(autouse=True)
def adapter_capabilities() -> Iterator[None]:
    """Keep unit tests focused on resulting argv and environment."""
    with (
        patch(
            "onetool.code.adapters.resolve_client_executable",
            side_effect=lambda value: f"/resolved/{Path(value).name}",
        ),
        patch("onetool.code.adapters._check_configured_version"),
        patch("onetool.code.adapters._check_help_capabilities"),
    ):
        yield


def _route(
    config: OneToolConfig,
    harness: Harness,
    *,
    route: str,
    permission: PermissionMode = "safe",
) -> ResolvedRoute:
    """Resolve one fixture route."""
    return resolve_route(
        config=config,
        harness=harness,
        model=None,
        route=route,
        permission=permission,
    )


def test_native_claude_is_sanitized_without_resolving_a_secret(
    routing_config: OneToolConfig,
) -> None:
    """Native Claude keeps native auth while removing inherited gateways."""
    secret_resolver = MagicMock()
    invocation = build_invocation(
        config=routing_config,
        route=_route(routing_config, "claude", route="claude-native"),
        passthrough=("--continue",),
        secret_resolver=secret_resolver,
        discovery_factory=FakeDiscovery,
    )

    assert invocation.argv == (
        "/resolved/claude",
        "--no-chrome",
        "--model",
        "claude-sonnet-4-6",
        "--continue",
    )
    assert invocation.environment.set_values == {}
    assert {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    } <= invocation.environment.remove
    secret_resolver.assert_not_called()


def test_proxied_claude_has_one_model_and_all_slots(
    routing_config: OneToolConfig,
) -> None:
    """A proxy secret remains in the child environment and never in argv."""
    invocation = build_invocation(
        config=routing_config,
        route=_route(
            routing_config,
            "claude",
            route="claude-sol",
            permission="bypass",
        ),
        passthrough=("--continue",),
        secret_resolver=lambda _name: "proxy-secret",
        discovery_factory=FakeDiscovery,
    )

    assert invocation.argv.count("--model") == 1
    assert invocation.argv[-2:] == (
        "--dangerously-skip-permissions",
        "--continue",
    )
    assert "proxy-secret" not in invocation.argv
    assert invocation.environment.set_values == {
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8317",
        "ANTHROPIC_AUTH_TOKEN": "proxy-secret",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "sol",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "sol",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "sol",
    }
    assert invocation.redacted()["environment"] == {
        "remove": sorted(invocation.environment.remove),
        "set": sorted(invocation.environment.set_values),
    }
    assert "proxy-secret" not in str(invocation.redacted())


def test_native_codex_does_not_override_provider_or_inject_secret(
    routing_config: OneToolConfig,
) -> None:
    """The direct subscription route preserves Codex native authentication."""
    resolver = MagicMock()
    invocation = build_invocation(
        config=routing_config,
        route=_route(routing_config, "codex", route="codex-native"),
        passthrough=("--no-alt-screen",),
        secret_resolver=resolver,
        discovery_factory=FakeDiscovery,
    )

    assert invocation.argv == (
        "/resolved/codex",
        "--search",
        "--model",
        "gpt-5.6-sol",
        "--no-alt-screen",
    )
    assert routing_config.code is not None
    codex_client = routing_config.code.clients.codex
    assert codex_client is not None
    assert codex_client.home_path is not None
    assert invocation.environment.set_values == {
        "CODEX_HOME": str(Path(codex_client.home_path))
    }
    assert not any("model_provider" in token for token in invocation.argv)
    resolver.assert_not_called()


def test_default_codex_home_uses_shared_external_path_resolver(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An inherited Codex home follows the canonical external-path resolver."""
    data = valid_routing_config()
    del data["code"]["clients"]["codex"]["home_path"]
    config = OneToolConfig.model_validate(data)
    expanded_home = tmp_path / "expanded-codex-home"
    monkeypatch.setenv("CODEX_HOME", "~/custom-codex")

    with patch(
        "onetool.code.adapters.expand_path",
        return_value=expanded_home,
    ) as expand:
        invocation = build_invocation(
            config=config,
            route=_route(config, "codex", route="codex-native"),
            passthrough=(),
            secret_resolver=lambda _name: None,
            discovery_factory=FakeDiscovery,
        )

    expand.assert_called_once_with("~/custom-codex")
    assert invocation.environment.set_values == {}


def test_proxied_codex_uses_responses_and_env_key(
    routing_config: OneToolConfig,
) -> None:
    """Codex proxy configuration is invocation-scoped and secret-free in argv."""
    invocation = build_invocation(
        config=routing_config,
        route=_route(routing_config, "codex", route="codex-proxy"),
        passthrough=(),
        secret_resolver=lambda _name: "proxy-secret",
        discovery_factory=FakeDiscovery,
    )

    joined = "\n".join(invocation.argv)
    assert 'model_provider="onetool_proxy"' in joined
    assert 'model_providers.onetool_proxy.base_url="http://127.0.0.1:8317"' in joined
    assert 'model_providers.onetool_proxy.wire_api="responses"' in joined
    assert 'model_providers.onetool_proxy.env_key="ONETOOL_CODE_PROVIDER_KEY"' in joined
    assert "proxy-secret" not in joined
    assert (
        invocation.environment.set_values["ONETOOL_CODE_PROVIDER_KEY"] == "proxy-secret"
    )


def test_direct_openrouter_isolated_from_proxy_connection(
    routing_config: OneToolConfig,
) -> None:
    """Direct custom provider uses only its own endpoint and named secret."""
    requested: list[str] = []

    def resolve(name: str) -> str:
        requested.append(name)
        return "openrouter-secret"

    invocation = build_invocation(
        config=routing_config,
        route=_route(routing_config, "codex", route="codex-openrouter"),
        passthrough=(),
        secret_resolver=resolve,
        discovery_factory=FakeDiscovery,
    )

    joined = "\n".join(invocation.argv)
    assert requested == ["OPENROUTER_API_KEY"]
    assert 'base_url="https://openrouter.ai/api/v1"' in joined
    assert "--profile\nopenrouter" in joined
    assert "model_catalog_json=" in joined
    assert "http://127.0.0.1:8317" not in joined
    assert "openrouter-secret" not in joined
    assert not FakeDiscovery.created[-1:] or FakeDiscovery.created[-1][1] != (
        "openrouter-secret"
    )


def test_configured_paths_resolve_relative_to_config_directory(
    tmp_path: Path,
) -> None:
    """Launcher-owned paths follow the standard .onetool-relative contract."""
    config_dir = tmp_path / ".onetool"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text("{}")
    (config_dir / "workspace").mkdir()
    (config_dir / "codex-home").mkdir()
    (config_dir / "codex-home" / "openrouter.config.toml").write_text(
        'model = "glm52"\n'
    )
    (config_dir / "models.json").write_text("{}")

    data = valid_routing_config()
    data["code"]["clients"]["claude"]["working_directory"] = "workspace"
    data["code"]["routes"]["claude-sol"]["settings_path"] = "settings.json"
    data["code"]["clients"]["codex"]["home_path"] = "codex-home"
    data["code"]["routes"]["codex-openrouter"]["model_catalog_path"] = "models.json"
    config_path = config_dir / "onetool.yaml"
    config_path.write_text(yaml.safe_dump(data))
    config = load_config(config_path)

    claude = build_invocation(
        config=config,
        route=_route(config, "claude", route="claude-sol"),
        passthrough=(),
        secret_resolver=lambda _name: "proxy-secret",
        discovery_factory=FakeDiscovery,
    )
    codex = build_invocation(
        config=config,
        route=_route(config, "codex", route="codex-openrouter"),
        passthrough=(),
        secret_resolver=lambda _name: "openrouter-secret",
        discovery_factory=FakeDiscovery,
    )

    assert claude.working_directory == str(config_dir / "workspace")
    assert str(config_dir / "settings.json") in claude.argv
    assert codex.environment.set_values["CODEX_HOME"] == str(config_dir / "codex-home")
    assert any(str(config_dir / "models.json") in token for token in codex.argv)


@pytest.mark.parametrize(
    ("harness", "route", "argument"),
    [
        ("claude", "claude-native", "--model=other"),
        ("claude", "claude-native", "--dangerously-skip-permissions"),
        ("codex", "codex-native", "-m"),
        ("codex", "codex-native", "exec"),
    ],
)
def test_passthrough_cannot_override_route(
    routing_config: OneToolConfig,
    harness: Harness,
    route: str,
    argument: str,
) -> None:
    """Typed route ownership applies equally to passthrough tokens."""
    with pytest.raises(ValueError, match=r"launcher-owned|launch-mode"):
        build_invocation(
            config=routing_config,
            route=_route(routing_config, harness, route=route),
            passthrough=(argument,),
            secret_resolver=lambda _name: "secret",
            discovery_factory=FakeDiscovery,
        )


def test_proxy_failure_does_not_fallback(
    routing_config: OneToolConfig,
) -> None:
    """An unavailable proxy fails the selected route without another adapter."""

    class FailingDiscovery(FakeDiscovery):
        def validate(self, *_identities: str) -> str:
            raise ProxyDiscoveryError("external proxy unavailable")

    with pytest.raises(ProxyDiscoveryError, match="external proxy unavailable"):
        build_invocation(
            config=routing_config,
            route=_route(routing_config, "codex", route="codex-proxy"),
            passthrough=(),
            secret_resolver=lambda _name: "proxy-secret",
            discovery_factory=FailingDiscovery,
        )


def test_model_override_requires_route_compatibility(
    routing_config: OneToolConfig,
) -> None:
    """Model selection never silently changes provider source."""
    with pytest.raises(ValueError, match="uses openrouter"):
        resolve_route(
            config=routing_config,
            harness="claude",
            model="glm52",
            route="claude-sol",
            permission=None,
        )


def test_explicit_empty_launcher_model_does_not_use_route_default(
    routing_config: OneToolConfig,
) -> None:
    """A supplied empty model is unknown rather than an omitted override."""
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_route(
            config=routing_config,
            harness="claude",
            model="",
            route="claude-native",
            permission=None,
        )


def test_missing_binary_precedes_secret_resolution(
    routing_config: OneToolConfig,
) -> None:
    """Local client validation happens before credential or network access."""
    resolver = MagicMock()
    with (
        patch(
            "onetool.code.adapters.resolve_client_executable",
            side_effect=ValueError("missing binary"),
        ),
        pytest.raises(ValueError, match="missing binary"),
    ):
        build_invocation(
            config=routing_config,
            route=_route(routing_config, "claude", route="claude-sol"),
            passthrough=(),
            secret_resolver=resolver,
            discovery_factory=FakeDiscovery,
        )
    resolver.assert_not_called()


def test_user_owned_files_remain_byte_identical(
    routing_config: OneToolConfig,
) -> None:
    """Building Claude and Codex routes never rewrites user-owned files."""
    assert routing_config.code is not None
    codex_client = routing_config.code.clients.codex
    assert codex_client is not None
    claude_path = Path(routing_config.code.routes["claude-sol"].settings_path or "")
    catalog_path = Path(
        routing_config.code.routes["codex-openrouter"].model_catalog_path or ""
    )
    profile_path = Path(codex_client.home_path or "") / "openrouter.config.toml"
    before = {
        path: path.read_bytes() for path in (claude_path, catalog_path, profile_path)
    }

    build_invocation(
        config=routing_config,
        route=_route(routing_config, "claude", route="claude-sol"),
        passthrough=(),
        secret_resolver=lambda _name: "proxy-secret",
        discovery_factory=FakeDiscovery,
    )
    build_invocation(
        config=routing_config,
        route=_route(routing_config, "codex", route="codex-openrouter"),
        passthrough=(),
        secret_resolver=lambda _name: "openrouter-secret",
        discovery_factory=FakeDiscovery,
    )

    assert {path: path.read_bytes() for path in before} == before


def test_foreground_runner_preserves_exit_code_and_signal(
    routing_config: OneToolConfig,
) -> None:
    """Inherited-stream supervision returns exact process outcomes."""
    route = _route(routing_config, "codex", route="codex-native")
    normal = LaunchInvocation(
        route=route,
        executable=sys.executable,
        argv=(sys.executable, "-c", "raise SystemExit(7)"),
        environment=EnvironmentDelta.create(remove=set(), set_values={}),
        working_directory=None,
    )
    terminated = LaunchInvocation(
        route=route,
        executable=sys.executable,
        argv=(
            sys.executable,
            "-c",
            "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
        ),
        environment=EnvironmentDelta.create(remove=set(), set_values={}),
        working_directory=None,
    )

    normal_code, _ = run_foreground(invocation=normal)
    signal_code, _ = run_foreground(invocation=terminated)

    assert normal_code == 7
    assert signal_code == -signal.SIGTERM


def test_invocation_display_redacts_and_bounds_arguments(
    routing_config: OneToolConfig,
) -> None:
    """Dry-run metadata cannot expose secret-shaped or unbounded arguments."""
    route = _route(routing_config, "codex", route="codex-native")
    secret = f"sk-{'a' * 24}"
    invocation = LaunchInvocation(
        route=route,
        executable=sys.executable,
        argv=(
            sys.executable,
            secret,
            "x" * 600,
            *(f"argument-{index}" for index in range(130)),
        ),
        environment=EnvironmentDelta.create(remove=set(), set_values={}),
        working_directory=None,
    )

    displayed = invocation.redacted()["argv"]
    assert isinstance(displayed, list)
    assert displayed[1] == "[REDACTED:api_key]"
    assert displayed[2].endswith("…")
    assert len(displayed[2]) == 513
    assert len(displayed) == 129
    assert displayed[-1].endswith("argument(s) omitted")
