"""Configuration for Browser Inspector CLI.

Loads ot-browse.yaml with browser settings.

Example ot-browse.yaml:

    devtools: true
    sessions_dir: .browser-sessions
    screenshot_quality: 85
    full_page_screenshot: true
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ot.paths import get_effective_cwd, get_global_dir


class BrowseConfig(BaseModel):
    """Configuration for Browser Inspector CLI."""

    # Browser settings
    devtools: bool = Field(
        default=False, description="Open DevTools when launching browser"
    )
    headless: bool = Field(default=False, description="Run browser in headless mode")
    codegen: bool = Field(
        default=False,
        description="Use Playwright Codegen mode (records actions as code)",
    )
    cdp_port: int = Field(
        default=9222,
        ge=1,
        le=65535,
        description="CDP port for connecting to existing browser",
    )
    no_viewport: bool = Field(
        default=True,
        description="Allow browser window to resize (True) or use fixed viewport (False)",
    )

    # Session storage
    sessions_dir: str = Field(
        default=".browse",
        description="Directory for storing capture sessions (relative to cwd)",
    )

    # Screenshot settings
    screenshot_quality: int = Field(
        default=85, ge=1, le=100, description="WebP quality for screenshots (1-100)"
    )
    full_page_screenshot: bool = Field(
        default=True, description="Capture full page screenshot vs viewport only"
    )
    annotation_padding: int = Field(
        default=50, ge=0, description="Padding around annotation screenshots in pixels"
    )

    # Browser args
    browser_args: list[str] = Field(
        default_factory=lambda: ["--no-sandbox", "--disable-setuid-sandbox"],
        description="Additional browser launch arguments",
    )

    # Capture settings
    max_text_length: int = Field(
        default=400,
        ge=0,
        description="Max chars for text fields in YAML output (0 for unlimited)",
    )
    max_annotation_screenshots: int = Field(
        default=10,
        ge=0,
        description="Skip annotation screenshots if count exceeds this (0 for unlimited)",
    )

    # Predefined annotations (applied on every page load)
    annotations: list[dict[str, str]] = Field(
        default_factory=list,
        description="Predefined annotations: [{selector: 'p', label: 'paragraphs'}, ...]",
    )

    # Favorite URLs for quick access
    favorites: list[str] = Field(
        default_factory=list,
        description="List of favorite URLs for quick access",
    )

    def get_sessions_path(self) -> Path:
        """Get resolved path for sessions directory."""
        return Path(self.sessions_dir).expanduser().resolve()


def load_config(config_path: Path | str | None = None) -> BrowseConfig:
    """Load Browser Inspector configuration from YAML file.

    Resolution order (when config_path is None):
    1. OT_BROWSE_CONFIG env var
    2. cwd/.onetool/config/ot-browse.yaml
    3. cwd/.onetool/ot-browse.yaml (legacy)
    4. ~/.onetool/ot-browse.yaml
    5. Built-in defaults

    Args:
        config_path: Path to config file (overrides resolution)

    Returns:
        Validated BrowseConfig
    """
    if config_path is None:
        # Check OT_BROWSE_CONFIG env var first
        env_config = os.getenv("OT_BROWSE_CONFIG")
        if env_config:
            config_path = Path(env_config)
        else:
            cwd = get_effective_cwd()
            # Try project config: cwd/.onetool/config/ot-browse.yaml (preferred)
            project_config = cwd / ".onetool" / "config" / "ot-browse.yaml"
            if project_config.exists():
                config_path = project_config
            else:
                # Try legacy location: cwd/.onetool/ot-browse.yaml
                legacy_config = cwd / ".onetool" / "ot-browse.yaml"
                if legacy_config.exists():
                    config_path = legacy_config
                else:
                    # Try global config: ~/.onetool/ot-browse.yaml
                    global_config = get_global_dir() / "ot-browse.yaml"
                    if global_config.exists():
                        config_path = global_config
                    else:
                        # No config found, use defaults
                        return BrowseConfig()
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        # Use defaults if no config file
        return BrowseConfig()

    try:
        with config_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading {config_path}: {e}") from e

    if raw_data is None:
        raw_data = {}

    try:
        config = BrowseConfig.model_validate(raw_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {config_path}: {e}") from e

    return config


# Global config instance
_config: BrowseConfig | None = None


def get_config(
    config_path: Path | str | None = None, reload: bool = False
) -> BrowseConfig:
    """Get or load the global configuration.

    Args:
        config_path: Path to config file (only used on first load)
        reload: Force reload configuration

    Returns:
        BrowseConfig instance
    """
    global _config

    if _config is None or reload:
        _config = load_config(config_path)

    return _config
