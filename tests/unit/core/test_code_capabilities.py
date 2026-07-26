"""Tests for bounded installed-client capability checks."""

from __future__ import annotations

import sys
import time
from unittest.mock import patch

import pytest

from onetool.code import adapters
from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import valid_routing_config

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_capability_timeout_terminates_child_after_stdout_closes() -> None:
    """A client cannot evade the deadline by closing output before hanging."""
    started = time.monotonic()
    with (
        patch("onetool.code.adapters._CAPABILITY_TIMEOUT", 0.05),
        pytest.raises(ValueError, match="timed out"),
    ):
        adapters.run_capability_command(
            (
                sys.executable,
                "-c",
                "import os, time; os.close(1); time.sleep(10)",
            )
        )

    assert time.monotonic() - started < 2


@pytest.mark.parametrize(
    ("output", "constraint", "expected"),
    [
        ("2.1.211 (Claude Code)", ">=2.1.0", "2.1.211"),
        ("codex-cli 0.200.0", ">=0.145.0", "0.200.0"),
        ("codex-cli 1.0.0", None, "1.0.0"),
    ],
)
def test_configured_version_accepts_matching_and_newer_clients(
    output: str,
    constraint: str | None,
    expected: str,
) -> None:
    """Fixture versions are provenance, not exact runtime pins."""
    with patch(
        "onetool.code.adapters.run_capability_command",
        return_value=output,
    ):
        installed = adapters._check_configured_version(
            executable="/installed/client",
            configured=constraint,
        )
    assert str(installed) == expected


def test_configured_version_rejects_nonmatching_client() -> None:
    """An explicit user constraint fails before launch when unsatisfied."""
    with (
        patch(
            "onetool.code.adapters.run_capability_command",
            return_value="codex-cli 0.100.0",
        ),
        pytest.raises(ValueError, match="does not satisfy"),
    ):
        adapters._check_configured_version(
            executable="/installed/codex",
            configured=">=0.145.0",
        )


def test_unparseable_version_is_rejected() -> None:
    """Unknown installed version output does not establish a capability."""
    with (
        patch(
            "onetool.code.adapters.run_capability_command",
            return_value="development build",
        ),
        pytest.raises(ValueError, match="Could not parse"),
    ):
        adapters._check_configured_version(
            executable="/installed/client",
            configured=None,
        )


def test_selected_help_capability_is_required() -> None:
    """A route fails when the installed harness lacks its exact adapter flag."""
    config = OneToolConfig.model_validate(valid_routing_config())
    assert config.code is not None
    route = config.code.routes["claude-sol"]
    with (
        patch(
            "onetool.code.adapters.run_capability_command",
            return_value="Usage: claude --model MODEL",
        ),
        pytest.raises(ValueError, match="--settings"),
    ):
        adapters._check_help_capabilities(
            executable="/installed/claude",
            harness="claude",
            route=route,
            permission="safe",
        )
