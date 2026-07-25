"""Pydantic models for OneTool configuration.

Scalar operational defaults live in model definitions. Large prompts and
templates live in template files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

# ==================== Snippet Models ====================


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


# ==================== LLM Configuration ====================


class LlmConfig(BaseModel):
    """Top-level shared LLM configuration.

    All tool packs (ot_llm, ot_image, mem, knowledge, ctx) fall back to these
    values when their own ``base_url`` / ``model`` settings are not set.
    Configure once here instead of repeating in every tool section.
    """

    model: str = Field(default="gpt-5.4-nano", description="Default completion model")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="Default embedding model"
    )
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible API base URL",
    )
    max_tokens: int = Field(default=4096, description="Max output tokens")


# ==================== Security Configuration ====================


class BuiltinsConfig(BaseModel):
    """Builtins allowlist configuration."""

    allow: list[str] = Field(
        default_factory=lambda: [
            # Types
            "bool",
            "bytes",
            "dict",
            "float",
            "frozenset",
            "int",
            "list",
            "set",
            "str",
            "tuple",
            "type",
            # Functions
            "abs",
            "all",
            "any",
            "ascii",
            "callable",
            "chr",
            "delattr",
            "dir",
            "divmod",
            "enumerate",
            "filter",
            "format",
            "getattr",
            "hasattr",
            "hash",
            "id",
            "isinstance",
            "issubclass",
            "iter",
            "len",
            "map",
            "max",
            "min",
            "next",
            "ord",
            "pow",
            "print",
            "range",
            "repr",
            "reversed",
            "round",
            "setattr",
            "slice",
            "sorted",
            "sum",
            "vars",
            "zip",
            # Exceptions
            "*Error",
            "*Exception",
            "StopIteration",
        ],
        description="Allowed builtin functions and types",
    )


class ImportsConfig(BaseModel):
    """Imports allowlist configuration."""

    allow: list[str] = Field(
        default_factory=lambda: [
            # Note: pathlib intentionally excluded - use file.* tools instead for sandboxed filesystem access
            "abc",
            "array",
            "base64",
            "bisect",
            "calendar",
            "collections",
            "copy",
            "csv",
            "dataclasses",
            "datetime",
            "decimal",
            "difflib",
            "enum",
            "fractions",
            "functools",
            "hashlib",
            "heapq",
            "html",
            "html.parser",
            "itertools",
            "json",
            "math",
            "operator",
            "random",
            "re",
            "statistics",
            "string",
            "textwrap",
            "time",
            "types",
            "typing",
            "urllib.parse",
            "uuid",
            "zoneinfo",
        ],
        description="Allowed import modules",
    )
    warn: list[str] = Field(
        default_factory=lambda: ["yaml"],
        description="Imports that trigger warnings but are allowed",
    )


class CallsConfig(BaseModel):
    """Qualified calls configuration."""

    allow: list[str] = Field(
        default_factory=list,
        description="Allowed qualified function calls (e.g., 'json.loads')",
    )
    block: list[str] = Field(
        default_factory=list,
        description="Blocked qualified function calls (e.g., 'pickle.*')",
    )
    warn: list[str] = Field(
        default_factory=list,
        description="Qualified calls that trigger warnings",
    )


class DundersConfig(BaseModel):
    """Magic variable (dunder) configuration."""

    allow: list[str] = Field(
        default_factory=lambda: ["__format__", "__sanitize__", "__force_context__"],
        description="Allowed magic variables (e.g., '__format__')",
    )


class OutputSanitizationConfig(BaseModel):
    """Output sanitization configuration for prompt injection protection.

    Protects against indirect prompt injection by sanitizing tool outputs
    that may contain malicious payloads from external content.

    Three-layer defense:
    1. Trigger sanitization: Replace __onetool, __ot, mcp__onetool patterns
    2. Tag sanitization: Remove <external-content-*> patterns
    3. GUID-tagged boundaries: Wrap content in unpredictable tags
    """

    enabled: bool = Field(
        default=True,
        description="Global toggle for output sanitization",
    )


class SecurityConfig(BaseModel):
    """Code validation security configuration.

    Allowlist-based security model: block everything by default, explicitly
    allow what's safe. Tool namespaces (ot.*, brave.*, etc.) are auto-allowed.

    Configuration structure:
        security:
          builtins:
            allow: [str, int, list, ...]
          imports:
            allow: [json, re, math, ...]
            warn: [yaml]
          calls:
            block: [pickle.*, yaml.load]
            warn: [random.seed]
          dunders:
            allow: [__format__, __sanitize__]

    Patterns support fnmatch wildcards:
    - '*' matches any characters (e.g., 'subprocess.*' matches 'subprocess.run')
    - '?' matches a single character
    - '[seq]' matches any character in seq
    """

    # Cached frozensets (computed lazily on first access)
    _allowed_builtins: frozenset[str] | None = PrivateAttr(default=None)
    _allowed_imports: frozenset[str] | None = PrivateAttr(default=None)
    _warned_imports: frozenset[str] | None = PrivateAttr(default=None)
    _blocked_calls: frozenset[str] | None = PrivateAttr(default=None)
    _warned_calls: frozenset[str] | None = PrivateAttr(default=None)
    _allowed_calls: frozenset[str] | None = PrivateAttr(default=None)
    _allowed_dunders: frozenset[str] | None = PrivateAttr(default=None)

    validate_code: bool = Field(
        default=True,
        description="Enable AST-based code validation before execution",
    )

    enabled: bool = Field(
        default=True,
        description="Enable security pattern checking (requires validate_code)",
    )

    builtins: BuiltinsConfig = Field(
        default_factory=BuiltinsConfig,
        description="Builtins allowlist configuration",
    )

    imports: ImportsConfig = Field(
        default_factory=ImportsConfig,
        description="Imports allowlist configuration",
    )

    calls: CallsConfig = Field(
        default_factory=CallsConfig,
        description="Qualified calls configuration",
    )

    dunders: DundersConfig = Field(
        default_factory=DundersConfig,
        description="Magic variable (dunder) configuration",
    )

    sanitize: OutputSanitizationConfig = Field(
        default_factory=OutputSanitizationConfig,
        description="Output sanitization for prompt injection protection",
    )

    def get_allowed_builtins(self) -> frozenset[str]:
        """Get the set of allowed builtins (cached)."""
        if self._allowed_builtins is None:
            self._allowed_builtins = frozenset(self.builtins.allow)
        return self._allowed_builtins

    def get_allowed_imports(self) -> frozenset[str]:
        """Get the set of allowed imports (cached)."""
        if self._allowed_imports is None:
            self._allowed_imports = frozenset(self.imports.allow)
        return self._allowed_imports

    def get_warned_imports(self) -> frozenset[str]:
        """Get the set of imports that trigger warnings (cached)."""
        if self._warned_imports is None:
            self._warned_imports = frozenset(self.imports.warn)
        return self._warned_imports

    def get_blocked_calls(self) -> frozenset[str]:
        """Get the set of blocked qualified calls (cached)."""
        if self._blocked_calls is None:
            self._blocked_calls = frozenset(self.calls.block)
        return self._blocked_calls

    def get_warned_calls(self) -> frozenset[str]:
        """Get the set of qualified calls that trigger warnings (cached)."""
        if self._warned_calls is None:
            self._warned_calls = frozenset(self.calls.warn)
        return self._warned_calls

    def get_allowed_calls(self) -> frozenset[str]:
        """Get the set of explicitly allowed qualified calls (cached)."""
        if self._allowed_calls is None:
            self._allowed_calls = frozenset(self.calls.allow)
        return self._allowed_calls

    def get_allowed_dunders(self) -> frozenset[str]:
        """Get the set of allowed magic variables (cached)."""
        if self._allowed_dunders is None:
            self._allowed_dunders = frozenset(self.dunders.allow)
        return self._allowed_dunders


# ==================== Output Configuration ====================


class OutputConfig(BaseModel):
    """Large output handling configuration.

    When tool outputs exceed max_inline_size, they are stored to disk
    and a summary with a query handle is returned instead.
    """

    max_inline_size: int = Field(
        default=5000,
        ge=0,
        description="Max output size in bytes before storing to disk. Set to 0 to disable.",
    )
    result_store_dir: str = Field(
        default="runtime/reports",
        description="Directory for result files (relative to .onetool/)",
    )
    sessions_dir: str = Field(
        default="runtime/sessions",
        description="Directory for session subdirectories (relative to .onetool/)",
    )
    session_retention_days: int = Field(
        default=1,
        ge=0,
        description="Number of days to retain session directories before purging at startup",
    )
    result_ttl: int = Field(
        default=3600,
        ge=0,
        description="Time-to-live in seconds for stored results (0 = no expiry)",
    )
    preview_lines: int = Field(
        default=10,
        ge=0,
        description="Number of preview lines to include in summary",
    )
    preview_max_chars: int = Field(
        default=500,
        ge=0,
        description="Max characters per preview line (0 = no limit)",
    )


# ==================== Telemetry Configuration ====================


class TelemetryConfig(BaseModel):
    """Anonymous startup telemetry configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable anonymous startup telemetry (PostHog)",
    )


