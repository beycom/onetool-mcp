"""Secrets loading for OneTool.

Loads secrets from secrets.yaml (gitignored) separate from committed configuration.
Secrets are passed to workers via JSON-RPC, not exposed as environment variables.

The secrets file path is resolved from ot-serve.yaml configuration:
- Default: secrets.yaml (sibling of ot-serve.yaml in config/ subdirectory)
- Override via secrets_file in ot-serve.yaml

Example secrets.yaml:

    BRAVE_API_KEY: "your-brave-api-key"
    OPENAI_API_KEY: "sk-..."
    DATABASE_URL: "postgresql://..."

Loading Order:
    load_secrets_from_default_locations() is used during early config loading.
    The search order is: project (.onetool/config/secrets.yaml) → global (~/.onetool/config/secrets.yaml).
    This function is also used by mcp.py for ${VAR} expansion during config loading.
"""

from __future__ import annotations

import os
from pathlib import Path

# Note: os is still used for OT_SECRETS_FILE bootstrap env var in get_secrets()
import yaml
from loguru import logger

# Global secrets cache
_secrets: dict[str, str] | None = None

# Cache for early secrets loading (before full config is available)
_early_secrets: dict[str, str] | None = None


def load_secrets(secrets_path: Path | str | None = None) -> dict[str, str]:
    """Load secrets from YAML file.

    Args:
        secrets_path: Path to secrets file. If None or doesn't exist,
            returns empty dict (no secrets).

    Returns:
        Dictionary of secret name -> value

    Raises:
        ValueError: If YAML is invalid
    """
    if secrets_path is None:
        logger.debug("No secrets path provided")
        return {}

    secrets_path = Path(secrets_path)

    if not secrets_path.exists():
        logger.debug(f"Secrets file not found: {secrets_path}")
        return {}

    logger.debug(f"Loading secrets from {secrets_path}")

    try:
        with secrets_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in secrets file {secrets_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading secrets file {secrets_path}: {e}") from e

    if raw_data is None:
        return {}

    if not isinstance(raw_data, dict):
        raise ValueError(
            f"Secrets file {secrets_path} must be a YAML mapping, not {type(raw_data).__name__}"
        )

    # Values are literal - no env var expansion
    secrets: dict[str, str] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str):
            logger.warning(f"Ignoring non-string secret key: {key}")
            continue

        if value is None:
            continue

        # Store as literal string - no ${VAR} expansion
        secrets[key] = str(value)

    logger.info(f"Loaded {len(secrets)} secrets")
    return secrets


def load_secrets_from_default_locations(silent: bool = False) -> dict[str, str]:
    """Load secrets from default project and global locations.

    Searches in order (first found wins):
    1. Project: {effective_cwd}/.onetool/config/secrets.yaml
    2. Global: ~/.onetool/config/secrets.yaml

    This is used during early config loading before the full config (with custom
    secrets_file path) is available. Also used by mcp.py for ${VAR} expansion.

    Args:
        silent: If True, suppress error logging (for early loading during config parse)

    Returns:
        Dictionary of secret name -> value (empty if no secrets found)
    """
    # Import here to avoid circular imports at module level
    from ot.paths import CONFIG_SUBDIR, get_effective_cwd, get_global_dir

    # Try project secrets first, then global
    paths_to_try = [
        get_effective_cwd() / ".onetool" / CONFIG_SUBDIR / "secrets.yaml",
        get_global_dir() / CONFIG_SUBDIR / "secrets.yaml",
    ]

    for secrets_path in paths_to_try:
        if secrets_path.exists():
            try:
                return load_secrets(secrets_path)
            except ValueError as e:
                if not silent:
                    logger.warning(f"Error loading secrets from {secrets_path}: {e}")
                # Continue to next path on error
                continue

    return {}


def get_early_secret(name: str) -> str | None:
    """Get a secret value during early config loading.

    Uses cached secrets loaded from default locations (.onetool/secrets.yaml).
    This is the canonical way to get secrets during config expansion before
    the full config (with custom secrets_file) is available.

    Thread-safety note: This uses a global cache populated on first access.
    In multi-threaded scenarios, ensure config loading completes in the main
    thread before spawning workers.

    Args:
        name: Secret name to look up

    Returns:
        Secret value or None if not found
    """
    global _early_secrets

    if _early_secrets is None:
        # Load from default locations with silent=True to not spam logs during parsing
        _early_secrets = load_secrets_from_default_locations(silent=True)

    return _early_secrets.get(name)


def get_secrets(
    secrets_path: Path | str | None = None, reload: bool = False
) -> dict[str, str]:
    """Get or load the cached secrets.

    Args:
        secrets_path: Path to secrets file (only used on first load or reload).
            Falls back to OT_SECRETS_FILE env var if not provided.
        reload: Force reload secrets

    Returns:
        Dictionary of secret name -> value
    """
    global _secrets

    if _secrets is None or reload:
        # Fallback to OT_SECRETS_FILE env var if no path provided
        if secrets_path is None:
            secrets_path = os.getenv("OT_SECRETS_FILE")
        _secrets = load_secrets(secrets_path)

    return _secrets


def get_secret(name: str) -> str | None:
    """Get a single secret value by name.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Secret value, or None if not found
    """
    secrets = get_secrets()
    return secrets.get(name)
