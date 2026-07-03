"""Dual-mode configuration shim for OneTool packs.

When running inside onetool-mcp, delegates to ot.config for all operations.
When running standalone (e.g., onetool-figma-mcp), falls back to a YAML file
with the same tools: section structure as onetool.yaml, or os.environ.

Usage:
    # In standalone mode, call configure_standalone() first:
    from otpack import configure_standalone
    configure_standalone("/path/to/config.yaml")

    # Then use as normal:
    from otpack import get_tool_config, get_secret, is_log_verbose
    config = get_tool_config("figma", FigmaConfig)
    key = get_secret("API_KEY")
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, TypeVar, overload

from pydantic import BaseModel, ValidationError

__all__ = [
    "configure_standalone",
    "get_secret",
    "get_tool_config",
    "is_log_verbose",
]

T = TypeVar("T", bound=BaseModel)

# Standalone state (used only when ot.config is not importable)
_standalone_config: dict[str, Any] | None = None
_standalone_secrets: dict[str, str] | None = None
_standalone_lock = threading.Lock()


def configure_standalone(config_path: str | Path, secrets_path: str | Path | None = None) -> None:
    """Load configuration from a YAML file for standalone operation.

    The YAML file uses the same tools: section structure as onetool.yaml.
    Call this before using get_tool_config() or get_secret() in standalone mode.

    Args:
        config_path: Path to YAML config file
        secrets_path: Optional explicit path to secrets YAML file. When provided,
            overrides auto-discovery of adjacent secrets.yaml. Raises
            FileNotFoundError if the explicit path does not exist.
    """
    global _standalone_config, _standalone_secrets
    import yaml

    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as f:
        data = yaml.safe_load(f) or {}

    with _standalone_lock:
        _standalone_config = data
        # Determine secrets file path
        resolved_secrets: Path | None
        if secrets_path is not None:
            resolved_secrets = Path(secrets_path).expanduser().resolve()
            if not resolved_secrets.exists():
                raise FileNotFoundError(f"Secrets file not found: {resolved_secrets}")
        else:
            resolved_secrets = path.parent / "secrets.yaml"
            if not resolved_secrets.exists():
                resolved_secrets = None

        if resolved_secrets is not None:
            with resolved_secrets.open() as f:
                secrets_data = yaml.safe_load(f) or {}
            encrypted = [k for k, v in secrets_data.items() if isinstance(v, str) and v.startswith("age1enc:")]
            if encrypted:
                raise ValueError(
                    f"Encrypted secrets are not supported in standalone mode: {', '.join(encrypted)}. "
                    "Use plain text values in secrets.yaml."
                )
            _standalone_secrets = {
                k: str(v) for k, v in secrets_data.items() if isinstance(k, str) and v is not None
            }
        else:
            _standalone_secrets = {}


def _get_standalone_tool_config(pack: str) -> dict[str, Any]:
    """Get raw tool config dict from standalone config."""
    with _standalone_lock:
        if _standalone_config is None:
            return {}
        tools = _standalone_config.get("tools", {})
        if not isinstance(tools, dict):
            return {}
        pack_config = tools.get(pack, {})
        return dict(pack_config) if isinstance(pack_config, dict) else {}


def _get_standalone_secret(name: str) -> str | None:
    """Get a secret from standalone config or os.environ."""
    with _standalone_lock:
        if _standalone_secrets is not None:
            value = _standalone_secrets.get(name)
            if value is not None:
                return value
    return os.environ.get(name)


@overload
def get_tool_config(pack: str, schema: type[T]) -> T: ...


@overload
def get_tool_config(pack: str, schema: None = None) -> dict[str, Any]: ...


def get_tool_config(pack: str, schema: type[T] | None = None) -> T | dict[str, Any]:
    """Get configuration for a tool pack.

    Delegates to ot.config when available (onetool mode), otherwise reads
    from the standalone config loaded via configure_standalone().

    Args:
        pack: Pack name (e.g., "brave", "figma")
        schema: Optional Pydantic model class to validate and return typed config.

    Returns:
        If schema provided: Instance of schema with config values merged
        If no schema: Dict with raw config values (empty dict if not configured)
    """
    try:
        from ot.config import get_tool_config as _ot_get_tool_config

        if schema is None:
            result: dict[str, Any] = _ot_get_tool_config(pack)
            return result
        return _ot_get_tool_config(pack, schema)
    except ImportError:
        pass

    raw_config = _get_standalone_tool_config(pack)

    if schema is None:
        return raw_config

    try:
        return schema.model_validate(raw_config)
    except ValidationError:
        return schema()


def get_secret(name: str) -> str | None:
    """Get a single secret value by name.

    Delegates to ot.config.secrets when available (onetool mode), otherwise
    reads from standalone secrets.yaml or os.environ.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Secret value, or None if not found
    """
    try:
        from ot.config.secrets import get_secret as _ot_get_secret

        return _ot_get_secret(name)
    except ImportError:
        pass

    return _get_standalone_secret(name)


def is_log_verbose() -> bool:
    """Check if verbose logging is enabled.

    Delegates to ot.config when available, otherwise checks OT_LOG_VERBOSE env var.

    Returns:
        True if verbose logging is enabled
    """
    # Environment variable always takes priority
    env_verbose = os.getenv("OT_LOG_VERBOSE", "").lower()
    if env_verbose in ("true", "1", "yes"):
        return True
    if env_verbose in ("false", "0", "no"):
        return False

    try:
        from ot.config import is_log_verbose as _ot_is_log_verbose

        return _ot_is_log_verbose()
    except ImportError:
        pass

    return False