# ==================== Stats Configuration ====================


class StatsConfig(BaseModel):
    """Runtime statistics collection configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable statistics collection",
    )
    persist_dir: str = Field(
        default="runtime/stats",
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
        default="anthropic/claude-opus-4-6",
        description="Model for cost estimation (e.g., anthropic/claude-opus-4-6)",
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


# ==================== MCP Server Configuration ====================


class AuthConfig(BaseModel):
    """Authentication configuration for MCP servers."""

    type: Literal["oauth", "bearer"] = Field(
        description="Authentication type",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="OAuth scopes (for type=oauth)",
    )
    token: str | None = Field(
        default=None,
        description="Bearer token (for type=bearer, supports ${VAR} expansion)",
    )


class McpServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    type: Literal["http", "stdio"] = Field(description="Server connection type")
    enabled: bool = Field(default=True, description="Whether this server is enabled")
    url: str | None = Field(default=None, description="URL for HTTP servers")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for HTTP servers"
    )
    command: str | None = Field(default=None, description="Command for stdio servers")
    args: list[str] = Field(
        default_factory=list, description="Arguments for stdio command"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for stdio servers"
    )
    inherit_env: bool = Field(
        default=False,
        description="Inherit parent process environment variables (stdio servers)",
    )
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    auth: AuthConfig | None = Field(
        default=None,
        description="Authentication configuration for HTTP servers",
    )
    description: str | None = Field(
        default=None,
        description="Brief description of this server's purpose",
    )
    source: str | None = Field(
        default=None,
        description="Authoritative source URL for this server (e.g. GitHub repo)",
    )
    instructions: str | None = Field(
        default=None,
        description="Agent instructions for using this server's tools (surfaced in MCP instructions)",
    )
    tool_prefix: str | None = Field(
        default=None,
        description=(
            "Prefix that this server's tools carry (e.g. 'docs_'). "
            "When set, callers may omit the prefix: knowledge.search_documentation() "
            "resolves to the tool docs_search_documentation."
        ),
    )


# ==================== Direct Configuration ====================


class DirectHostConfig(BaseModel):
    """MCP-owned direct API settings for `onetool direct run`."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        strict=True,
        description="Bind an authenticated loopback direct API from the MCP process.",
    )
    port: int = Field(
        default=8765,
        ge=1,
        le=65535,
        description=(
            "Preferred MCP direct API port. "
            "MCP startup tries this port first, then increments until a free port is found."
        ),
    )


