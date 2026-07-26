"""Opt-in installed-client launcher boundary tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from onetool.code.adapters import build_invocation, run_foreground
from onetool.code.domain import EnvironmentDelta, LaunchInvocation
from onetool.code.resolver import resolve_route
from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import valid_routing_config

if TYPE_CHECKING:
    from ot.config.routing import Harness

pytestmark = [pytest.mark.integration, pytest.mark.serve]


@pytest.fixture(scope="module", autouse=True)
def require_explicit_installed_client_opt_in() -> None:
    """Require explicit confirmation before probing installed harness clients."""
    if os.environ.get("ONETOOL_LIVE_CODE_CLIENTS") != "confirmed":
        pytest.skip(
            "Set ONETOOL_LIVE_CODE_CLIENTS=confirmed to probe installed Claude "
            "Code and Codex clients without sending inference requests"
        )


@pytest.mark.parametrize(
    ("harness", "route_name"),
    [
        ("claude", "claude-native"),
        ("codex", "codex-native"),
    ],
)
def test_installed_native_route_constructs_without_network(
    harness: Harness,
    route_name: str,
) -> None:
    """Installed clients satisfy the native route's version/help capabilities."""
    data = valid_routing_config()
    data["code"]["clients"]["claude"].pop("additional_arguments")
    data["code"]["clients"]["codex"].pop("additional_arguments")
    data["code"]["clients"]["codex"].pop("home_path")
    config = OneToolConfig.model_validate(data)
    route = resolve_route(
        config=config,
        harness=harness,
        model=None,
        route=route_name,
        permission="safe",
    )

    invocation = build_invocation(
        config=config,
        route=route,
        passthrough=(),
        secret_resolver=lambda _name: pytest.fail(
            "native route attempted to resolve a secret"
        ),
    )

    assert invocation.argv[0] == invocation.executable
    assert "--model" in invocation.argv


def test_foreground_boundary_uses_inherited_streams_without_inference() -> None:
    """The foreground runner preserves a local non-harness child outcome."""
    data = valid_routing_config()
    config = OneToolConfig.model_validate(data)
    route = resolve_route(
        config=config,
        harness="codex",
        model=None,
        route="codex-native",
        permission="safe",
    )
    invocation = LaunchInvocation(
        route=route,
        executable=sys.executable,
        argv=(sys.executable, "-c", "raise SystemExit(0)"),
        environment=EnvironmentDelta.create(remove=set(), set_values={}),
        working_directory=str(Path.cwd()),
    )

    return_code, _ = run_foreground(invocation=invocation)
    assert return_code == 0
