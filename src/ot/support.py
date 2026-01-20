"""Centralized support information for OneTool.

Single source of truth for donation/support links, messages, and version.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

# Support URLs
KOFI_URL = "https://ko-fi.com/gavinlas"
KOFI_HANDLE = "gavinlas"

# Support messages
SUPPORT_MESSAGE = "If you find OneTool useful, please consider supporting development!"
SUPPORT_MESSAGE_SHORT = "Support OneTool development"

# For HTML reports
SUPPORT_HTML_TITLE = "Support OneTool"
SUPPORT_HTML_MESSAGE = "If you find this project useful, please consider buying me a coffee!"
SUPPORT_HTML_BUTTON_TEXT = "Buy me a coffee on Ko-fi"


def get_support_dict() -> dict[str, str]:
    """Get support info as a dictionary for JSON output.

    Returns:
        Dict with support URLs and messages
    """
    return {
        "message": SUPPORT_MESSAGE,
        "kofi_url": KOFI_URL,
    }


def get_startup_message() -> str:
    """Get support message for server startup logs.

    Returns:
        Formatted startup message with support link
    """
    return f"{SUPPORT_MESSAGE_SHORT}: {KOFI_URL}"


def get_version() -> str:
    """Get OneTool package version.

    Returns:
        Version string, or "dev" if not installed as a package.
    """
    try:
        return version("onetool")
    except PackageNotFoundError:
        return "dev"
