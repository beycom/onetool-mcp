"""Secrets loading for OneTool.

Loads secrets from secrets.yaml (gitignored) separate from committed configuration.
Secrets are passed to workers via JSON-RPC, not exposed as environment variables.

The secrets file path is resolved in order:
1. Explicit path passed to get_secrets()
2. Config's secrets_file setting (if config loaded and file exists)
3. Default locations: project (.onetool/config/secrets.yaml) then global (~/.onetool/config/secrets.yaml)
4. OT_SECRETS_FILE environment variable

Example secrets.yaml:

    BRAVE_API_KEY: "your-brave-api-key"
    OPENAI_API_KEY: "sk-..."
    DATABASE_URL: "postgresql://..."
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from loguru import logger

# Single global secrets cache
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


def _load_from_default_locations() -> dict[str, str]:
    """Load secrets from default project and global locations.

    Searches in order (first found wins):
    1. Project: {effective_cwd}/.onetool/config/secrets.yaml
    2. Global: ~/.onetool/config/secrets.yaml

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
                # Silent during bootstrap - don't spam logs
                logger.debug(f"Error loading secrets from {secrets_path}: {e}")
                continue

    return {}


def get_secrets(
    secrets_path: Path | str | None = None, reload: bool = False
) -> dict[str, str]:
    """Get or load the cached secrets.

    Resolution order (first match wins):
    1. Explicit secrets_path argument
    2. Config's secrets_file setting (if config loaded and file exists)
    3. Default locations (.onetool/config/secrets.yaml)
    4. OT_SECRETS_FILE environment variable

    Args:
        secrets_path: Path to secrets file (only used on first load or reload).
        reload: Force reload secrets from disk.

    Returns:
        Dictionary of secret name -> value
    """
    global _secrets

    if _secrets is None or reload:
        # Resolution chain: explicit > config (if loaded) > defaults > env var
        if secrets_path is None:
            # WARNING: Do NOT call get_config() here!
            # =========================================
            # This function is called during config loading via:
            #   get_config() → load_config() → expand_secrets() → get_early_secret() → get_secrets()
            #
            # If we call get_config() here, it triggers config loading again → infinite recursion.
            # Instead, we check _config directly - if it's None, config is still loading.
            try:
                import ot.config.loader

                if ot.config.loader._config is not None:
                    config_path = ot.config.loader._config.get_secrets_file_path()
                    if config_path.exists():
                        secrets_path = config_path
            except Exception:
                pass  # Module not loaded yet, fall through

        # Try default locations if still no path
        if secrets_path is None:
            loaded = _load_from_default_locations()
            if loaded:
                _secrets = loaded
                return _secrets

        # Final fallback to OT_SECRETS_FILE env var
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
    return get_secrets().get(name)


# Alias for backward compatibility and semantic clarity during config loading
# Both functions now use the same unified cache
get_early_secret = get_secret
