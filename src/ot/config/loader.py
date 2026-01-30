"""YAML configuration loading for OneTool.

Loads ot-serve.yaml with tool discovery patterns and settings.

Example ot-serve.yaml:

    version: 1

    include:
      - prompts.yaml    # prompts: section
      - snippets.yaml   # snippets: section

    tools_dir:
      - src/ot_tools/*.py

    transform:
      model: anthropic/claude-3-5-haiku

    secrets_file: secrets.yaml   # default: sibling of ot-serve.yaml
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from ot.config.mcp import McpServerConfig, expand_secrets
from ot.paths import (
    CONFIG_SUBDIR,
    get_bundled_config_dir,
    get_config_dir,
    get_effective_cwd,
    get_global_dir,
)

# Current config schema version
CURRENT_CONFIG_VERSION = 1


class TransformConfig(BaseModel):
    """Configuration for the transform() tool."""

    model: str = Field(default="", description="Model for code generation")
    base_url: str = Field(default="", description="Base URL for OpenAI-compatible API")
    max_tokens: int = Field(default=4096, description="Max output tokens")


class SnippetParam(BaseModel):
    """Parameter definition for a snippet."""

    required: bool = Field(
        default=True, description="Whether this parameter is required"
    )
    default: Any = Field(default=None, description="Default value if not provided")
    description: str = Field(default="", description="Description of the parameter")


class SnippetDef(BaseModel):
    """Definition of a reusable snippet template."""

    description: str = Field(
        default="", description="Description of what this snippet does"
    )
    params: dict[str, SnippetParam] = Field(
        default_factory=dict, description="Parameter definitions"
    )
    body: str = Field(
        ..., description="Jinja2 template body that expands to Python code"
    )


# ==================== Core Configuration Models ====================
# Note: Tool-specific configs (BraveConfig, GroundConfig, etc.) have been
# moved to their respective tool files. Tools access config via
# get_tool_config(pack, Config) at runtime.


class MsgTopicConfig(BaseModel):
    """Topic-to-file mapping for message routing."""

    pattern: str = Field(
        ...,
        description="Glob-style topic pattern (e.g., 'status:*', 'doc:*')",
    )
    file: str = Field(
        ...,
        description="File path for messages matching this pattern (supports ~ and ${VAR})",
    )


class MsgConfig(BaseModel):
    """Message tool configuration."""

    topics: list[MsgTopicConfig] = Field(
        default_factory=list,
        description="Topic patterns mapped to output files (first match wins)",
    )


class OutputSanitizationConfig(BaseModel):
    """Output sanitization configuration for prompt injection protection.

    Protects against indirect prompt injection by sanitizing tool outputs
    that may contain malicious payloads from external content.

    Three-layer defense:
    1. Trigger sanitization: Replace __ot, mcp__onetool patterns
    2. Tag sanitization: Remove <external-content-*> patterns
    3. GUID-tagged boundaries: Wrap content in unpredictable tags
    """

    enabled: bool = Field(
        default=True,
        description="Global toggle for output sanitization",
    )


class SecurityConfig(BaseModel):
    """Code validation security configuration.

    Controls code validation with three-tier pattern system:
    - allow: Execute silently (highest priority)
    - warned: Log warning but allow execution
    - blocked: Reject with error (lowest priority)

    Priority order: allow > warned > blocked

    Patterns support fnmatch wildcards:
    - '*' matches any characters (e.g., 'subprocess.*' matches 'subprocess.run')
    - '?' matches a single character
    - '[seq]' matches any character in seq

    Pattern matching logic (handled automatically by validator):
    - Patterns WITHOUT dots (e.g., 'exec', 'subprocess') match:
      * Builtin function calls: exec(), eval()
      * Import statements: import subprocess, from os import system
    - Patterns WITH dots (e.g., 'subprocess.*', 'os.system') match:
      * Qualified function calls: subprocess.run(), os.system()

    Configuration behavior:
    - blocked/warned lists EXTEND the built-in defaults (additive)
    - Adding a pattern to 'warned' downgrades it from blocked (if in defaults)
    - Use 'allow' list to exempt specific patterns entirely (no warning)

    Example configurations:
        # Air-gapped mode - block network tools
        security:
          block: [brave.*, web_fetch.*, context7.*]

        # Trust file ops
        security:
          allow: [file.*]
    """

    validate_code: bool = Field(
        default=True,
        description="Enable AST-based code validation before execution",
    )

    enabled: bool = Field(
        default=True,
        description="Enable security pattern checking (requires validate_code)",
    )

    # Blocked patterns - EXTENDS built-in defaults (prevents accidental removal)
    # Use 'allow' to exempt specific patterns if needed
    blocked: list[str] = Field(
        default_factory=list,
        description="Additional patterns to block (extends defaults, not replaces)",
    )

    # Warned patterns - EXTENDS built-in defaults
    warned: list[str] = Field(
        default_factory=list,
        description="Additional patterns to warn on (extends defaults, not replaces)",
    )

    # Allow list - explicitly exempt patterns from defaults
    # Use this to remove a default pattern you need (e.g., allow 'open' for file tools)
    allow: list[str] = Field(
        default_factory=list,
        description="Patterns to exempt from blocking/warning (removes from defaults)",
    )

    # Output sanitization configuration
    sanitize: OutputSanitizationConfig = Field(
        default_factory=OutputSanitizationConfig,
        description="Output sanitization for prompt injection protection",
    )


class StatsConfig(BaseModel):
    """Runtime statistics collection configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable statistics collection",
    )
    persist_dir: str = Field(
        default="stats",
        description="Directory for stats files (relative to .onetool/)",
    )
    persist_path: str = Field(
        default="stats.jsonl",
        description="Filename for stats persistence (within persist_dir)",
    )
    flush_interval_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Interval in seconds between flushing stats to disk",
    )
    context_per_call: int = Field(
        default=30000,
        ge=0,
        description="Estimated context tokens saved per consolidated tool call",
    )
    time_overhead_per_call_ms: int = Field(
        default=4000,
        ge=0,
        description="Estimated time overhead in ms saved per consolidated tool call",
    )
    model: str = Field(
        default="anthropic/claude-opus-4.5",
        description="Model for cost estimation (e.g., anthropic/claude-opus-4.5)",
    )
    cost_per_million_input_tokens: float = Field(
        default=15.0,
        ge=0,
        description="Cost in USD per million input tokens",
    )
    cost_per_million_output_tokens: float = Field(
        default=75.0,
        ge=0,
        description="Cost in USD per million output tokens",
    )
    chars_per_token: float = Field(
        default=4.0,
        ge=1.0,
        description="Average characters per token for estimation",
    )


