"""MCP server configuration for OneTool proxy.

Defines configuration for connecting to external MCP servers that are
proxied through OneTool's single `run` tool.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Use canonical early secrets loader from secrets.py (eliminates duplication)
from ot.config.secrets import get_early_secret


def expand_secrets(value: str) -> str:
    """Expand ${VAR} patterns using secrets.yaml ONLY.

    Use this for configuration values that MUST be in secrets.yaml.
    This enforces that sensitive values are stored in the gitignored secrets file,
    not in environment variables that might leak into logs or process lists.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    When to use:
        - Config file values (URLs, API keys, database connections)
        - Anywhere secrets should be explicit and fail loudly if missing

    When NOT to use:
        - Subprocess environment pass-through (use expand_subprocess_env instead)

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded from secrets.

    Raises:
        ValueError: If variable not found in secrets and no default provided.
    """
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
    missing_vars: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Read from secrets only - no os.environ
        secret_value = get_early_secret(var_name)
        if secret_value is not None:
            return secret_value
        if default_value is not None:
            return default_value
        missing_vars.append(var_name)
        return match.group(0)

    result = pattern.sub(replace, value)

    if missing_vars:
        raise ValueError(
            f"Missing variables in secrets.yaml: {', '.join(missing_vars)}. "
            f"Add them to .onetool/secrets.yaml or use ${{VAR:-default}} syntax."
        )

    return result


def expand_subprocess_env(value: str) -> str:
    """Expand ${VAR} for subprocess environment variables.

    Use this ONLY for subprocess env configuration where pass-through is needed.
    Searches: secrets.yaml first, then os.environ. Returns empty string if not found.

    This is the ONLY place where reading os.environ is allowed. This enables
    explicit pass-through of system environment variables like ${HOME}, ${PATH},
    or ${USER} to subprocesses without requiring them to be in secrets.yaml.

    When to use:
        - MCP server 'env' configuration (subprocess environment)
        - Any subprocess that needs access to system env vars

    When NOT to use:
        - Config file values (use expand_secrets instead - it enforces secrets.yaml)
        - Anything that should fail if the secret is missing

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded. Empty string if not found (silent failure).
    """
    import os

    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Secrets first
        secret_value = get_early_secret(var_name)
        if secret_value is not None:
            return secret_value
        # Then os.environ (for pass-through like ${HOME})
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        # Use default if provided
        if default_value is not None:
            return default_value
        # Empty string if not found
        return ""

    return pattern.sub(replace, value)


class McpServerConfig(BaseModel):
    """Configuration for an MCP server connection.

    Compatible with bench ServerConfig format, with additional
    `enabled` field for toggling servers without removing config.
    """

    type: Literal["http", "stdio"] = Field(description="Server connection type")
    enabled: bool = Field(default=True, description="Whether this server is enabled")
    url: str | None = Field(default=None, description="URL for HTTP servers")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for HTTP servers"
    )
    command: str | None = Field(default=None, description="Command for stdio servers")
    args: list[str] = Field(
        default_factory=list, description="Arguments for stdio command"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for stdio servers"
    )
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    @field_validator("url", "command", mode="before")
    @classmethod
    def expand_secrets_validator(cls, v: str | None) -> str | None:
        """Expand ${VAR} from secrets.yaml in URL and command."""
        if v is None:
            return None
        return expand_secrets(v)
