"""Tests for bounded diagnostic-only harness capability probes."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from onetool.code import adapters
from onetool.code.adapters import (
    check_client_capabilities,
    run_capability_command,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_capability_probe_uses_one_bounded_subprocess_run() -> None:
    output = "--model --profile --config --dangerously-bypass-approvals-and-sandbox"
    with patch(
        "onetool.code.adapters.run_capability_command",
        return_value=output,
    ) as run_capability:
        capabilities = check_client_capabilities(
            executable="/usr/bin/codex",
            harness="codex",
            permission="bypass",
            require_proxy=True,
            require_profile=True,
        )

    assert capabilities == (
        "--config",
        "--dangerously-bypass-approvals-and-sandbox",
        "--model",
        "--profile",
    )
    run_capability.assert_called_once_with(("/usr/bin/codex", "--help"))


def test_capability_command_enforces_output_and_time_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "_MAX_CAPABILITY_OUTPUT", 32)
    with pytest.raises(ValueError, match="exceeded 32 bytes"):
        run_capability_command(
            (
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x' * 33)",
            )
        )

    monkeypatch.setattr(adapters, "_CAPABILITY_TIMEOUT", 0.05)
    with pytest.raises(ValueError, match="timed out"):
        run_capability_command(
            (sys.executable, "-c", "import time; time.sleep(1)")
        )


def test_capability_probe_reports_nonzero_and_missing_flag() -> None:
    with pytest.raises(ValueError, match="exit code 2"):
        run_capability_command((sys.executable, "-c", "raise SystemExit(2)"))

    with patch(
        "onetool.code.adapters.run_capability_command",
        return_value="--model",
    ), pytest.raises(ValueError, match="--profile"):
        check_client_capabilities(
            executable="/usr/bin/codex",
            harness="codex",
            permission="normal",
            require_proxy=False,
            require_profile=True,
        )
