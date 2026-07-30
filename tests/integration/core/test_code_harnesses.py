"""Opt-in installed-client capability boundary tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from onetool.code.adapters import (
    check_client_capabilities,
    resolve_client_executable,
)

if TYPE_CHECKING:
    from ot.config.routing import Harness

pytestmark = [pytest.mark.integration, pytest.mark.core]


@pytest.fixture(scope="module", autouse=True)
def require_explicit_installed_client_opt_in() -> None:
    """Require explicit confirmation before probing installed harness clients."""
    if os.environ.get("ONETOOL_LIVE_CODE_CLIENTS") != "confirmed":
        pytest.skip(
            "Set ONETOOL_LIVE_CODE_CLIENTS=confirmed to probe installed Claude "
            "Code and Codex clients without sending inference requests"
        )


@pytest.mark.parametrize(
    ("harness", "require_profile"),
    [("claude", False), ("codex", True)],
)
def test_installed_harness_exposes_required_launcher_flags(
    harness: Harness,
    require_profile: bool,
) -> None:
    """Installed clients expose the flags used by configured launch adapters."""
    executable = resolve_client_executable(harness)

    capabilities = check_client_capabilities(
        executable=executable,
        harness=harness,
        permission="normal",
        require_proxy=True,
        require_profile=require_profile,
    )

    assert "--model" in capabilities
