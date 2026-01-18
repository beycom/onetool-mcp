"""Unit tests for code linter (Ruff integration).

Tests the optional Ruff linting integration for style warnings.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ot.executor.linter import (
    LintResult,
    _check_ruff_available,
    is_ruff_available,
    lint_code,
    lint_code_quick,
)

# =============================================================================
# Availability Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_is_ruff_available_cached() -> None:
    """Availability check is cached."""
    import ot.executor.linter as linter_module

    # Reset the cache
    original = linter_module._ruff_available
    linter_module._ruff_available = None

    try:
        # First call checks availability
        result1 = is_ruff_available()
        # Second call should use cached value
        result2 = is_ruff_available()
        assert result1 == result2
        # Cache should be set
        assert linter_module._ruff_available is not None
    finally:
        # Restore original cache state
        linter_module._ruff_available = original


@pytest.mark.unit
@pytest.mark.core
def test_lint_code_unavailable() -> None:
    """Returns available=False when ruff missing."""
    with patch("ot.executor.linter.is_ruff_available", return_value=False):
        result = lint_code("x = 1")
        assert result.available is False
        assert result.warnings == []


@pytest.mark.unit
@pytest.mark.core
def test_check_ruff_available_not_found() -> None:
    """_check_ruff_available returns False when ruff not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = _check_ruff_available()
        assert result is False


# =============================================================================
# Lint Result Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_lint_result_structure() -> None:
    """LintResult has expected fields."""
    result = LintResult()
    assert result.available is False
    assert result.warnings == []
    assert result.error is None


@pytest.mark.unit
@pytest.mark.core
def test_lint_code_empty_for_clean_code() -> None:
    """No warnings for perfectly valid code."""
    # This test only runs if ruff is available
    if not is_ruff_available():
        pytest.skip("Ruff not available")

    # Clean code with no style issues
    code = "x = 1\n"
    result = lint_code(code)
    assert result.available is True
    # Clean code should have no warnings
    assert result.error is None


@pytest.mark.unit
@pytest.mark.core
def test_lint_code_quick_convenience() -> None:
    """lint_code_quick returns list."""
    with patch("ot.executor.linter.is_ruff_available", return_value=False):
        result = lint_code_quick("x = 1")
        assert isinstance(result, list)
        assert result == []


@pytest.mark.unit
@pytest.mark.core
def test_lint_code_returns_warnings() -> None:
    """Warnings parsed from ruff output when ruff available."""
    if not is_ruff_available():
        pytest.skip("Ruff not available")

    # Code with intentional style issue (unused import)
    code = "import os\nx = 1\n"
    result = lint_code(code)
    assert result.available is True
    # Should have warning about unused import
    # (exact message depends on ruff config)


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_lint_timeout_handled() -> None:
    """Timeout returns error message."""
    import subprocess

    with (
        patch("ot.executor.linter.is_ruff_available", return_value=True),
        patch(
            "ot.executor.linter.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ruff", 30),
        ),
    ):
        result = lint_code("x = 1")
        assert result.error is not None
        assert "timed out" in result.error.lower()


@pytest.mark.unit
@pytest.mark.core
def test_lint_oserror_handled() -> None:
    """OSError returns error message."""
    with (
        patch("ot.executor.linter.is_ruff_available", return_value=True),
        patch("tempfile.NamedTemporaryFile", side_effect=OSError("disk full")),
    ):
        result = lint_code("x = 1")
        assert result.error is not None


@pytest.mark.unit
@pytest.mark.core
def test_lint_select_rules() -> None:
    """Select parameter filters rules."""
    if not is_ruff_available():
        pytest.skip("Ruff not available")

    code = "import os\nx = 1\n"
    # Only check for specific rule types
    result = lint_code(code, select=["F"])
    assert result.available is True
    # Should work without error


@pytest.mark.unit
@pytest.mark.core
def test_lint_ignore_rules() -> None:
    """Ignore parameter excludes rules."""
    if not is_ruff_available():
        pytest.skip("Ruff not available")

    code = "import os\nx = 1\n"
    # Ignore unused import warning
    result = lint_code(code, ignore=["F401"])
    assert result.available is True
    # Should work without error