class ToolsConfig(BaseModel):
    """Aggregated tool configurations.

    Core configs (msg, stats) are typed fields. Tool-specific configs
    (brave, ground, etc.) are allowed as extra fields and accessed via
    get_tool_config() with schemas defined in tool files.
    """

    model_config = ConfigDict(extra="allow")

    # Core configs - always available
    msg: MsgConfig = Field(default_factory=MsgConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)


class OneToolConfig(BaseModel):
    """Root configuration for OneTool V1."""

    # Private attribute to track config file location (not serialized)
    # Note: Path is natively supported by Pydantic, no arbitrary_types_allowed needed
    _config_dir: Path | None = PrivateAttr(default=None)

    version: int = Field(
        default=1,
        description="Config schema version for migration support",
    )

    inherit: Literal["global", "bundled", "none"] = Field(
        default="global",
        description=(
            "Config inheritance mode:\n"
            "  - 'global' (default): Merge ~/.onetool/ot-serve.yaml first, then "
            "bundled defaults as fallback. Use for project configs that extend user prefs.\n"
            "  - 'bundled': Merge package defaults only, skip global config. "
            "Use for reproducible configs that shouldn't depend on user settings.\n"
            "  - 'none': Standalone config with no inheritance. "
            "Use for fully self-contained configs."
        ),
    )

    include: list[str] = Field(
        default_factory=list,
        description="Files to deep-merge into config (processed before validation)",
    )

    transform: TransformConfig = Field(
        default_factory=TransformConfig, description="transform() tool configuration"
    )

    alias: dict[str, str] = Field(
        default_factory=dict,
        description="Short alias names mapping to full function names (e.g., ws -> brave.web_search)",
    )

    snippets: dict[str, SnippetDef] = Field(
        default_factory=dict,
        description="Reusable snippet templates with Jinja2 variable substitution",
    )

    servers: dict[str, McpServerConfig] = Field(
        default_factory=dict,
        description="External MCP servers to proxy through OneTool",
    )

    tools: ToolsConfig = Field(
        default_factory=ToolsConfig,
        description="Tool-specific configuration (timeouts, limits, etc.)",
    )

    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Code validation and security pattern configuration",
    )

    stats: StatsConfig = Field(
        default_factory=StatsConfig,
        description="Runtime statistics collection configuration (replaces tools.stats)",
    )

    tools_dir: list[str] = Field(
        default_factory=lambda: ["tools/*.py"],
        description="Glob patterns for tool discovery (relative to OT_DIR .onetool/, or absolute)",
    )
    secrets_file: str = Field(
        default="config/secrets.yaml",
        description="Path to secrets file (relative to OT_DIR .onetool/, or absolute)",
    )
    prompts: dict[str, Any] | None = Field(
        default=None,
        description="Inline prompts config (can also be loaded via include:)",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_dir: str = Field(
        default="logs",
        description="Directory for log files (relative to .onetool/)",
    )
    compact_max_length: int = Field(
        default=120, description="Max value length in compact console output"
    )
    log_verbose: bool = Field(
        default=False,
        description="Disable log truncation for debugging (full values in output)",
    )
    debug_tracebacks: bool = Field(
        default=False,
        description="Show verbose tracebacks with local variables on errors",
    )

    @field_validator("snippets", "servers", "alias", mode="before")
    @classmethod
    def empty_dict_if_none(cls, v: Any) -> Any:
        """Convert None to empty dict for dict-type fields.

        This handles YAML files where the key exists but all values are commented out,
        which YAML parses as None instead of an empty dict.
        """
        return {} if v is None else v

    @model_validator(mode="before")
    @classmethod
    def migrate_tools_stats(cls, data: Any) -> Any:
        """Migrate tools.stats to root-level stats with deprecation warning.

        During the deprecation period, supports both paths:
        - Root-level `stats:` (preferred)
        - Legacy `tools.stats:` (deprecated)

        If both exist, root-level takes precedence.
        """
        if not isinstance(data, dict):
            return data

        tools = data.get("tools")
        if not isinstance(tools, dict):
            return data

        legacy_stats = tools.get("stats")
        root_stats = data.get("stats")

        if legacy_stats and not root_stats:
            # Only tools.stats exists - migrate with warning
            logger.warning(
                "Deprecation: 'tools.stats' config path is deprecated. "
                "Move to root-level 'stats:' section. "
                "This will be removed in a future version."
            )
            data["stats"] = legacy_stats
        elif legacy_stats and root_stats:
            # Both exist - root takes precedence, log info
            logger.debug(
                "Both 'stats' and 'tools.stats' defined. "
                "Using root-level 'stats' (ignoring deprecated 'tools.stats')."
            )

        return data

    def get_tool_files(self) -> list[Path]:
        """Get list of tool files matching configured glob patterns.

        Pattern resolution (all relative to OT_DIR .onetool/):
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory
        - Relative patterns: resolved relative to OT_DIR (.onetool/)

        Returns:
            List of Path objects for tool files
        """
        tool_files: list[Path] = []
        cwd = get_effective_cwd()

        # Determine OT_DIR for resolving patterns
        if self._config_dir is not None:
            # _config_dir is the config/ subdirectory, go up to .onetool/
            ot_dir = self._config_dir.parent
        else:
            # Fallback: cwd/.onetool
            ot_dir = cwd / ".onetool"

        for pattern in self.tools_dir:
            # Expand ~ first
            expanded = Path(pattern).expanduser()

            # Determine resolved pattern for globbing
            if expanded.is_absolute():
                # Absolute pattern - use as-is
                resolved_pattern = str(expanded)
            else:
                # All relative patterns resolve against OT_DIR
                resolved_pattern = str(ot_dir / pattern)

            # Use glob.glob() for cross-platform compatibility
            for match in glob.glob(resolved_pattern, recursive=True):  # noqa: PTH207
                path = Path(match)
                if path.is_file() and path.suffix == ".py":
                    tool_files.append(path)

        return sorted(set(tool_files))

    def _resolve_onetool_relative_path(self, path_str: str) -> Path:
        """Resolve a path relative to the .onetool directory.

        Handles:
        - Absolute paths: returned as-is
        - ~ expansion: expanded to home directory
        - Relative paths: resolved relative to .onetool/ directory (parent of config/)

        Note: Does NOT expand ${VAR} - use ~/path instead of ${HOME}/path.

        Args:
            path_str: Path string to resolve

        Returns:
            Resolved absolute Path
        """
        # Only expand ~ (no ${VAR} expansion)
        path = Path(path_str).expanduser()

        # If absolute after expansion, use as-is
        if path.is_absolute():
            return path

        # Resolve relative to .onetool/ directory (parent of config/)
        if self._config_dir is not None:
            # _config_dir is the config/ subdirectory, go up to .onetool/
            onetool_dir = self._config_dir.parent
            return (onetool_dir / path).resolve()

        # Fallback: resolve relative to cwd/.onetool
        return (get_effective_cwd() / ".onetool" / path).resolve()

    def _resolve_config_relative_path(self, path_str: str) -> Path:
        """Resolve a path relative to the config directory.

        Handles:
        - Absolute paths: returned as-is
        - ~ expansion: expanded to home directory
        - Relative paths: resolved relative to config/ directory

        Note: Does NOT expand ${VAR} - use ~/path instead of ${HOME}/path.

        Args:
            path_str: Path string to resolve

        Returns:
            Resolved absolute Path
        """
        # Only expand ~ (no ${VAR} expansion)
        path = Path(path_str).expanduser()

        # If absolute after expansion, use as-is
        if path.is_absolute():
            return path

        # Resolve relative to config directory
        if self._config_dir is not None:
            return (self._config_dir / path).resolve()

        # Fallback: resolve relative to cwd/.onetool/config
        return (get_effective_cwd() / ".onetool" / CONFIG_SUBDIR / path).resolve()

    def get_secrets_file_path(self) -> Path:
        """Get the resolved path to the secrets configuration file.

        Path is resolved relative to OT_DIR (.onetool/).

        Returns:
            Absolute Path to secrets file
        """
        return self._resolve_onetool_relative_path(self.secrets_file)

    def get_log_dir_path(self) -> Path:
        """Get the resolved path to the log directory.

        Path is resolved relative to the .onetool/ directory.

        Returns:
            Absolute Path to log directory
        """
        return self._resolve_onetool_relative_path(self.log_dir)

    def get_stats_dir_path(self) -> Path:
        """Get the resolved path to the stats directory.

        Path is resolved relative to the .onetool/ directory.

        Returns:
            Absolute Path to stats directory
        """
        return self._resolve_onetool_relative_path(self.stats.persist_dir)

    def get_stats_file_path(self) -> Path:
        """Get the resolved path to the stats JSONL file.

        Stats file is stored in the stats directory.

        Returns:
            Absolute Path to stats file
        """
        return self.get_stats_dir_path() / self.stats.persist_path


def _resolve_config_path(config_path: Path | str | None) -> Path | None:
    """Resolve config path from explicit path, env var, or default locations.

    Resolution order:
    1. Explicit config_path if provided
    2. OT_SERVE_CONFIG env var
    3. cwd/.onetool/config/ot-serve.yaml
    4. ~/.onetool/config/ot-serve.yaml
    5. None (use defaults)

    Args:
        config_path: Explicit path to config file (may be None).

    Returns:
        Resolved Path or None if no config file found.
    """
    if config_path is not None:
        return Path(config_path)

    env_config = os.getenv("OT_SERVE_CONFIG")
    if env_config:
        return Path(env_config)

    cwd = get_effective_cwd()
    project_config = cwd / ".onetool" / CONFIG_SUBDIR / "ot-serve.yaml"
    if project_config.exists():
        return project_config

    global_config = get_config_dir(get_global_dir()) / "ot-serve.yaml"
    if global_config.exists():
        return global_config

    return None


def _load_yaml_file(config_path: Path) -> dict[str, Any]:
    """Load and parse YAML file with error handling.

    Args:
        config_path: Path to YAML file.

    Returns:
        Parsed YAML data as dict.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If YAML is invalid or file can't be read.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with config_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading {config_path}: {e}") from e

    return raw_data if raw_data is not None else {}


def _expand_secrets_recursive(data: Any) -> Any:
    """Recursively expand ${VAR} from secrets.yaml in config data.

    Args:
        data: Config data (dict, list, or scalar).

    Returns:
        Data with secrets expanded.
    """
    if isinstance(data, dict):
        return {k: _expand_secrets_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_secrets_recursive(v) for v in data]
    elif isinstance(data, str):
        return expand_secrets(data)
    return data


def _validate_version(data: dict[str, Any], config_path: Path) -> None:
    """Validate config version and set default if missing.

    Args:
        data: Config data dict (modified in place).
        config_path: Path to config file (for error messages).

    Raises:
        ValueError: If version is unsupported.
    """
    config_version = data.get("version")
    if config_version is None:
        logger.warning(
            f"Config file missing 'version' field, assuming version 1. "
            f"Add 'version: {CURRENT_CONFIG_VERSION}' to {config_path}"
        )
        data["version"] = 1
    elif config_version > CURRENT_CONFIG_VERSION:
        raise ValueError(
            f"Config version {config_version} is not supported. "
            f"Maximum supported version is {CURRENT_CONFIG_VERSION}. "
            f"Please upgrade OneTool: uv tool upgrade onetool"
        )


def _remove_legacy_fields(data: dict[str, Any]) -> None:
    """Remove V1-unsupported fields from config data.

    Args:
        data: Config data dict (modified in place).
    """
    for key in ["mounts", "profile"]:
        if key in data:
            logger.debug(f"Ignoring legacy config field '{key}'")
            del data[key]


def _resolve_include_path(
    include_path_str: str, ot_dir: Path
) -> Path | None:
    """Resolve an include path using three-tier fallback.

    Search order:
    1. ot_dir (project .onetool/ or wherever the config's OT_DIR is)
    2. global (~/.onetool/)
    3. bundled (package defaults)

    Supports:
    - Absolute paths (used as-is)
    - ~ expansion (expands to home directory)
    - Relative paths (searched in three-tier order)

    Args:
        include_path_str: Path string from include directive
        ot_dir: The .onetool/ directory (OT_DIR) for the config

    Returns:
        Resolved Path if found, None otherwise
    """
    # Expand ~ first
    include_path = Path(include_path_str).expanduser()

    # Absolute paths are used as-is
    if include_path.is_absolute():
        if include_path.exists():
            logger.debug(f"Include resolved (absolute): {include_path}")
            return include_path
        return None

    # Tier 1: ot_dir (project .onetool/ or current OT_DIR)
    tier1 = (ot_dir / include_path).resolve()
    if tier1.exists():
        logger.debug(f"Include resolved (ot_dir): {tier1}")
        return tier1

    # Tier 2: global (~/.onetool/)
    tier2 = (get_global_dir() / include_path).resolve()
    if tier2.exists():
        logger.debug(f"Include resolved (global): {tier2}")
        return tier2

    # Tier 3: bundled (package defaults)
    try:
        bundled_dir = get_bundled_config_dir()
        tier3 = (bundled_dir / include_path).resolve()
        if tier3.exists():
            logger.debug(f"Include resolved (bundled): {tier3}")
            return tier3
    except FileNotFoundError:
        # Bundled defaults not available
        pass

    logger.debug(f"Include not found in any tier: {include_path_str}")
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override values taking precedence.

    - Nested dicts are recursively merged
    - Non-dict values (lists, scalars) are replaced entirely
    - Keys in override not in base are added

    Args:
        base: Base dictionary (inputs not mutated)
        override: Override dictionary (inputs not mutated, values take precedence)

    Returns:
        New merged dictionary
    """
    result = base.copy()

    for key, override_value in override.items():
        if key in result:
            base_value = result[key]
            # Only deep merge if both are dicts
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = _deep_merge(base_value, override_value)
            else:
                # Replace entirely (lists, scalars, or type mismatch)
                result[key] = override_value
        else:
            # New key from override
            result[key] = override_value

    return result


def _load_includes(
    data: dict[str, Any], ot_dir: Path, seen_paths: set[Path] | None = None
) -> dict[str, Any]:
    """Load and merge files from 'include:' list into config data.

    Files are merged left-to-right (later files override earlier).
    Inline content in the main file overrides everything.

    Include resolution uses three-tier fallback:
    1. ot_dir (project .onetool/ or current OT_DIR)
    2. global (~/.onetool/)
    3. bundled (package defaults)

    Args:
        data: Config data dict containing optional 'include' key
        ot_dir: The .onetool/ directory (OT_DIR) for resolving relative paths
        seen_paths: Set of already-processed paths (for circular detection)

    Returns:
        Merged config data with includes processed
    """
    if seen_paths is None:
        seen_paths = set()

    include_list = data.get("include", [])
    if not include_list:
        return data

    # Start with empty base for merging included files
    merged: dict[str, Any] = {}

    for include_path_str in include_list:
        # Use three-tier resolution
        include_path = _resolve_include_path(include_path_str, ot_dir)

        if include_path is None:
            logger.warning(f"Include file not found: {include_path_str}")
            continue

        # Circular include detection
        if include_path in seen_paths:
            logger.warning(f"Circular include detected, skipping: {include_path}")
            continue

        try:
            with include_path.open() as f:
                include_data = yaml.safe_load(f)

            if not include_data or not isinstance(include_data, dict):
                logger.debug(f"Empty or non-dict include file: {include_path}")
                continue

            # Recursively process nested includes (same OT_DIR for all nested includes)
            new_seen = seen_paths | {include_path}
            include_data = _load_includes(
                include_data, ot_dir, new_seen
            )

            # Merge this include file (later overrides earlier)
            merged = _deep_merge(merged, include_data)

            logger.debug(f"Merged include file: {include_path}")

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in include file {include_path}: {e}")
        except OSError as e:
            logger.error(f"Error reading include file {include_path}: {e}")

    # Main file content (minus 'include' key) overrides everything
    main_content = {k: v for k, v in data.items() if k != "include"}
    result = _deep_merge(merged, main_content)

    # Preserve the include list for reference (but it's already processed)
    result["include"] = include_list

    return result


def _load_base_config(
    inherit: str, current_config_path: Path | None
) -> dict[str, Any]:
    """Load base configuration for inheritance.

    Args:
        inherit: Inheritance mode (global, bundled, none)
        current_config_path: Path to the current config file (to avoid self-include)

    Returns:
        Base config data dict to merge with current config
    """
    if inherit == "none":
        return {}

    # Try global first for 'global' mode
    if inherit == "global":
        global_config_path = get_config_dir(get_global_dir()) / "ot-serve.yaml"
        if global_config_path.exists():
            # Skip if this is the same file we're already loading
            if current_config_path and global_config_path.resolve() == current_config_path.resolve():
                logger.debug("Skipping global inheritance (loading global config itself)")
            else:
                try:
                    raw_data = _load_yaml_file(global_config_path)
                    # Process includes in global config - OT_DIR is ~/.onetool/
                    global_ot_dir = get_global_dir()
                    data = _load_includes(raw_data, global_ot_dir)
                    logger.debug(f"Inherited base config from global: {global_config_path}")
                    return data
                except (FileNotFoundError, ValueError) as e:
                    logger.warning(f"Failed to load global config for inheritance: {e}")

    # Fall back to bundled for both 'global' (when global missing) and 'bundled' modes
    try:
        bundled_dir = get_bundled_config_dir()
        bundled_config_path = bundled_dir / "ot-serve.yaml"
        if bundled_config_path.exists():
            raw_data = _load_yaml_file(bundled_config_path)
            # Process includes in bundled config - bundled dir is flat (no config/ subdir)
            data = _load_includes(raw_data, bundled_dir)
            logger.debug(f"Inherited base config from bundled: {bundled_config_path}")
            return data
    except FileNotFoundError:
        logger.debug("Bundled config not available for inheritance")

    return {}


def load_config(config_path: Path | str | None = None) -> OneToolConfig:
    """Load OneTool configuration from YAML file.

    Resolution order (when config_path is None):
        1. OT_SERVE_CONFIG env var
        2. cwd/.onetool/ot-serve.yaml (project config)
        3. ~/.onetool/ot-serve.yaml (global config)
        4. Built-in defaults (bundled with package)

    Inheritance (controlled by 'inherit' field in your config):

        'global' (default):
            Base: ~/.onetool/ot-serve.yaml → bundled defaults (if global missing)
            Your config overrides the base. Use for project configs that
            extend user preferences (API keys, timeouts, etc.).

        'bundled':
            Base: bundled defaults only (ignores ~/.onetool/)
            Your config overrides bundled. Use for reproducible configs
            that shouldn't depend on user-specific settings.

        'none':
            No base config. Your config is standalone.
            Use for fully self-contained configurations.

    Example minimal project config using global inheritance::

        # .onetool/ot-serve.yaml
        version: 1
        # inherit: global  (implicit default - gets API keys from ~/.onetool/)
        tools_dir:
          - ./tools/*.py

    Args:
        config_path: Path to config file (overrides resolution)

    Returns:
        Validated OneToolConfig

    Raises:
        FileNotFoundError: If explicit config path doesn't exist
        ValueError: If YAML is invalid or validation fails
    """
    resolved_path = _resolve_config_path(config_path)

    if resolved_path is None:
        logger.debug("No config file found, using defaults")
        config = OneToolConfig()
        config._config_dir = get_effective_cwd() / ".onetool" / CONFIG_SUBDIR
        return config

    logger.debug(f"Loading config from {resolved_path}")

    raw_data = _load_yaml_file(resolved_path)
    expanded_data = _expand_secrets_recursive(raw_data)

    # Process includes before validation (merges external files)
    # Resolve includes from OT_DIR (.onetool/), not config_dir (.onetool/config/)
    config_dir = resolved_path.parent.resolve()
    ot_dir = config_dir.parent  # Go up from config/ to .onetool/
    merged_data = _load_includes(expanded_data, ot_dir)

    # Determine inheritance mode (default: global)
    inherit = merged_data.get("inherit", "global")
    if inherit not in ("global", "bundled", "none"):
        logger.warning(f"Invalid inherit value '{inherit}', using 'global'")
        inherit = "global"

    # Load and merge base config for inheritance
    base_config = _load_base_config(inherit, resolved_path)
    if base_config:
        # Base first, then current config overrides
        merged_data = _deep_merge(base_config, merged_data)
        logger.debug(f"Applied inheritance mode: {inherit}")

    _validate_version(merged_data, resolved_path)
    _remove_legacy_fields(merged_data)

    try:
        config = OneToolConfig.model_validate(merged_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {resolved_path}: {e}") from e

    config._config_dir = resolved_path.parent.resolve()

    logger.info(f"Config loaded: version {config.version}")

    return config


# Global config instance (singleton pattern)
# Thread-safety: This cache is NOT thread-safe. In multi-threaded applications,
# ensure load_config() is called once during initialization before spawning threads.
# The `reload` parameter is intended for testing only.
_config: OneToolConfig | None = None


def is_log_verbose() -> bool:
    """Check if verbose logging is enabled.

    Verbose mode disables log truncation, showing full values.
    Enabled by:
    - OT_LOG_VERBOSE=true environment variable (highest priority)
    - log_verbose: true in config file

    Returns:
        True if verbose logging is enabled
    """
    # Environment variable takes priority
    env_verbose = os.getenv("OT_LOG_VERBOSE", "").lower()
    if env_verbose in ("true", "1", "yes"):
        return True
    if env_verbose in ("false", "0", "no"):
        return False

    # Fall back to config
    global _config
    if _config is not None:
        return _config.log_verbose

    return False


def get_config(
    config_path: Path | str | None = None, reload: bool = False
) -> OneToolConfig:
    """Get or load the global configuration (singleton pattern).

    Returns a cached config instance. On first call, loads config from disk.
    Subsequent calls return the cached instance unless reload=True.

    Thread-safety note: This function is NOT thread-safe. In multi-threaded
    applications, call this once during initialization before spawning threads.
    The cache uses a simple global variable without locking.

    Args:
        config_path: Path to config file (only used on first load or reload).
            Ignored after config is cached unless reload=True.
        reload: Force reload configuration from disk. Use sparingly - primarily
            intended for testing. In production, restart the process to reload.

    Returns:
        OneToolConfig instance (same instance on subsequent calls)
    """
    global _config

    if _config is None or reload:
        _config = load_config(config_path)

    return _config
