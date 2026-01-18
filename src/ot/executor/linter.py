"""Optional Ruff linting integration for OneTool.

Provides style warnings (non-blocking) using Ruff linter if installed.
Falls back gracefully if Ruff is not available.

Example:
    result = lint_code(code)
    if result.available:
        for warning in result.warnings:
            print(f"Style warning: {warning}")
"""

from __future__ import annotations

import contextlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class LintResult:
    """Result of linting operation."""

    available: bool = False  # Whether Ruff is available
    warnings: list[str] = field(default_factory=list)
    error: str | None = None  # Error message if linting failed


def _check_ruff_available() -> bool:
    """Check if Ruff is available on the system."""
    try:
        result = subprocess.run(
            ["ruff", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# Cache Ruff availability check
_ruff_available: bool | None = None


def is_ruff_available() -> bool:
    """Check if Ruff linter is available (cached)."""
    global _ruff_available
    if _ruff_available is None:
        _ruff_available = _check_ruff_available()
    return _ruff_available


def lint_code(
    code: str,
    select: list[str] | None = None,
    ignore: list[str] | None = None,
) -> LintResult:
    """Lint Python code using Ruff.

    Args:
        code: Python code to lint
        select: Rule codes to enable (e.g., ["E", "F", "W"])
        ignore: Rule codes to ignore (e.g., ["E501"])

    Returns:
        LintResult with warnings if Ruff is available
    """
    result = LintResult()

    if not is_ruff_available():
        result.available = False
        return result

    result.available = True

    # Write code to temp file for Ruff
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(code)
            temp_path = Path(f.name)

        # Build Ruff command
        cmd = ["ruff", "check", str(temp_path), "--output-format=text"]

        if select:
            cmd.extend(["--select", ",".join(select)])
        if ignore:
            cmd.extend(["--ignore", ",".join(ignore)])

        # Run Ruff
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Parse output - each line is a warning
        if proc.stdout:
            for line in proc.stdout.strip().split("\n"):
                if line.strip():
                    # Remove temp file path from output
                    warning = line.replace(str(temp_path), "<code>")
                    result.warnings.append(warning)

    except subprocess.TimeoutExpired:
        result.error = "Ruff linting timed out"
        logger.warning("Ruff linting timed out")
    except OSError as e:
        result.error = f"Failed to run Ruff: {e}"
        logger.warning(f"Failed to run Ruff: {e}")
    finally:
        # Clean up temp file
        with contextlib.suppress(NameError, OSError):
            temp_path.unlink()

    return result


def lint_code_quick(code: str) -> list[str]:
    """Quick lint that returns just the warnings list.

    Convenience function for simple use cases.

    Args:
        code: Python code to lint

    Returns:
        List of warning strings (empty if Ruff unavailable)
    """
    result = lint_code(code)
    return result.warnings
