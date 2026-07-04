"""Secrets loading for OneTool.

Loads secrets from secrets.yaml (gitignored) separate from committed configuration.
Secrets are passed to workers via JSON-RPC, not exposed as environment variables.

Pass the secrets file explicitly via ``--secrets <file>``.
If --secrets is not provided, no secrets are loaded.

Values prefixed with ``age1enc:`` are transparently decrypted in memory using an
age X25519 identity stored in the OS keychain. Plain values are passed through
unchanged. Keychain access is lazy — only triggered when encrypted values are present.

Example secrets.yaml:

    BRAVE_API_KEY: "your-brave-api-key"
    OPENAI_API_KEY: "sk-..."
    DATABASE_URL: "postgresql://..."
"""

from __future__ import annotations

import base64
import os
import re
import threading
from pathlib import Path

import yaml
from loguru import logger

_AGE_PREFIX = "age1enc:"


class SecretDecryptionError(Exception):
    """Raised when an age-encrypted secret cannot be decrypted."""


# Single global secrets cache
_secrets: dict[str, str] | None = None
_secrets_lock = threading.Lock()

# Pre-compiled regex for variable expansion (avoids recompilation on each call)
_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def load_secrets(
    secrets_path: Path | str | None = None,
    explicit: bool = False,
) -> dict[str, str]:
    """Load secrets from YAML file.

    Args:
        secrets_path: Path to secrets file. If None or doesn't exist,
            returns empty dict (no secrets).
        explicit: If True, raises FileNotFoundError when secrets_path is
            provided but doesn't exist (for user-specified --secrets flag).

    Returns:
        Dictionary of secret name -> value

    Raises:
        FileNotFoundError: If explicit=True and secrets_path doesn't exist
        ValueError: If YAML is invalid
    """
    if secrets_path is None:
        logger.debug("No secrets path provided")
        return {}

    secrets_path = Path(secrets_path)

    if not secrets_path.exists():
        if explicit:
            raise FileNotFoundError(f"Secrets file not found: {secrets_path}")
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

    # Transparent per-value decryption: only triggered when age1enc: values present
    encrypted_keys = [k for k, v in secrets.items() if v.startswith(_AGE_PREFIX)]
    if encrypted_keys:
        try:
            import keyring
        except ImportError as e:
            raise ImportError(
                "Encrypted secrets detected but keyring is not installed. "
                "Run: pip install keyring"
            ) from e

        try:
            import pyrage  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "Encrypted secrets detected but pyrage is not installed. "
                "Run: pip install pyrage"
            ) from e

        # Fail-closed on an insecure/plaintext keyring backend before reading the
        # identity (reuses the ot_secrets allow-list — single source of truth).
        from ottools.ot_secrets import (
            _NO_IDENTITY_MSG,
            _assert_secure_keyring_backend,
        )

        _assert_secure_keyring_backend(keyring)

        private_key = keyring.get_password("onetool", "age_identity")
        if not private_key:
            raise SecretDecryptionError(_NO_IDENTITY_MSG)

        identity = pyrage.x25519.Identity.from_str(private_key)
        for key in encrypted_keys:
            encoded = secrets[key][len(_AGE_PREFIX):]
            ciphertext = base64.b64decode(encoded, validate=True)
            # Decrypt — plaintext never logged
            plaintext_bytes = pyrage.decrypt(ciphertext, [identity])
            secrets[key] = plaintext_bytes.decode()

        logger.debug(f"Decrypted {len(encrypted_keys)} encrypted secret(s)")

    logger.debug(f"Loaded {len(secrets)} secrets")
    return secrets


def get_secrets(
    secrets_path: Path | str | None = None,
    reload: bool = False,
    explicit: bool = False,
) -> dict[str, str]:
    """Get or load the cached secrets.

    If secrets_path is None (i.e. --secrets not passed), returns {}.

    Args:
        secrets_path: Path to secrets file (only used on first load or reload).
            If None, returns empty dict — no secrets are loaded.
        reload: Force reload secrets from disk.

    Returns:
        Dictionary of secret name -> value
    """
    global _secrets

    if _secrets is not None and not reload:
        return _secrets

    with _secrets_lock:
        if _secrets is None or reload:
            _secrets = load_secrets(secrets_path, explicit=explicit)
    return _secrets


def get_secret(name: str) -> str | None:
    """Get a single secret value by name.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Secret value, or None if not found
    """
    return get_secrets().get(name)


def expand_vars(value: str, env: dict[str, str] | None = None) -> str:
    """Expand ${VAR} patterns from secrets.yaml first, then config env: section.

    Variable resolution order (first match wins):
    1. secrets.yaml (sensitive, user-specific values)
    2. env dict (caller-supplied override dict)
    3. config env: section (non-sensitive, shared values)
    4. os.environ (system environment)
    5. Default value if provided via ${VAR:-default} syntax
    6. ValueError if no match found

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    When to use:
        - Tool configuration values that may reference secrets or env vars
        - Subprocess environment variables (after root env + server env merge)
        - Any config value that needs runtime expansion

    Args:
        value: String potentially containing ${VAR} patterns.
        env: Optional additional environment dict checked after secrets.

    Returns:
        String with variables expanded.

    Raises:
        ValueError: If variable not found and no default provided.
    """
    missing_vars: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)

        # 1. Check secrets first (sensitive, user-specific)
        secret_value = get_secret(var_name)
        if secret_value is not None:
            return secret_value

        # 2. Check caller-supplied env dict
        if env is not None:
            env_val = env.get(var_name)
            if env_val is not None:
                return env_val

        # 3. Check config env: section (non-sensitive, shared)
        try:
            # Import here to avoid circular dependency
            from ot.config.loader import get_config

            config = get_config()
            config_env_value = config.env.get(var_name)
            if config_env_value is not None:
                return config_env_value
        except Exception:
            # Config not loaded yet or no env section
            pass

        # 4. Check os.environ
        os_val = os.environ.get(var_name)
        if os_val is not None:
            return os_val

        # 5. Use default if provided
        if default_value is not None:
            return default_value

        # 6. Error - variable not found
        missing_vars.append(var_name)
        return match.group(0)

    result = _VAR_PATTERN.sub(replace, value)

    if missing_vars:
        raise ValueError(
            f"Missing variables: {', '.join(missing_vars)}. "
            f"Add them to secrets.yaml or env: section in config, "
            f"or use ${{VAR:-default}} syntax."
        )

    return result


# Alias for backward compatibility with external code
expand_secrets = expand_vars


def reset() -> None:
    """Clear secrets cache for reload.

    Use this as part of the config reload flow to force secrets to be
    reloaded from disk on next access.
    """
    global _secrets
    _secrets = None
