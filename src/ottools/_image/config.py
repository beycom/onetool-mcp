"""Configuration for the image pack."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ot.config.routing import GenerationSelection  # noqa: TC001 - Pydantic resolves it
from otpack import get_tool_config


class Config(BaseModel):
    """Image pack configuration — discovered by registry."""

    model_config = ConfigDict(extra="forbid")

    llm: GenerationSelection | None = Field(
        default=None,
        description="Pack-level shared generation overrides",
    )
    max_edge: int = Field(
        default=1568,
        description="Maximum longest edge in pixels for in-memory model-upload resize",
    )
    session_cache_size: int = Field(
        default=10,
        description="Maximum number of images to keep in the in-memory session LRU cache",
    )


def get_image_config() -> Config:
    """Load strict image processing and generation-selection configuration."""
    return get_tool_config("ot_image", Config)
