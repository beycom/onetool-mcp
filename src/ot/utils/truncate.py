"""Text truncation and error formatting utilities."""

from __future__ import annotations

import subprocess
from typing import Any

__all__ = ["format_error", "run_command", "truncate"]


def truncate(text: str, max_length: int = 4000, indicator: str = "...") -> str:
    """Truncate text to a maximum length with an indicator.

    Args:
        text: Text to truncate
        max_length: Maximum length including indicator
        indicator: String to append when truncated (default: "...")

    Returns:
        Truncated text with indicator, or original if within limit
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(indicator)] + indicator


def format_error(message: str, details: dict[str, Any] | None = None) -> str:
    """Format an error message consistently.

    Args:
        message: Main error message
        details: Optional additional details

    Returns:
        Formatted error string
    """
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        return f"Error: {message} ({detail_str})"
    return f"Error: {message}"


def run_command(
    args: list[str],
    *,
    timeout: float = 30.0,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess command with timeout.

    Args:
        args: Command and arguments
        timeout: Timeout in seconds (default: 30)
        cwd: Working directory

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        subprocess.TimeoutExpired: If command times out
    """
    result = subprocess.run(
        args,
        timeout=timeout,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr
