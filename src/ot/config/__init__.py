"""Centralized configuration for OneTool.

This module provides a single source of truth for all configuration settings
via YAML configuration for tool discovery and settings.

Usage:
    from ot.config import get_config, load_config

    config = get_config()
    print(config.log_level)
    print(config.tools_dir)
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

__all__ = [
    "McpServerConfig",
    "OneToolConfig",
    "SnippetDef",
    "SnippetParam",
    "get_config",
    "get_secret",
    "get_secrets",
    "is_log_verbose",
    "load_config",
    "load_secrets",
]
