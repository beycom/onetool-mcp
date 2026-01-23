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
from pydantic import BaseModel, Field, PrivateAttr, field_validator

from ot.config.mcp import McpServerConfig, expand_secrets
from ot.paths import get_bundled_config_dir, get_effective_cwd, get_global_dir

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


# ==================== Tool Configuration Models ====================


class BraveConfig(BaseModel):
    """Brave search configuration."""

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )


class GroundConfig(BaseModel):
    """Grounding search configuration."""

    model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model for grounding",
    )


class Context7Config(BaseModel):
    """Context7 documentation API configuration."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )
    docs_limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Default docs result limit",
    )


class WebFetchConfig(BaseModel):
    """Web fetch configuration."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )
    max_length: int = Field(
        default=50000,
        ge=1000,
        le=500000,
        description="Max content length to return",
    )


class RipgrepConfig(BaseModel):
    """Ripgrep search configuration."""

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Search timeout in seconds",
    )


class CodeSearchConfig(BaseModel):
    """Code search configuration."""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default result limit",
    )


class DbConfig(BaseModel):
    """Database tools configuration."""

    max_chars: int = Field(
        default=4000,
        ge=100,
        le=100000,
        description="Truncation limit for results",
    )


class PageViewConfig(BaseModel):
    """Page view configuration."""

    sessions_dir: str = Field(
        default=".browse",
        description="Directory for browser sessions",
    )


class PackageConfig(BaseModel):
    """Package tools configuration."""

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )


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


class FileConfig(BaseModel):
    """File tool configuration."""

    allowed_dirs: list[str] = Field(
        default_factory=list,
        description="Allowed directories (relative to OT_CWD). Empty = cwd only.",
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            # Version control
            ".git",
            ".svn",
            ".hg",
            # Dependencies
            "node_modules",
            ".venv",
            "venv",
            # Python cache
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            "*.pyc",
            # Build artifacts
            "dist",
            "build",
            # Environment files
            ".env*",
            # OS files
            ".DS_Store",
            "Thumbs.db",
        ],
        description="Glob patterns to exclude from operations",
    )
    max_file_size: int = Field(
        default=10_000_000,
        ge=1000,
        le=100_000_000,
        description="Maximum file size in bytes (1KB-100MB)",
    )
    max_list_entries: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Maximum entries in directory listing (10-10000)",
    )
    backup_on_write: bool = Field(
        default=True,
        description="Create .bak backup before writes",
    )
    use_trash: bool = Field(
        default=False,
        description="Use send2trash for deletion (if available)",
    )


# ==================== Diagram Configuration Models ====================


class DiagramBackendConfig(BaseModel):
    """Kroki backend configuration for diagram rendering."""

    type: Literal["kroki"] = Field(
        default="kroki",
        description="Backend type (only kroki supported)",
    )
    remote_url: str = Field(
        default="https://kroki.io",
        description="Remote Kroki service URL",
    )
    self_hosted_url: str = Field(
        default="http://localhost:8000",
        description="Self-hosted Kroki URL",
    )
    prefer: Literal["remote", "self_hosted", "auto"] = Field(
        default="remote",
        description="Preferred backend: remote, self_hosted, or auto",
    )
    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )


class DiagramPolicyConfig(BaseModel):
    """Policy rules for diagram generation."""

    rules: str = Field(
        default="""\
NEVER use ASCII art or text-based diagrams in markdown.
Use the diagram tools for all visual representations.
Save output as SVG and reference in markdown.
Always generate source first, then render.""",
        description="Policy rules for LLM guidance",
    )
    preferred_format: Literal["svg", "png", "pdf"] = Field(
        default="svg",
        description="Default output format",
    )
    preferred_providers: list[str] = Field(
        default_factory=lambda: ["mermaid", "d2", "plantuml"],
        description="Preferred diagram providers in order",
    )


class DiagramOutputConfig(BaseModel):
    """Output settings for generated diagrams."""

    dir: str = Field(
        default="diagrams",
        description="Output directory for rendered diagrams (relative to project dir)",
    )
    naming: str = Field(
        default="{provider}_{name}_{timestamp}",
        description="Filename pattern (supports {provider}, {name}, {timestamp})",
    )
    default_format: Literal["svg", "png", "pdf"] = Field(
        default="svg",
        description="Default output format",
    )
    save_source: bool = Field(
        default=True,
        description="Save diagram source alongside rendered output",
    )


