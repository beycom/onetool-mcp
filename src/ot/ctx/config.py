"""Configuration for the ctx pack."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ot.config import get_tool_config
from ot.config.routing import DirectModelId, ReasoningEffort  # noqa: TC001


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    model_config = ConfigDict(extra="forbid")

    model: DirectModelId | None = Field(
        default=None, description="Direct model override"
    )
    effort: ReasoningEffort | None = Field(
        default=None, description="Reasoning effort override"
    )
    ttl: int = Field(
        default=3600,
        ge=0,
        description="Handle TTL in seconds (0 = no expiry)",
    )
    max_line_chars: int = Field(
        default=500,
        ge=1,
        description="Lines longer than this are truncated with a [+N chars] suffix",
    )
    ask_max_bytes: int = Field(
        default=204800,
        ge=0,
        description="Content is truncated to this size before sending to ctx.ask (bytes, 0 = no limit)",
    )


def _get_config() -> Config:
    """Get ctx pack configuration."""
    return get_tool_config("ot_context", Config)
