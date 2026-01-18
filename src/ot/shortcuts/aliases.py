"""Alias resolution for OneTool shortcuts.

Resolves short alias names to their full namespaced function names.
E.g., ws(query="test") -> brave.web_search(query="test")
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ot.config import OneToolConfig


def resolve_alias(code: str, config: OneToolConfig) -> str:
    """Resolve aliases in code to their full function names.

    Replaces alias function calls with their target:
    - ws(query="test") -> brave.web_search(query="test")
    - c7(query="react") -> context7.search(query="react")

    Args:
        code: Python code potentially containing alias calls
        config: Configuration with alias mappings

    Returns:
        Code with aliases resolved to full names
    """
    if not config.alias:
        return code

    result = code

    # Sort aliases by length (longest first) to avoid partial matches
    # e.g., "wsb" should be matched before "ws"
    sorted_aliases = sorted(config.alias.keys(), key=len, reverse=True)

    for alias_name in sorted_aliases:
        target = config.alias[alias_name]

        # Match alias followed by ( but not preceded by . or alphanumeric
        # This prevents matching "foo.ws(" or "aws("
        pattern = rf"(?<![.\w]){re.escape(alias_name)}\("

        if re.search(pattern, result):
            result = re.sub(pattern, f"{target}(", result)

    return result


def validate_aliases(config: OneToolConfig) -> list[str]:
    """Validate alias configuration for circular references.

    Args:
        config: Configuration with alias mappings

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []

    # Check for circular aliases
    for alias_name, target in config.alias.items():
        # Extract just the function name from target (before any dot)
        target_base = target.split(".")[0] if "." in target else target

        # Check if target points to another alias
        if target_base in config.alias:
            # Follow the chain to detect cycles
            visited = {alias_name}
            current = target_base

            while current in config.alias:
                if current in visited:
                    errors.append(
                        f"Circular alias detected: '{alias_name}' -> '{target}' "
                        f"creates a cycle through '{current}'"
                    )
                    break
                visited.add(current)
                next_target = config.alias[current]
                current = (
                    next_target.split(".")[0] if "." in next_target else next_target
                )

    return errors