class DiagramProviderInstructions(BaseModel):
    """Instructions for a specific diagram provider."""

    when_to_use: str = Field(
        default="",
        description="Guidance on when to use this provider",
    )
    style_tips: str = Field(
        default="",
        description="Style and syntax tips",
    )
    syntax_guide: str = Field(
        default="",
        description="Link to syntax documentation",
    )
    example: str = Field(
        default="",
        description="Example diagram source",
    )


class DiagramTemplateRef(BaseModel):
    """Reference to a diagram template file."""

    provider: str = Field(
        ...,
        description="Diagram provider (mermaid, plantuml, d2)",
    )
    diagram_type: str = Field(
        ...,
        description="Type of diagram (sequence, flowchart, etc.)",
    )
    description: str = Field(
        default="",
        description="Template description",
    )
    file: str = Field(
        ...,
        description="Path to template file (relative to config)",
    )


class DiagramConfig(BaseModel):
    """Complete diagram tool configuration."""

    backend: DiagramBackendConfig = Field(
        default_factory=DiagramBackendConfig,
        description="Kroki backend settings",
    )
    policy: DiagramPolicyConfig = Field(
        default_factory=DiagramPolicyConfig,
        description="Policy rules for diagram generation",
    )
    output: DiagramOutputConfig = Field(
        default_factory=DiagramOutputConfig,
        description="Output settings",
    )
    instructions: dict[str, DiagramProviderInstructions] = Field(
        default_factory=dict,
        description="Provider-specific instructions",
    )
    templates: dict[str, DiagramTemplateRef] = Field(
        default_factory=dict,
        description="Named template references",
    )


