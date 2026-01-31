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


# -----------------------------------------------------------------------------
# Secrets Setup for Integration Tests
# -----------------------------------------------------------------------------

# Set OT_SECRETS_FILE for integration tests that need API keys
_project_root = Path(__file__).parent.parent
_secrets_file = _project_root / "secrets.yaml"
if _secrets_file.exists():
    os.environ.setdefault("OT_SECRETS_FILE", str(_secrets_file))


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

    This prevents user's global config (~/.onetool/config/onetool.yaml) from
    affecting unit tests. Tests use tests/.onetool/config/onetool.yaml
    which has inherit: none to prevent global config inheritance.
    """
    import ot.config.loader as loader
    from ot.executor import tool_loader

    # Reset config cache
    loader._config = None

    # Reset tool loader cache
    tool_loader._module_cache.clear()

    # Set ONETOOL_CONFIG to test config that uses inherit: none
    test_config = _project_root / "tests" / ".onetool" / "config" / "onetool.yaml"
    old_config_env = os.environ.get("ONETOOL_CONFIG")
    os.environ["ONETOOL_CONFIG"] = str(test_config)

    yield

    # Restore original env and clean up
    if old_config_env is not None:
        os.environ["ONETOOL_CONFIG"] = old_config_env
    else:
        os.environ.pop("ONETOOL_CONFIG", None)
    loader._config = None
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

    tools_dir = Path(__file__).parent.parent / "src" / "ot_tools"
    tool_funcs: dict[str, Any] = load_tool_functions(tools_dir)

    def run(code: str) -> str:
        return execute_python_code(code, tool_functions=tool_funcs)

    return run


def pytest_collection_modifyitems(items: list[Item]) -> None:
    """Skip tests that are missing required markers."""
    for item in items:
        markers = {m.name for m in item.iter_markers()}

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


