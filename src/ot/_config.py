"""Shared configuration utilities for OneTool CLIs.

Provides generic YAML config loading with Pydantic validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import yaml

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["load_yaml_config"]

T = TypeVar("T", bound="BaseModel")


def load_yaml_config(
    model_class: type[T],
    config_path: Path | str | None = None,
    *,
    env_var: str | None = None,
    default_filename: str = "config.yaml",
) -> T:
    """Load and validate YAML configuration.

    Args:
        model_class: Pydantic model class to validate against
        config_path: Explicit path to config file
        env_var: Environment variable to check for config path
        default_filename: Default filename if no path specified

    Returns:
        Validated Pydantic model instance

    Raises:
        FileNotFoundError: If explicit config path doesn't exist
        ValueError: If YAML is invalid or validation fails

    Example:
        config = load_yaml_config(
            BrowseConfig,
            config_path,
            env_var="OT_BROWSE_CONFIG",
            default_filename="config/ot-browse.yaml",
        )
    """
    # Determine config path
    if config_path is None:
        env_config = os.getenv(env_var) if env_var else None
        resolved_path = Path(env_config) if env_config else Path(default_filename)
    else:
        resolved_path = Path(config_path)

    # Check if file exists
    if not resolved_path.exists():
        # Only use defaults if no explicit path was given
        is_default = config_path is None and (env_var is None or not os.getenv(env_var))
        if is_default:
            return model_class()
        raise FileNotFoundError(f"Config file not found: {resolved_path}")

    # Load YAML
    try:
        with resolved_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {resolved_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading {resolved_path}: {e}") from e

    if raw_data is None:
        raw_data = {}

    # Validate
    try:
        return model_class.model_validate(raw_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {resolved_path}: {e}") from e
