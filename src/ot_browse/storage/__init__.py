"""Session storage package for browser captures.

Provides functions for managing capture sessions and saving page data.
"""

from __future__ import annotations

from .index import generate_llm_markdown
from .session import (
    create_session,
    list_sessions,
    save_capture,
    save_comprehensive_capture,
)
from .utils import clean_text, set_max_text_length

__all__ = [
    "clean_text",
    "create_session",
    "generate_llm_markdown",
    "list_sessions",
    "save_capture",
    "save_comprehensive_capture",
    "set_max_text_length",
]
