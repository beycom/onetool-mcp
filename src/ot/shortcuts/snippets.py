"""Snippet parsing and expansion for OneTool shortcuts.

Handles snippet syntax parsing and Jinja2 template expansion:
- Single-line: $wsq q1=AI q2=ML p=Compare
- Multi-line: $wsq\nq1: AI\nq2: ML\np: Compare
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from ot.config import OneToolConfig, SnippetDef

try:
    from jinja2 import Environment, StrictUndefined, TemplateSyntaxError
except ImportError as e:
    raise ImportError(
        "jinja2 is required for snippets. Install with: pip install jinja2"
    ) from e


@dataclass
class ParsedSnippet:
    """Result of parsing a snippet invocation."""

    name: str
    params: dict[str, str]
    raw: str


def is_snippet(code: str) -> bool:
    """Check if code is a snippet invocation (starts with $).

    Args:
        code: Code to check

    Returns:
        True if code starts with $ (snippet syntax)
    """
    stripped = code.strip()
    # Must start with $ but not be $variable inside other code
    return stripped.startswith("$") and not stripped.startswith("${")


def parse_snippet(code: str) -> ParsedSnippet:
    """Parse a snippet invocation into name and parameters.

    Supports two syntaxes:
    - Single-line: $name key=value key2=value2
    - Multi-line: $name\\nkey: value\\nkey2: value2

    Args:
        code: Snippet invocation string

    Returns:
        ParsedSnippet with name and extracted parameters

    Raises:
        ValueError: If snippet syntax is invalid
    """
    stripped = code.strip()

    if not stripped.startswith("$"):
        raise ValueError(f"Snippet must start with $: {stripped[:50]}")

    # Remove $ prefix
    content = stripped[1:]

    # Check for multi-line (has newline after snippet name)
    lines = content.split("\n")
    first_line = lines[0].strip()

    # Extract snippet name (first word)
    name_match = re.match(r"^(\w+)", first_line)
    if not name_match:
        raise ValueError(f"Invalid snippet name: {first_line[:50]}")

    name = name_match.group(1)

    # Check if multi-line or single-line
    if len(lines) > 1:
        return _parse_multiline_snippet(name, lines[1:], stripped)
    else:
        return _parse_singleline_snippet(name, first_line[len(name) :], stripped)


def _strip_quotes(value: str) -> str:
    """Strip matching outer quotes from a value.

    Handles both single and double quotes. Only strips if quotes are balanced.

    Args:
        value: String that may have outer quotes

    Returns:
        String with outer quotes removed if present and balanced
    """
    if len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    return value


def _parse_singleline_snippet(name: str, params_str: str, raw: str) -> ParsedSnippet:
    """Parse single-line snippet parameters: key=value key2="value with spaces".

    Values extend until the next key= or end of string.
    Outer quotes are stripped from values (key="value" becomes key=value).
    Escaped equals (\\=) are preserved in values.
    """
    params: dict[str, str] = {}
    params_str = params_str.strip()

    if not params_str:
        return ParsedSnippet(name=name, params=params, raw=raw)

    # Replace escaped equals with placeholder
    placeholder = "\x00EQUALS\x00"
    params_str = params_str.replace("\\=", placeholder)

    # Find all key=value pairs
    # Pattern: word followed by = and then value until next word= or end
    pattern = r"(\w+)=((?:[^=]|$)*?)(?=\s+\w+=|$)"
    matches = re.findall(pattern, params_str)

    for key, value in matches:
        # Restore escaped equals and strip whitespace
        value = value.replace(placeholder, "=").strip()
        # Strip outer quotes from value (e.g., packages="react" -> packages=react)
        value = _strip_quotes(value)
        params[key] = value

    return ParsedSnippet(name=name, params=params, raw=raw)


def _parse_multiline_snippet(name: str, lines: list[str], raw: str) -> ParsedSnippet:
    """Parse multi-line snippet parameters: key: value.

    Blank line terminates the snippet parameters.
    Only the first colon is the separator (colons in values are preserved).
    Outer quotes are stripped from values for consistency with single-line format.
    """
    params: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()

        # Blank line terminates
        if not stripped:
            break

        # Parse key: value (only first colon is separator)
        colon_idx = stripped.find(":")
        if colon_idx == -1:
            logger.warning(f"Invalid snippet line (no colon): {stripped}")
            continue

        key = stripped[:colon_idx].strip()
        value = stripped[colon_idx + 1 :].strip()

        if not key:
            logger.warning(f"Empty key in snippet line: {stripped}")
            continue

        # Strip outer quotes from value for consistency
        value = _strip_quotes(value)
        params[key] = value

    return ParsedSnippet(name=name, params=params, raw=raw)


def expand_snippet(
    parsed: ParsedSnippet,
    config: OneToolConfig,
) -> str:
    """Expand a parsed snippet using Jinja2 templating.

    Args:
        parsed: Parsed snippet with name and parameters
        config: Configuration with snippet definitions

    Returns:
        Expanded Python code from the snippet template

    Raises:
        ValueError: If snippet not found, missing required params, or Jinja2 error
    """
    if parsed.name not in config.snippets:
        available = ", ".join(sorted(config.snippets.keys())) or "(none)"
        raise ValueError(f"Unknown snippet '{parsed.name}'. Available: {available}")

    snippet_def: SnippetDef = config.snippets[parsed.name]

    # Build context with defaults and provided values
    context: dict[str, Any] = {}

    # Apply defaults first
    for param_name, param_def in snippet_def.params.items():
        if param_def.default is not None:
            context[param_name] = param_def.default

    # Apply provided values
    for key, value in parsed.params.items():
        if key not in snippet_def.params:
            logger.warning(
                f"Unknown parameter '{key}' for snippet '{parsed.name}' (ignored)"
            )
        context[key] = value

    # Check required parameters
    for param_name, param_def in snippet_def.params.items():
        if param_def.required and param_name not in context:
            raise ValueError(
                f"Snippet '{parsed.name}' requires parameter '{param_name}'"
            )

    # Render template with Jinja2
    try:
        env = Environment(undefined=StrictUndefined)
        template = env.from_string(snippet_def.body)
        return template.render(**context)
    except TemplateSyntaxError as e:
        raise ValueError(f"Jinja2 syntax error in snippet '{parsed.name}': {e}") from e
    except Exception as e:
        # StrictUndefined raises UndefinedError for missing variables
        if "undefined" in str(e).lower():
            raise ValueError(
                f"Undefined variable in snippet '{parsed.name}': {e}"
            ) from e
        raise ValueError(f"Error expanding snippet '{parsed.name}': {e}") from e


def validate_snippets(config: OneToolConfig) -> list[str]:
    """Validate snippet definitions for Jinja2 syntax errors.

    Args:
        config: Configuration with snippet definitions

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []
    env = Environment(undefined=StrictUndefined)

    for name, snippet_def in config.snippets.items():
        try:
            env.from_string(snippet_def.body)
        except TemplateSyntaxError as e:
            errors.append(f"Snippet '{name}' has invalid Jinja2 syntax: {e}")

    return errors
