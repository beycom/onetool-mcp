"""Pytest configuration with marker enforcement.

Every test must have:
1. A speed tier marker (smoke, unit, integration, slow)
2. A component marker (serve, bench, pkg, core)

Tests missing required markers are automatically skipped.

Use `--allow-skips` to gracefully skip tests with missing requirements.
By default, tests with missing requirements will error (fail fast).
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from unittest.mock import MagicMock, patch

import pytest


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
    from _pytest.nodes import Item

SPEED_MARKERS = {"smoke", "unit", "integration", "slow"}
COMPONENT_MARKERS = {"serve", "bench", "pkg", "core", "spec", "tools"}


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
        text, _raw, _sanitize, _fmt, _fc, _display = execute_python_code(code, tool_functions=tool_funcs)
        return text

    return run


def pytest_collection_modifyitems(items: list[Item]) -> None:
    """Skip tests that are missing required markers."""
    in_vscode = "VSCODE_PID" in os.environ
    for item in items:
        markers = {m.name for m in item.iter_markers()}

        if in_vscode and "integration" in markers:
            item.add_marker(
                pytest.mark.skip(reason="Integration tests skipped in VSCode")
            )
            continue

        if not markers & SPEED_MARKERS:
            warnings.warn(
                f"Test {item.nodeid} is missing a speed marker "
                f"(one of: {', '.join(sorted(SPEED_MARKERS))})",
                stacklevel=1,
            )
            item.add_marker(pytest.mark.skip(reason="Missing speed marker"))

        if not markers & COMPONENT_MARKERS:
            warnings.warn(
                f"Test {item.nodeid} is missing a component marker "
                f"(one of: {', '.join(sorted(COMPONENT_MARKERS))})",
                stacklevel=1,
            )
            item.add_marker(pytest.mark.skip(reason="Missing component marker"))


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


