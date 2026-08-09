"""Small generation fixtures for focused tests."""

from __future__ import annotations

from typing import Any


def generation_config() -> dict[str, Any]:
    """Return the minimal shared CLIProxyAPI generation connection."""
    return {
        "version": 2,
        "llm": {
            "backend": "cliproxy",
            "base_url": "http://127.0.0.1:8317/v1",
            "model": "gpt-5.6-sol",
            "effort": "low",
            "timeout": 30,
            "max_tokens": 4096,
        },
    }