class DirectConfig(BaseModel):
    """Direct API configuration for MCP-owned direct execution."""

    model_config = ConfigDict(extra="forbid")

    host: DirectHostConfig = Field(
        default_factory=DirectHostConfig,
        description="MCP-owned direct API settings.",
    )


class ConsoleConfig(BaseModel):
    """MCP-side Console outbox producer queue settings."""

    model_config = ConfigDict(extra="forbid")

    max_queue_messages: int = Field(
        default=1000,
        ge=1,
        description="Maximum Console messages retained by the MCP producer queue.",
    )


# ==================== Tools Configuration ====================


class ToolsConfig(BaseModel):
    """Aggregated tool configurations.

    Core configs (msg, stats) are typed fields. Tool-specific configs
    (brave, ground, etc.) are allowed as extra fields and accessed via
    get_tool_config() with schemas defined in tool files.
    """

    model_config = ConfigDict(extra="allow")

    # Core configs - always available
    stats: StatsConfig = Field(default_factory=StatsConfig)


# ==================== Root Configuration ====================


class OneToolConfig(BaseModel):
    """Root configuration for OneTool."""

    model_config = ConfigDict(extra="forbid")

    # Private attribute to track config file location (set by load_config())
    _config_dir: Path = PrivateAttr()

    version: int = Field(
        default=2,
        description="Config schema version for migration support",
    )

    include: list[str] = Field(
        default_factory=list,
        description="Files to deep-merge into config (processed before validation)",
    )

    # Root-level environment variables for subprocesses
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Shared environment variables for all MCP servers",
    )

    llm: LlmConfig = Field(
        default_factory=LlmConfig, description="llm tool configuration"
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

    direct: DirectConfig = Field(
        default_factory=DirectConfig,
        description="MCP-owned direct API configuration",
    )

    console: ConsoleConfig = Field(
        default_factory=ConsoleConfig,
        description="MCP-side Console outbox producer queue configuration",
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
        description="Runtime statistics collection configuration",
    )

    telemetry: TelemetryConfig = Field(
        default_factory=TelemetryConfig,
        description="Anonymous startup telemetry configuration",
    )

    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Large output handling configuration",
    )

    tools_dir: list[str] = Field(
        default_factory=lambda: ["tools/*.py"],
        description="Glob patterns for tool discovery (relative to .onetool/, or absolute)",
    )
    prompts: dict[str, Any] | None = Field(
        default=None,
        description="Inline prompts config (can also be loaded via include:)",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_dir: str = Field(
        default="runtime/logs",
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

    def get_tool_files(self) -> list[Path]:
        """Get list of tool files matching configured glob patterns.

        Pattern resolution (all relative to OT_DIR .onetool/):
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory
        - Relative patterns: resolved relative to OT_DIR (.onetool/)

        Returns:
            List of Path objects for tool files

        Raises:
            RuntimeError: If _config_dir not set (load_config() not called)
        """
        import glob

        tool_files: list[Path] = []

        try:
            ot_dir = self._config_dir
        except AttributeError as err:
            raise RuntimeError(
                "_config_dir not set — was load_config() called?"
            ) from err

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
        - Relative paths: resolved relative to .onetool/ directory (where config file lives)

        Note: Does NOT expand ${VAR} - use ~/path instead of ${HOME}/path.

        Args:
            path_str: Path string to resolve

        Returns:
            Resolved absolute Path

        Raises:
            RuntimeError: If _config_dir not set (load_config() not called)
        """
        # Only expand ~ (no ${VAR} expansion)
        path = Path(path_str).expanduser()

        # If absolute after expansion, use as-is
        if path.is_absolute():
            return path

        # Resolve relative to .onetool/ directory (flat layout: config is directly in .onetool/)
        try:
            return (self._config_dir / path).resolve()
        except AttributeError as err:
            raise RuntimeError(
                "_config_dir not set — was load_config() called?"
            ) from err

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

    def get_result_store_path(self) -> Path:
        """Get the resolved path to the result store directory.

        Path is resolved relative to the .onetool/ directory.

        Returns:
            Absolute Path to result store directory
        """
        return self._resolve_onetool_relative_path(self.output.result_store_dir)
