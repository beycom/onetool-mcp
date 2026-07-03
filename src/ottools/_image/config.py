"""Configuration for the image pack."""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from ot.logging import LogEntry
from otpack import get_secret, get_tool_config


class Config(BaseModel):
    """Image pack configuration — discovered by registry."""

    model: str = Field(
        default="",
        description="Vision model to use for ask() and summary() (e.g. openai/gpt-4o-mini)",
    )
    max_edge: int = Field(
        default=1568,
        description="Maximum longest edge in pixels for in-memory model-upload resize",
    )
    session_cache_size: int = Field(
        default=10,
        description="Maximum number of images to keep in the in-memory session LRU cache",
    )
    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL (empty = inherit from top-level llm config)",
    )


def get_image_config() -> Config:
    """Load image pack configuration with top-level llm fallbacks.

    Reads ``tools.ot_image`` from onetool.yaml. Falls back to the top-level
    ``llm.base_url`` and ``llm.model`` when not explicitly set in
    ``tools.ot_image``.  The API key is always read from the ``OPENAI_API_KEY``
    secret.

    Returns:
        Fully resolved Config for the image pack.
    """
    from ot.config import get_llm_config

    config = get_tool_config("ot_image", Config)

    try:
        llm = get_llm_config()
        updates: dict[str, str] = {}
        if not config.base_url and llm.base_url:
            updates["base_url"] = llm.base_url
        if not config.model and llm.model:
            updates["model"] = llm.model
        if updates:
            config = config.model_copy(update=updates)
    except Exception as e:
        logger.warning(
            LogEntry(
                event="ot_image.config.llm_fallback_failed",
                tool="ot_image",
                configSource="llm",
                errorType=type(e).__name__,
                error=str(e),
            )
        )

    return config


def get_image_api_key() -> str | None:
    """Return the API key for vision model calls.

    Tries ``OPENAI_API_KEY`` first, then falls back to ``OT_LLM_API_KEY``
    so that a shared OpenRouter key works without duplication.
    """
    return get_secret("OPENAI_API_KEY") or get_secret("OT_LLM_API_KEY")
