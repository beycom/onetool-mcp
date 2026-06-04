"""Local display service for user-visible OneTool artifacts."""

from __future__ import annotations

__all__ = [
    "clear_messages",
    "focus_message",
    "get_message",
    "get_payload_view",
    "get_status",
    "list_messages",
    "show_message",
]


def __getattr__(name: str) -> object:
    """Load service re-exports lazily to avoid admin/display import cycles."""
    if name not in __all__:
        raise AttributeError(name)
    from ot.display import service

    return getattr(service, name)
