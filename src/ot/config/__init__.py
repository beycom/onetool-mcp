"""Centralized configuration for OneTool V2 (global-only).

This module provides a single source of truth for all configuration settings
via YAML configuration for tool discovery and settings.

Key changes from V1:
- Global-only configuration (no project configs or inheritance)
- Root-level env: section for subprocess environment variables
- Runtime variable expansion (happens in get_tool_config(), not load_config())
- Scalar defaults embedded in Pydantic models; larger prompts/templates live in package files
- Depth-limited includes (no circular detection)

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

    # For variable expansion (secrets.yaml → env: section):
    from ot.config import expand_vars

    api_url = expand_vars("https://api.service.test?key=${API_KEY}")
"""

from ot.config.loader import (
    get_config,
    get_embeddings_config,
    get_llm_config,
    get_tool_config,
    is_log_verbose,
    load_config,
)
from ot.config.loader import (
    reset as reset_config,
)
from ot.config.models import (
    McpServerConfig,
    OneToolConfig,
    SecurityConfig,
    SnippetDef,
    SnippetParam,
)
from ot.config.routing import DirectModelId, EmbeddingsConfig, LlmConfig
from ot.config.secrets import (
    expand_secrets,
    expand_vars,
    get_secret,
    get_secrets,
    load_secrets,
)
from ot.config.secrets import (
    reset as reset_secrets,
)


def reset() -> None:
    """Clear all config and secrets caches for reload.

    This is a convenience function that resets both config and secrets caches.
    Use this as part of the reload flow (called from ot.reload()).
    """
    reset_config()
    reset_secrets()


__all__ = [
    "DirectModelId",
    "EmbeddingsConfig",
    "LlmConfig",
    "McpServerConfig",
    "OneToolConfig",
    "SecurityConfig",
    "SnippetDef",
    "SnippetParam",
    "expand_secrets",
    "expand_vars",
    "get_config",
    "get_embeddings_config",
    "get_llm_config",
    "get_secret",
    "get_secrets",
    "get_tool_config",
    "is_log_verbose",
    "load_config",
    "load_secrets",
    "reset",
]
