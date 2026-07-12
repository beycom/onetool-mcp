"""Pytest configuration with marker enforcement.

Every test must have:
1. A speed tier marker (smoke, unit, integration, slow)
2. A component marker (serve, pkg, core, spec, tools)

By default, tests missing a required marker FAIL collection (fail fast) — for both
the `require()`-based checks and the speed/component marker gate.

Use `--allow-skips` to gracefully skip tests with missing requirements instead.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

# Eagerly import ot.meta (and everything it pulls in, e.g. ot.meta._debug) before any
# test module runs. Several core modules do a MODULE-LEVEL `from ot.config import
# get_config` (e.g. ot/meta/_debug.py). That import statement only executes once, the
# first time the module is imported, and it binds a name in that module's own
# namespace to whatever object `ot.config.get_config` currently is.
#
# Some tests do `patch("ot.config.get_config", return_value=<mock>)` around code that
# lazily imports ot.meta for the first time (e.g. via `ot.direct_auth.direct_auth_key`
# -> `ot.meta.resolve_ot_path`). If that first import happens to land inside the
# `patch(...)` context, the importing module permanently captures the mock function
# object -- it keeps returning the stale mocked config forever after, even once the
# patch context has exited, because the module is never re-imported (see
# ot.meta._debug.get_config). This previously caused test_direct_app.py to fail only
# when run after test_direct_api.py in the same session.
#
# Forcing the import here, before collection/patching of any test module can occur,
# guarantees these modules bind the real `ot.config.get_config` and never observe a
# mocked one.
import ot.meta  # noqa: F401


@pytest.fixture(autouse=True)
def isolate_console_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep session-scoped Console body files out of the working tree."""
    from ot.console import storage

    monkeypatch.setattr(
        storage,
        "get_project_state_dir",
        lambda pack: tmp_path / ".onetool" / "state" / pack,
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom CLI options."""
    parser.addoption(
        "--allow-skips",
        action="store_true",
        default=False,
        help="Skip tests with missing requirements instead of erroring",
    )


def require(condition: bool, reason: str, request: pytest.FixtureRequest) -> None:
    """Require a condition or error/skip based on --allow-skips.

    Use in fixtures to enforce requirements:
        @pytest.fixture
        def api_key(request):
            key = get_secret("API_KEY")
            require(key is not None, "API_KEY not configured", request)
            return key

    Args:
        condition: If False, the test will error or skip
        reason: Description of missing requirement
        request: pytest request fixture (pass from your fixture)

    Raises:
        pytest.fail: If condition is False and --allow-skips is not set
        pytest.skip: If condition is False and --allow-skips is set
    """
    if condition:
        return

    allow_skips = request.config.getoption("--allow-skips", default=False)
    if allow_skips:
        pytest.skip(reason)
    else:
        pytest.fail(f"Missing requirement: {reason} (use --allow-skips to skip)")


_project_root = Path(__file__).parent.parent

if TYPE_CHECKING:
    from collections.abc import Callable

    from _pytest.nodes import Item

SPEED_MARKERS = {"smoke", "unit", "integration", "slow"}
COMPONENT_MARKERS = {"serve", "pkg", "core", "spec", "tools"}


# -----------------------------------------------------------------------------
# Config Isolation for Unit Tests
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache before each test to ensure test isolation.

    Loads the test config (tests/.onetool/onetool.yaml) so that tests
    which call get_config() without a path get the test config.
    Tests that load their own config will override this.
    """
    import ot.config.loader as loader
    from ot.config.loader import get_config
    from ot.executor import tool_loader

    # Reset caches
    loader._config = None
    loader._config_path = None
    loader._secrets_path = None
    tool_loader._module_cache.clear()

    # Pre-load test config so get_config() works without an explicit path
    test_config = _project_root / "tests" / ".onetool" / "onetool.yaml"
    if test_config.exists():
        get_config(test_config)

    yield

    # Clean up after test
    loader._config = None
    loader._config_path = None
    tool_loader._module_cache.clear()


# -----------------------------------------------------------------------------
# Executor Fixture for Unit Tests
# -----------------------------------------------------------------------------


@pytest.fixture
def executor() -> Callable[[str], str]:
    """Fixture for executing Python code directly without LLM.

    This fixture provides direct access to the OneTool execution engine,
    bypassing the LLM layer. Use it to test Python execution logic
    deterministically without API costs or variance.

    Returns:
        A function that takes Python code and returns the result string.

    Example:
        def test_basic_execution(executor):
            result = executor("1 + 1")
            assert result == "2"
    """
    from ot.executor.runner import execute_python_code
    from ot.executor.tool_loader import load_tool_functions

    tools_dir = Path(__file__).parent.parent / "src" / "ottools"
    tool_funcs: dict[str, Any] = load_tool_functions(tools_dir)

    def run(code: str) -> str:
        text, _raw, _sanitize, _fmt, _fc, _raw_ser = execute_python_code(
            code, tool_functions=tool_funcs
        )
        return text

    return run


def pytest_collection_modifyitems(config: pytest.Config, items: list[Item]) -> None:
    """Enforce required markers.

    By default a test missing a speed or component marker FAILS collection (so a
    mislabelled test can't silently vanish while CI stays green). Pass
    ``--allow-skips`` to skip such tests (with a warning) instead.
    """
    in_vscode = "VSCODE_PID" in os.environ
    allow_skips = config.getoption("--allow-skips", default=False)
    missing: list[str] = []

    for item in items:
        markers = {m.name for m in item.iter_markers()}

        if in_vscode and "integration" in markers:
            item.add_marker(
                pytest.mark.skip(reason="Integration tests skipped in VSCode")
            )
            continue

        reasons: list[str] = []
        if not markers & SPEED_MARKERS:
            reasons.append(f"speed (one of: {', '.join(sorted(SPEED_MARKERS))})")
        if not markers & COMPONENT_MARKERS:
            reasons.append(
                f"component (one of: {', '.join(sorted(COMPONENT_MARKERS))})"
            )

        if not reasons:
            continue

        detail = f"{item.nodeid} is missing {' and '.join(reasons)}"
        if allow_skips:
            warnings.warn(detail, stacklevel=1)
            item.add_marker(pytest.mark.skip(reason="Missing required marker"))
        else:
            missing.append(detail)

    if missing:
        pytest.exit(
            "Tests missing required markers (use --allow-skips to skip):\n  "
            + "\n  ".join(missing),
            returncode=1,
        )


# -----------------------------------------------------------------------------
# Shared Mock Fixtures for Tool Tests
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_http_get():
    """Mock ot.http_client.http_get for API tests.

    Usage:
        def test_npm(mock_http_get):
            mock_http_get.return_value = (True, {"dist-tags": {"latest": "1.0.0"}})
            result = npm(packages=["react"])
            assert "1.0.0" in result
    """
    with patch("ot.http_client.http_get") as mock:
        yield mock


@pytest.fixture
def mock_secrets():
    """Mock ot.config.secrets.get_secret for API key tests.

    Usage:
        def test_api_call(mock_secrets):
            mock_secrets.return_value = "test-api-key"
            # Run test that needs API key
    """
    with patch("ot.config.secrets.get_secret") as mock:
        yield mock


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for binary tool tests.

    Usage:
        def test_ripgrep_search(mock_subprocess):
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="file.py:10:match",
                stderr=""
            )
            result = search(pattern="test", path=".")
    """
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture
def mock_config():
    """Mock ot.config.get_config for configuration tests.

    Usage:
        def test_with_config(mock_config):
            mock_config.return_value.tools.ripgrep.timeout = 30
            # Run test that uses config
    """
    with patch("ot.config.get_config") as mock:
        yield mock


@pytest.fixture
def mock_proxy_manager():
    """Mock ot.proxy.get_proxy_manager for MCP server tests.

    Usage:
        def test_mcp_call(mock_proxy_manager):
            mock_proxy_manager.servers = ["chrome_devtools"]
            mock_proxy_manager.call_tool_sync.return_value = '{"success": true}'
            # Run test that calls MCP tools
    """
    with patch("otdev._inject_base.get_proxy_manager") as mock:
        proxy = MagicMock()
        proxy.servers = []
        mock.return_value = proxy
        yield proxy
