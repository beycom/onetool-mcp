"""Centralized configuration for OneTool.

This module provides a single source of truth for all configuration settings
via YAML configuration for tool discovery and settings.

Usage:
    from ot.config import get_config, load_config

    config = get_config()
    print(config.log_level)
    print(config.tools_dir)

    # For tools to access their configuration:
    from ot.config import get_tool_config

    class Config(BaseModel):
        timeout: float = 60.0

    config = get_tool_config("brave", Config)
"""

from ot.config.loader import (
    OneToolConfig,
    SnippetDef,
    SnippetParam,
    get_config,
    is_log_verbose,
    load_config,
)
from ot.config.mcp import McpServerConfig
from ot.config.secrets import get_secret, get_secrets, load_secrets
from ot.config.tool_config import get_tool_config

__all__ = [
    "McpServerConfig",
    "OneToolConfig",
    "SnippetDef",
    "SnippetParam",
    "get_config",
    "get_secret",
    "get_secrets",
    "get_tool_config",
    "is_log_verbose",
    "load_config",
    "load_secrets",
]
