"""Prompts loader for externalized MCP server instructions.

Loads prompts from prompts.yaml. File must exist and contain instructions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field


class ToolPrompt(BaseModel):
    """Prompt configuration for a specific tool."""

    description: str | None = Field(
        default=None, description="Override tool description"
    )
    examples: list[str] = Field(default_factory=list, description="Usage examples")


class PromptsConfig(BaseModel):
    """Configuration for MCP server prompts and tool descriptions."""

    instructions: str = Field(
        description="Main server instructions shown to the LLM",
    )
    tools: dict[str, ToolPrompt] = Field(
        default_factory=dict,
        description="Per-tool prompt overrides",
    )
    templates: dict[str, str] = Field(
        default_factory=dict,
        description="Reusable prompt templates with {variable} placeholders",
    )
    packs: dict[str, str] = Field(
        default_factory=dict,
        description="Per-pack instructions (e.g., excel, github)",
    )


class PromptsError(Exception):
    """Error loading prompts configuration."""


def _get_bundled_prompts_path() -> Path:
    """Get path to bundled default prompts.yaml."""
    return Path(__file__).parent / "config" / "defaults" / "prompts.yaml"


def load_prompts(prompts_path: Path | str | None = None) -> PromptsConfig:
    """Load prompts configuration from YAML file.

    Args:
        prompts_path: Path to prompts file. Falls back to bundled default.

    Returns:
        PromptsConfig with loaded prompts.

    Raises:
        PromptsError: If file is invalid or has no instructions.
    """
    if prompts_path is not None:
        prompts_path = Path(prompts_path)
        if not prompts_path.exists():
            raise PromptsError(f"Prompts file not found: {prompts_path}")
    else:
        # Try config/prompts.yaml, fall back to bundled default
        prompts_path = Path("config/prompts.yaml")
        if not prompts_path.exists():
            prompts_path = _get_bundled_prompts_path()

    logger.debug(f"Loading prompts from {prompts_path}")

    try:
        with prompts_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PromptsError(f"Invalid YAML in {prompts_path}: {e}") from e
    except OSError as e:
        raise PromptsError(f"Error reading {prompts_path}: {e}") from e

    if raw_data is None or not isinstance(raw_data, dict):
        raise PromptsError(f"Empty or invalid prompts file: {prompts_path}")

    # Handle nested 'prompts:' key (used in bundled default)
    if "prompts" in raw_data and isinstance(raw_data["prompts"], dict):
        raw_data = raw_data["prompts"]

    if "instructions" not in raw_data or not raw_data["instructions"]:
        raise PromptsError(f"Missing 'instructions' in {prompts_path}")

    try:
        return PromptsConfig.model_validate(raw_data)
    except Exception as e:
        raise PromptsError(f"Invalid prompts configuration: {e}") from e


def render_template(
    config: PromptsConfig, template_name: str, **kwargs: Any
) -> str | None:
    """Render a prompt template with variable substitution.

    Args:
        config: PromptsConfig with templates
        template_name: Name of the template to render
        **kwargs: Variables to substitute in the template

    Returns:
        Rendered template string, or None if template not found.
    """
    template = config.templates.get(template_name)
    if template is None:
        return None

    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Missing template variable: {e}")
        return None


def get_tool_description(
    config: PromptsConfig, tool_name: str, default: str = ""
) -> str:
    """Get tool description from prompts config with fallback to docstring.

    Args:
        config: PromptsConfig with tool prompts
        tool_name: Name of the tool
        default: Default description if not in config (typically from docstring)

    Returns:
        Tool description string.
    """
    tool_prompt = config.tools.get(tool_name)
    if tool_prompt and tool_prompt.description:
        return tool_prompt.description
    return default


def get_tool_examples(config: PromptsConfig, tool_name: str) -> list[str]:
    """Get usage examples for a tool.

    Args:
        config: PromptsConfig with tool prompts
        tool_name: Name of the tool

    Returns:
        List of example strings.
    """
    tool_prompt = config.tools.get(tool_name)
    if tool_prompt:
        return tool_prompt.examples
    return []


def get_pack_instructions(config: PromptsConfig, pack: str) -> str | None:
    """Get instructions for a pack from prompts config.

    Args:
        config: PromptsConfig with pack instructions
        pack: Name of the pack (e.g., "excel", "github")

    Returns:
        Pack instructions string, or None if not configured.
    """
    return config.packs.get(pack)


# Global prompts instance
_prompts: PromptsConfig | None = None


def get_prompts(
    prompts_path: Path | str | None = None,
    inline_prompts: dict[str, Any] | None = None,
    reload: bool = False,
) -> PromptsConfig:
    """Get or load the global prompts configuration.

    Prompts are loaded with the following priority:
    1. Inline prompts (if provided)
    2. prompts_file (from config or explicit path)

    Args:
        prompts_path: Path to prompts file (only used on first load)
        inline_prompts: Inline prompts dict from config (overrides file)
        reload: Force reload configuration

    Returns:
        PromptsConfig instance

    Raises:
        PromptsError: If prompts cannot be loaded.
    """
    global _prompts

    if _prompts is None or reload:
        if inline_prompts is not None:
            # Use inline prompts from config
            if (
                "instructions" not in inline_prompts
                or not inline_prompts["instructions"]
            ):
                raise PromptsError("Missing 'instructions' in inline prompts")
            try:
                _prompts = PromptsConfig.model_validate(inline_prompts)
                logger.debug("Using inline prompts from config")
            except Exception as e:
                raise PromptsError(f"Invalid inline prompts: {e}") from e
        else:
            _prompts = load_prompts(prompts_path)

    return _prompts
