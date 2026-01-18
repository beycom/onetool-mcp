"""Secrets loading for OneTool.

Loads secrets from secrets.yaml (gitignored) separate from committed configuration.
Secrets are passed to workers via JSON-RPC, not exposed as environment variables.

The secrets file path is resolved from ot-serve.yaml configuration:
- Default: secrets.yaml (sibling of ot-serve.yaml)
- Override via secrets_file in ot-serve.yaml

Example secrets.yaml:

    BRAVE_API_KEY: "your-brave-api-key"
    OPENAI_API_KEY: "sk-..."
    DATABASE_URL: "postgresql://..."
"""

from __future__ import annotations

import os
from pathlib import Path

# Note: os is still used for OT_SECRETS_FILE bootstrap env var in get_secrets()
import yaml
from loguru import logger

# Global secrets cache
_secrets: dict[str, str] | None = None


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
