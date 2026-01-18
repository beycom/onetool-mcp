"""YAML configuration loading for OneTool.

Loads ot-serve.yaml with tool discovery patterns and settings.

Example ot-serve.yaml:

    tools_dir:
      - src/ot_tools/*.py

    transform:
      model: anthropic/claude-3-5-haiku

    # prompts_file and secrets_file resolve relative to this config file
    prompts_file: prompts.yaml   # default: sibling of ot-serve.yaml
    secrets_file: secrets.yaml   # default: sibling of ot-serve.yaml

    # Use !include for modular configs
    diagram: !include diagram.yaml
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from ot.config.mcp import McpServerConfig, expand_secrets
from ot.paths import get_effective_cwd, get_global_dir


# Custom YAML Loader with !include support
class IncludeLoader(yaml.SafeLoader):
    """YAML loader that supports !include tag for modular configs.

    The !include tag loads another YAML file and inlines its contents.
    Paths are resolved relative to the including file.

    Example:
        # In ot-serve.yaml
        diagram: !include diagram.yaml

        # In diagram.yaml
        backend:
          type: kroki
          prefer: remote
    """

    _base_path: Path | None = None

    @classmethod
    def with_base_path(cls, base_path: Path) -> type[IncludeLoader]:
        """Create a loader class with a specific base path for includes."""

        class BoundLoader(cls):  # type: ignore[valid-type,misc]
            _base_path = base_path

        return BoundLoader


def _include_constructor(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Handle !include YAML tag by loading the referenced file."""
    include_path = loader.construct_scalar(node)  # type: ignore[arg-type]

    if loader._base_path is None:
        raise yaml.YAMLError(f"Cannot resolve !include path: {include_path}")

    # Resolve path relative to the including file
    resolved = (loader._base_path / include_path).resolve()

    if not resolved.exists():
        logger.warning(f"!include file not found: {resolved}")
        return None

    try:
        with resolved.open() as f:
            # Create a new loader with the included file's directory as base
            bound_loader = IncludeLoader.with_base_path(resolved.parent)
            return yaml.load(f, Loader=bound_loader)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error loading !include {include_path}: {e}") from e


# Register the !include constructor
IncludeLoader.add_constructor("!include", _include_constructor)

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


