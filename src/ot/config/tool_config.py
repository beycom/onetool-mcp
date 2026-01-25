"""Runtime tool configuration accessor.

This module provides the primary interface for tools to access their
configuration at runtime. Tools call get_tool_config() with their pack
name and optional Config schema class.

Example usage in a tool file:
    from pydantic import BaseModel, Field

    pack = "brave"

    class Config(BaseModel):
        timeout: float = Field(default=60.0, ge=1.0, le=300.0)

    def search(query: str) -> str:
        from ot.config.tool_config import get_tool_config
        config = get_tool_config("brave", Config)
        # config.timeout is typed and validated
        ...
"""

from __future__ import annotations

from typing import Any, TypeVar, overload

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@overload
def get_tool_config(pack: str, schema: type[T]) -> T: ...


@overload
def get_tool_config(pack: str, schema: None = None) -> dict[str, Any]: ...


def get_tool_config(
    pack: str, schema: type[T] | None = None
) -> T | dict[str, Any]:
    """Get configuration for a tool pack.

    Args:
        pack: Pack name (e.g., "brave", "ground", "context7")
        schema: Optional Pydantic model class to validate and return typed config.
                If provided, returns an instance of the schema with merged values.
                If None, returns raw config dict.

    Returns:
        If schema provided: Instance of schema with config values merged
        If no schema: Dict with raw config values (empty dict if not configured)

    Example:
        # With schema (recommended for type safety)
        class Config(BaseModel):
            timeout: float = 60.0

        config = get_tool_config("brave", Config)
        print(config.timeout)  # typed as float

        # Without schema (raw dict)
        raw = get_tool_config("brave")
        print(raw.get("timeout", 60.0))
    """
    # Get raw config values for this pack
    raw_config = _get_raw_config(pack)

    if schema is None:
        return raw_config

    # Validate and return typed config instance
    try:
        return schema.model_validate(raw_config)
    except Exception:
        # If validation fails, return defaults from schema
        return schema()


def _get_raw_config(pack: str) -> dict[str, Any]:
    """Get raw config dict for a pack from loaded configuration.

    This function handles both typed tools.X fields and extra fields
    allowed via model_config. It supports:
    1. Typed tools.X fields (e.g., tools.stats)
    2. Extra fields for tool packs (e.g., tools.brave)

    Args:
        pack: Pack name (e.g., "brave", "ground")

    Returns:
        Raw config dict for the pack, or empty dict if not configured
    """
    from ot.config.loader import get_config

    try:
        config = get_config()
    except Exception:
        # Config not loaded yet - return empty dict
        return {}

    # Get the tools section
    tools = config.tools

    # First check for typed attribute (e.g., tools.stats)
    if hasattr(tools, pack):
        pack_config = getattr(tools, pack)
        if hasattr(pack_config, "model_dump"):
            return pack_config.model_dump()
        # Handle raw dict from extra fields
        if isinstance(pack_config, dict):
            return pack_config
        return {}

    # Check model_extra for dynamically allowed fields
    if hasattr(tools, "model_extra") and tools.model_extra:
        extra = tools.model_extra
        if pack in extra:
            pack_data = extra[pack]
            if isinstance(pack_data, dict):
                return pack_data
            return {}

    return {}
