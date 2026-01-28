"""YAML configuration loading for harness scenarios and tasks.

Loads ot-dev.yaml with test scenarios and harness configuration.
Supports variable expansion from bench-secrets.yaml in the format ${VAR_NAME}.

Example ot-dev.yaml:

    defaults:
      model: openai/gpt-5-mini
      timeout: 120

    servers:
      onetool:
        type: stdio
        command: uv
        args: ["run", "onetool"]

    scenarios:
      - name: Basic Tests
        tasks:
          - name: hello world
            prompt: Say hello
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from ot_bench.secrets import get_bench_secret

if TYPE_CHECKING:
    from pathlib import Path


def expand_secrets(value: str) -> str:
    """Expand variables in a string using bench-secrets.yaml only.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.
    Reads from bench-secrets.yaml only - does NOT read from os.environ.
    Raises error if variable not found and no default provided.

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded from bench secrets.

    Raises:
        ValueError: If variable not found in secrets and no default.
    """
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
    missing_vars: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Read from bench secrets only - no os.environ
        secret_value = get_bench_secret(var_name)
        if secret_value:
            return secret_value
        if default_value is not None:
            return default_value
        missing_vars.append(var_name)
        return match.group(0)

    result = pattern.sub(replace, value)

    if missing_vars:
        raise ValueError(
            f"Missing variables in bench-secrets.yaml: {', '.join(missing_vars)}. "
            f"Add them to .onetool/config/bench-secrets.yaml or use ${{VAR:-default}} syntax."
        )

    return result


def expand_subprocess_env(value: str) -> str:
    """Expand ${VAR} for subprocess environment values.

    Reads from bench secrets first, then os.environ for pass-through.
    This is the ONLY place where reading os.environ is allowed for bench,
    enabling explicit env var pass-through to subprocesses.

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded. Empty string if not found.
    """
    import os

    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Bench secrets first
        secret_value = get_bench_secret(var_name)
        if secret_value:
            return secret_value
        # Then os.environ (for pass-through like ${HOME})
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        # Use default if provided
        if default_value is not None:
            return default_value
        # Empty string if not found
        return ""

    return pattern.sub(replace, value)


def expand_secrets_in_dict(data: Any, skip_keys: set[str] | None = None) -> Any:
    """Recursively expand secrets in a dict/list structure.

    Args:
        data: Dict, list, or scalar value.
        skip_keys: Set of dict keys whose values should not be expanded.
            Used to skip 'env' values which are expanded later by subprocess.

    Returns:
        Structure with all string values expanded.
    """
    if skip_keys is None:
        skip_keys = {"env"}

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in skip_keys:
                # Don't expand these - they're handled by expand_subprocess_env later
                result[k] = v
            else:
                result[k] = expand_secrets_in_dict(v, skip_keys)
        return result
    elif isinstance(data, list):
        return [expand_secrets_in_dict(v, skip_keys) for v in data]
    elif isinstance(data, str):
        return expand_secrets(data)
    return data


class ServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    type: Literal["http", "stdio"] = Field(description="Server connection type")
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
    timeout: int | None = Field(
        default=None, description="Connection timeout in seconds (overrides default)"
    )

    @field_validator("url", "command", mode="before")
    @classmethod
    def expand_secrets_validator(cls, v: str | None) -> str | None:
        """Expand secrets in URL and command."""
        if v is None:
            return None
        return expand_secrets(v)


class EvaluateConfig(BaseModel):
    """Configuration for evaluation (LLM or deterministic)."""

    # For deterministic checks - can be string, list, dict, number, bool
    expected: str | list[Any] | dict[str, Any] | int | float | bool | None = Field(
        default=None,
        description="Expected value(s) for deterministic evaluation",
    )

    # For regex pattern matching
    regex: str | None = Field(
        default=None,
        description="Regex pattern to match against response",
    )
    expect_match: bool = Field(
        default=True,
        description="If True, regex must match. If False, regex must NOT match.",
    )

    # For error tests - when True, test expects an error response
    # If LLM "fixes" the code and it succeeds, that's a failure
    expect_error: bool = Field(
        default=False,
        description="When True, test expects error/failure. Success without error pattern is a failure.",
    )

    # For LLM-as-judge evaluation
    prompt: str | None = Field(
        default=None,
        description="Evaluation prompt template with {response} and {expected}",
    )
    model: str | None = Field(
        default=None,
        description="Model to use for LLM evaluation (required if using LLM-as-judge)",
    )


class TaskConfig(BaseModel):
    """Configuration for a single task (direct or harness).

    Task types:
        - direct: Direct MCP tool invocation without LLM
        - harness: LLM benchmark with optional MCP servers (default)
    """

    name: str = Field(description="Task name")
    type: Literal["direct", "harness"] = Field(
        default="harness",
        description="Task type: 'direct' for MCP tool call, 'harness' for LLM benchmark",
    )

    # Common fields
    server: str | list[str] | None = Field(
        default=None, description="Server name(s) from servers - single or list"
    )
    timeout: int | None = Field(default=None, description="Timeout in seconds")
    tags: list[str] = Field(
        default_factory=list, description="Tags for filtering tasks"
    )

    # Harness-specific fields (type: harness)
    prompt: str | None = Field(
        default=None, description="Prompt to send to LLM (required for harness type)"
    )
    model: str | None = Field(default=None, description="Model override (harness only)")
    evaluate: str | EvaluateConfig | None = Field(
        default=None,
        description="Evaluation config (harness only)",
    )

    # Direct-specific fields (type: direct)
    tool: str | None = Field(
        default=None, description="Tool name to call (required for direct type)"
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments (direct only)"
    )

    @field_validator("tags", mode="before")
    @classmethod
    def tags_default_empty(cls, v: list[str] | None) -> list[str]:
        """Convert None to empty list for tags."""
        return v if v is not None else []

    def model_post_init(self, __context: Any) -> None:
        """Validate type-specific required fields."""
        if self.type == "direct":
            if not self.tool:
                raise ValueError(
                    f"Task '{self.name}': type 'direct' requires 'tool' field"
                )
            if not self.server:
                raise ValueError(
                    f"Task '{self.name}': type 'direct' requires 'server' field"
                )
        elif self.type == "harness":
            if not self.prompt:
                raise ValueError(
                    f"Task '{self.name}': type 'harness' requires 'prompt' field"
                )


class ScenarioConfig(BaseModel):
    """Configuration for a benchmark scenario."""

    name: str = Field(description="Scenario name")
    description: str = Field(default="", description="Scenario description")
    tasks: list[TaskConfig] = Field(description="List of tasks in the scenario")


class DefaultsConfig(BaseModel):
    """Default configuration values."""

    timeout: int = Field(default=120, description="Default timeout in seconds")
    model: str = Field(default="openai/gpt-5-mini", description="Default model")
    system_prompt: str | None = Field(
        default=None, description="System prompt to prepend to all tasks"
    )


class HarnessConfig(BaseModel):
    """Root configuration for harness YAML files."""

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    servers: dict[str, ServerConfig] = Field(default_factory=dict)
    evaluators: dict[str, EvaluateConfig] = Field(
        default_factory=dict,
        description="Named evaluators that can be referenced by tasks",
    )
    evaluate: EvaluateConfig | None = Field(
        default=None,
        description="Legacy: default evaluator (deprecated, use evaluators)",
    )
    scenarios: list[ScenarioConfig] = Field(default_factory=list)


def load_harness_config(path: Path) -> HarnessConfig:
    """Load and validate a harness YAML configuration.

    Args:
        path: Path to the YAML file.

    Returns:
        Validated HarnessConfig.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as f:
        raw_data = yaml.safe_load(f)

    if raw_data is None:
        raw_data = {}

    # Expand secrets
    data = expand_secrets_in_dict(raw_data)

    return HarnessConfig.model_validate(data)


def _convert_legacy_tools_config(data: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy tools config to unified format.

    Legacy tools configs have tasks with 'tool' field but no 'type' field.
    This adds 'type: direct' to such tasks.

    Args:
        data: Parsed YAML data.

    Returns:
        Data with legacy tasks converted to unified format.
    """
    scenarios = data.get("scenarios", [])
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        tasks = scenario.get("tasks", [])
        for task in tasks:
            if not isinstance(task, dict):
                continue
            # If task has 'tool' but no 'type', it's a legacy direct task
            if "tool" in task and "type" not in task:
                task["type"] = "direct"
    return data


def load_config(path: Path) -> HarnessConfig:
    """Load and validate a YAML configuration file.

    Supports both unified configs (with explicit type field) and
    legacy configs (auto-detects direct vs harness based on content).

    Args:
        path: Path to the YAML file.

    Returns:
        Validated HarnessConfig.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as f:
        raw_data = yaml.safe_load(f)

    if raw_data is None:
        raw_data = {}

    # Expand secrets
    data = expand_secrets_in_dict(raw_data)

    # Convert legacy tools config format if needed
    data = _convert_legacy_tools_config(data)

    return HarnessConfig.model_validate(data)
