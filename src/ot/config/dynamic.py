"""Dynamic tool configuration building.

This module provides dynamic configuration building for tools based on
discovered Config classes in tool files. Instead of hardcoding tool configs
in loader.py, each tool declares its own Config(BaseModel) class which is
discovered and used for validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import BaseModel, Field, create_model

if TYPE_CHECKING:
    from ot.executor.pep723 import ToolFileInfo


def build_tools_config_model(
    tool_files: list[ToolFileInfo],
) -> type[BaseModel]:
    """Generate a dynamic ToolsConfig model from discovered tool schemas.

    Creates a Pydantic model where each pack with a Config class gets
    a corresponding field. Packs without Config classes are not included.

    Args:
        tool_files: List of analyzed tool files with config_class_source

    Returns:
        A dynamically generated Pydantic model class

    Example:
        If brave_search.py has:
            class Config(BaseModel):
                timeout: float = Field(default=60.0, ge=1.0, le=300.0)

        Then build_tools_config_model returns a model with:
            class DynamicToolsConfig(BaseModel):
                brave: BraveConfig = Field(default_factory=BraveConfig)
    """
    fields: dict[str, Any] = {}
    config_classes: dict[str, type[BaseModel]] = {}

    for tool_file in tool_files:
        if not tool_file.pack or not tool_file.config_class_source:
            continue

        pack_name = tool_file.pack

        # Skip if we already processed this pack
        if pack_name in config_classes:
            continue

        try:
            # Execute the config class source to get the actual class
            config_class = _compile_config_class(
                pack_name, tool_file.config_class_source
            )
            if config_class:
                config_classes[pack_name] = config_class
                fields[pack_name] = (
                    config_class,
                    Field(default_factory=config_class),
                )
                logger.debug(f"Registered config for pack '{pack_name}'")
        except Exception as e:
            logger.warning(f"Failed to compile config for pack '{pack_name}': {e}")

    return create_model("DynamicToolsConfig", **fields)


def _compile_config_class(
    _pack_name: str, config_source: str
) -> type[BaseModel] | None:
    """Compile a Config class source into an actual class.

    Args:
        pack_name: Pack name for context
        config_source: Source code of the Config class

    Returns:
        The compiled Config class, or None if compilation fails
    """
    # Create a namespace with required imports
    namespace: dict[str, Any] = {
        "BaseModel": BaseModel,
        "Field": Field,
    }

    try:
        exec(config_source, namespace)
        config_class = namespace.get("Config")
        if config_class and isinstance(config_class, type) and issubclass(
            config_class, BaseModel
        ):
            return config_class
    except Exception:
        pass

    return None


def get_pack_config_raw(pack: str) -> dict[str, Any]:
    """Get raw config dict for a pack from loaded configuration.

    Args:
        pack: Pack name (e.g., "brave", "ground")

    Returns:
        Raw config dict for the pack, or empty dict if not configured
    """
    from ot.config.loader import get_config

    config = get_config()

    # Try to get from tools section as raw dict
    tools_dict = config.model_dump().get("tools", {})
    return tools_dict.get(pack, {})