class SecurityConfig(BaseModel):
    """Code validation security configuration.

    Controls code validation and which patterns are blocked or warned.
    Blocked patterns prevent code execution; warned patterns log but allow.

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
    - This prevents accidentally removing critical security patterns

    This simplified two-category design replaces the previous four categories
    (blocked_builtins, blocked_functions, warned_functions, warned_imports).
    The validator determines the match type based on the pattern structure.
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


class StatsConfig(BaseModel):
    """Runtime statistics collection configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable statistics collection",
    )
    persist_path: str = Field(
        default="stats.jsonl",
        description="Path to JSONL file for stats persistence (relative to log dir)",
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
    """Aggregated tool configurations."""

    brave: BraveConfig = Field(default_factory=BraveConfig)
    ground: GroundConfig = Field(default_factory=GroundConfig)
    context7: Context7Config = Field(default_factory=Context7Config)
    web_fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
    ripgrep: RipgrepConfig = Field(default_factory=RipgrepConfig)
    code_search: CodeSearchConfig = Field(default_factory=CodeSearchConfig)
    db: DbConfig = Field(default_factory=DbConfig)
    page_view: PageViewConfig = Field(default_factory=PageViewConfig)
    package: PackageConfig = Field(default_factory=PackageConfig)
    msg: MsgConfig = Field(default_factory=MsgConfig)
    file: FileConfig = Field(default_factory=FileConfig)
    diagram: DiagramConfig = Field(default_factory=DiagramConfig)
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

    tools_dir: list[str] = Field(
        default_factory=lambda: ["src/ot_tools/*.py"],
        description="Glob patterns for tool discovery",
    )
    secrets_file: str = Field(
        default="secrets.yaml",
        description="Path to secrets file (relative to config dir, or absolute)",
    )
    prompts: dict[str, Any] | None = Field(
        default=None,
        description="Inline prompts config (can also be loaded via include:)",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_dir: str = Field(
        default="../logs",
        description="Directory for log files (relative to config dir)",
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

    def get_tool_files(self) -> list[Path]:
        """Get list of tool files matching configured glob patterns.

        Returns:
            List of Path objects for tool files
        """
        tool_files: list[Path] = []
        for pattern in self.tools_dir:
            # Use glob.glob() for cross-platform compatibility and to support
            # both relative and absolute patterns in tools_dir configuration
            for match in glob.glob(pattern, recursive=True):  # noqa: PTH207
                path = Path(match)
                if path.is_file() and path.suffix == ".py":
                    tool_files.append(path)

        return sorted(set(tool_files))

    def _resolve_config_relative_path(self, path_str: str) -> Path:
        """Resolve a path relative to the config directory.

        Handles:
        - Absolute paths: returned as-is
        - ~ expansion: expanded to home directory
        - Relative paths: resolved relative to config directory

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

        # Fallback: resolve relative to cwd/.onetool
        return (get_effective_cwd() / ".onetool" / path).resolve()

    def get_secrets_file_path(self) -> Path:
        """Get the resolved path to the secrets configuration file.

        Path is resolved relative to the config file directory.

        Returns:
            Absolute Path to secrets file
        """
        return self._resolve_config_relative_path(self.secrets_file)

    def get_log_dir_path(self) -> Path:
        """Get the resolved path to the log directory.

        Path is resolved relative to the config file directory.

        Returns:
            Absolute Path to log directory
        """
        return self._resolve_config_relative_path(self.log_dir)

    def get_stats_file_path(self) -> Path:
        """Get the resolved path to the stats CSV file.

        Stats file is stored in the log directory alongside other logs.

        Returns:
            Absolute Path to stats file
        """
        return self.get_log_dir_path() / self.tools.stats.persist_path


def _resolve_config_path(config_path: Path | str | None) -> Path | None:
    """Resolve config path from explicit path, env var, or default locations.

    Resolution order:
    1. Explicit config_path if provided
    2. OT_SERVE_CONFIG env var
    3. cwd/.onetool/ot-serve.yaml
    4. ~/.onetool/ot-serve.yaml
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
    project_config = cwd / ".onetool" / "ot-serve.yaml"
    if project_config.exists():
        return project_config

    global_config = get_global_dir() / "ot-serve.yaml"
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
    include_path_str: str, config_dir: Path
) -> Path | None:
    """Resolve an include path using three-tier fallback.

    Search order:
    1. config_dir (project or wherever the main config is)
    2. global (~/.onetool/)
    3. bundled (package defaults)

    Supports:
    - Absolute paths (used as-is)
    - ~ expansion (expands to home directory)
    - Relative paths (searched in three-tier order)

    Args:
        include_path_str: Path string from include directive
        config_dir: Directory of the config file containing the include

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

    # Tier 1: config_dir (project or current config location)
    tier1 = (config_dir / include_path).resolve()
    if tier1.exists():
        logger.debug(f"Include resolved (config_dir): {tier1}")
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
    data: dict[str, Any], config_dir: Path, seen_paths: set[Path] | None = None
) -> dict[str, Any]:
    """Load and merge files from 'include:' list into config data.

    Files are merged left-to-right (later files override earlier).
    Inline content in the main file overrides everything.

    Include resolution uses three-tier fallback:
    1. config_dir (project or current config location)
    2. global (~/.onetool/)
    3. bundled (package defaults)

    Args:
        data: Config data dict containing optional 'include' key
        config_dir: Directory for resolving relative paths
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
        include_path = _resolve_include_path(include_path_str, config_dir)

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

            # Recursively process nested includes
            new_seen = seen_paths | {include_path}
            include_data = _load_includes(
                include_data, include_path.parent, new_seen
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
        global_config_path = get_global_dir() / "ot-serve.yaml"
        if global_config_path.exists():
            # Skip if this is the same file we're already loading
            if current_config_path and global_config_path.resolve() == current_config_path.resolve():
                logger.debug("Skipping global inheritance (loading global config itself)")
            else:
                try:
                    raw_data = _load_yaml_file(global_config_path)
                    # Process includes in global config (with bundled fallback)
                    data = _load_includes(raw_data, global_config_path.parent)
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
            # Process includes in bundled config (within bundled dir)
            data = _load_includes(raw_data, bundled_config_path.parent)
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
        config._config_dir = get_effective_cwd() / ".onetool"
        return config

    logger.debug(f"Loading config from {resolved_path}")

    raw_data = _load_yaml_file(resolved_path)
    expanded_data = _expand_secrets_recursive(raw_data)

    # Process includes before validation (merges external files)
    config_dir = resolved_path.parent.resolve()
    merged_data = _load_includes(expanded_data, config_dir)

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