class OneToolConfig(BaseModel):
    """Root configuration for OneTool V1."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Private attribute to track config file location (not serialized)
    _config_dir: Path | None = PrivateAttr(default=None)

    version: int = Field(
        default=1,
        description="Config schema version for migration support",
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

    snippets_dir: list[str] = Field(
        default_factory=list,
        description="Glob patterns for external snippet files to load",
    )

    servers: dict[str, McpServerConfig] = Field(
        default_factory=dict,
        description="External MCP servers to proxy through OneTool",
    )

    tools: ToolsConfig = Field(
        default_factory=ToolsConfig,
        description="Tool-specific configuration (timeouts, limits, etc.)",
    )

    tools_dir: list[str] = Field(
        default_factory=lambda: ["src/ot_tools/*.py"],
        description="Glob patterns for tool discovery",
    )
    prompts_file: str = Field(
        default="prompts.yaml",
        description="Path to prompts file (relative to config dir, or absolute)",
    )
    secrets_file: str = Field(
        default="secrets.yaml",
        description="Path to secrets file (relative to config dir, or absolute)",
    )
    prompts: dict[str, Any] | None = Field(
        default=None,
        description="Inline prompts config (overrides prompts_file if set)",
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
    validate_code: bool = Field(
        default=True, description="Whether to validate code before execution"
    )

    def get_tool_files(self) -> list[Path]:
        """Get list of tool files matching configured glob patterns.

        Returns:
            List of Path objects for tool files
        """
        tool_files: list[Path] = []
        for pattern in self.tools_dir:
            # NOTE: Use glob.glob() not Path().glob() - pathlib doesn't support
            # absolute patterns like "/path/to/tools/**/*.py" (raises NotImplementedError)
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

    def get_prompts_file_path(self) -> Path:
        """Get the resolved path to the prompts configuration file.

        Path is resolved relative to the config file directory.

        Returns:
            Absolute Path to prompts file
        """
        return self._resolve_config_relative_path(self.prompts_file)

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

    def load_external_snippets(self) -> None:
        """Load snippets from external files and merge with inline snippets.

        External snippets are loaded first, then inline snippets override them.
        This method modifies self.snippets in place.

        Files are matched using glob patterns from snippets_dir.
        Invalid files are logged and skipped.
        """
        if not self.snippets_dir:
            return

        # Store inline snippets (these take precedence)
        inline_snippets = dict(self.snippets)

        # Load external snippets
        external_snippets: dict[str, SnippetDef] = {}

        for pattern in self.snippets_dir:
            # Resolve path relative to config directory
            resolved_path = self._resolve_config_relative_path(pattern)

            # Find matching files
            if "*" in pattern:
                # Glob pattern - use parent directory and glob the filename
                files = sorted(resolved_path.parent.glob(resolved_path.name))
            else:
                # Single file
                files = [resolved_path] if resolved_path.exists() else []

            if not files:
                logger.warning(f"No snippet files found matching: {pattern}")
                continue

            for file_path in files:
                try:
                    with file_path.open() as f:
                        data = yaml.safe_load(f)

                    if not data or "snippets" not in data:
                        logger.debug(f"No snippets key in {file_path}")
                        continue

                    for name, snippet_data in data["snippets"].items():
                        if name in external_snippets:
                            logger.warning(
                                f"Snippet '{name}' overridden by {file_path}"
                            )
                        external_snippets[name] = SnippetDef.model_validate(
                            snippet_data
                        )

                    logger.debug(
                        f"Loaded {len(data['snippets'])} snippets from {file_path}"
                    )

                except yaml.YAMLError as e:
                    logger.error(f"Invalid YAML in {file_path}: {e}")
                except Exception as e:
                    logger.error(f"Failed to load snippets from {file_path}: {e}")

        # Merge: external first, then inline overrides
        merged_snippets = external_snippets.copy()

        for name, snippet_def in inline_snippets.items():
            if name in external_snippets:
                logger.debug(f"Inline snippet '{name}' overrides external")
            merged_snippets[name] = snippet_def

        self.snippets = merged_snippets

        if external_snippets:
            logger.info(
                f"Loaded {len(external_snippets)} external snippets, "
                f"{len(inline_snippets)} inline"
            )


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

    Supports !include tags for modular configuration files.

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
            # Use IncludeLoader to support !include tags
            bound_loader = IncludeLoader.with_base_path(config_path.parent)
            raw_data = yaml.load(f, Loader=bound_loader)
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


def load_config(config_path: Path | str | None = None) -> OneToolConfig:
    """Load OneTool configuration from YAML file.

    Resolution order (when config_path is None):
    1. OT_SERVE_CONFIG env var
    2. cwd/.onetool/ot-serve.yaml
    3. ~/.onetool/ot-serve.yaml
    4. Built-in defaults

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
        config.load_external_snippets()
        return config

    logger.debug(f"Loading config from {resolved_path}")

    raw_data = _load_yaml_file(resolved_path)
    expanded_data = _expand_secrets_recursive(raw_data)

    _validate_version(expanded_data, resolved_path)
    _remove_legacy_fields(expanded_data)

    try:
        config = OneToolConfig.model_validate(expanded_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {resolved_path}: {e}") from e

    config._config_dir = resolved_path.parent.resolve()
    config.load_external_snippets()

    logger.info(f"Config loaded: version {config.version}")

    return config


# Global config instance
_config: OneToolConfig | None = None


def get_config(
    config_path: Path | str | None = None, reload: bool = False
) -> OneToolConfig:
    """Get or load the global configuration.

    Args:
        config_path: Path to config file (only used on first load)
        reload: Force reload configuration

    Returns:
        OneToolConfig instance
    """
    global _config

    if _config is None or reload:
        _config = load_config(config_path)

    return _config
