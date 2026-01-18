"""MCP server configuration for OneTool proxy.

Defines configuration for connecting to external MCP servers that are
proxied through OneTool's single `run` tool.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Cache for early secrets loading (before full config is available)
_early_secrets: dict[str, str] | None = None


def _get_early_secret(name: str) -> str | None:
    """Get a secret value during config loading.

    Loads secrets from the default location (.onetool/secrets.yaml) if not
    already loaded. This is used during config expansion before the full
    config (with custom secrets_file path) is available.

    Args:
        name: Secret name to look up

    Returns:
        Secret value or None if not found
    """
    global _early_secrets

    if _early_secrets is None:
        _early_secrets = {}
        # Try to load from default locations
        # Import here to avoid circular imports at module level
        import yaml

        from ot.paths import get_effective_cwd, get_global_dir

        # Try project secrets first, then global
        paths_to_try = [
            get_effective_cwd() / ".onetool" / "secrets.yaml",
            get_global_dir() / "secrets.yaml",
        ]

        for secrets_path in paths_to_try:
            if secrets_path.exists():
                try:
                    with secrets_path.open() as f:
                        raw_data = yaml.safe_load(f)
                    if isinstance(raw_data, dict):
                        _early_secrets = {
                            k: str(v) for k, v in raw_data.items() if v is not None
                        }
                    break
                except Exception:
                    pass  # Silently ignore errors during early loading

    return _early_secrets.get(name)


def expand_secrets(value: str) -> str:
    """Expand ${VAR} patterns using secrets.yaml only.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.
    Reads from secrets.yaml only - does NOT read from os.environ.
    Raises error if variable not found and no default provided.

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded from secrets.

    Raises:
        ValueError: If variable not found in secrets and no default.
    """
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
    missing_vars: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Read from secrets only - no os.environ
        secret_value = _get_early_secret(var_name)
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
    """Expand ${VAR} for subprocess environment values.

    Reads from secrets first, then os.environ for pass-through.
    This is the ONLY place where reading os.environ is allowed,
    enabling explicit env var pass-through to subprocesses.

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded. Empty string if not found.
    """
    import os

    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Secrets first
        secret_value = _get_early_secret(var_name)
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

    Compatible with ot-bench ServerConfig format, with additional
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
