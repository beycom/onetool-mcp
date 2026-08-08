"""Opt-in real proxied requests through both official harnesses."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.core,
    pytest.mark.network,
    pytest.mark.api,
]


@pytest.fixture(scope="module", autouse=True)
def require_live_harness_opt_in() -> None:
    """Require explicit confirmation and installed harnesses."""
    if os.environ.get("ONETOOL_LIVE_CODE_HARNESSES") != "confirmed":
        pytest.skip(
            "Set ONETOOL_LIVE_CODE_HARNESSES=confirmed to run real harness requests"
        )
    for executable in ("onetool", "claude", "codex"):
        if shutil.which(executable) is None:
            pytest.fail(f"Required executable is not installed: {executable}")
    if not os.environ.get("CLIPROXY_INFERENCE_KEY"):
        pytest.fail("CLIPROXY_INFERENCE_KEY is required")
    if not os.environ.get("ONETOOL_LIVE_CODE_MODEL"):
        pytest.fail("ONETOOL_LIVE_CODE_MODEL is required")


@pytest.mark.parametrize(
    ("harness", "arguments"),
    [
        ("claude", ("-p", "Return exactly: onetool-harness-live-ok")),
        (
            "codex",
            (
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "Return exactly: onetool-harness-live-ok",
            ),
        ),
    ],
)
def test_real_proxied_harness_request(
    harness: str,
    arguments: tuple[str, ...],
) -> None:
    """Complete one bounded non-interactive request through each harness."""
    model = os.environ["ONETOOL_LIVE_CODE_MODEL"]
    result = subprocess.run(
        ["onetool", "code", harness, model, *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env=os.environ.copy(),
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output[-2000:]
    assert "onetool-harness-live-ok" in output.lower()
    assert os.environ["CLIPROXY_INFERENCE_KEY"] not in output
