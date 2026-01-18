"""Tool decorators for enhanced metadata.

The @tool decorator attaches metadata to tool functions for better
LLM comprehension. Plain functions work without decorators.

Example:
    @tool(
        description="Search the web using Brave Search",
        examples=["search(query='Python news')"],
        tags=["search", "web"],
    )
    def brave_search(query: str, count: int = 10) -> str:
        '''Search the web.'''
        ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ToolMetadata:
    """Metadata attached to tool functions by the @tool decorator."""

    description: str | None = None
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    deprecated: bool = False
    deprecated_message: str | None = None


# Attribute name used to store metadata on decorated functions
TOOL_METADATA_ATTR = "_tool_metadata"


def tool(
    description: str | None = None,
    examples: list[str] | None = None,
    tags: list[str] | None = None,
    enabled: bool = True,
    deprecated: bool = False,
    deprecated_message: str | None = None,
) -> Callable[[F], F]:
    """Decorator to add metadata to a tool function.

    Attaches a ToolMetadata instance to the function for the registry
    to extract and use for enhanced descriptions.

    Args:
        description: Override the docstring description
        examples: List of usage examples
        tags: Categorization tags
        enabled: Whether the tool is enabled (default True)
        deprecated: Mark as deprecated
        deprecated_message: Message shown when deprecated

    Returns:
        Decorator function

    Example:
        @tool(
            description="Search the web using Brave Search API",
            examples=[
                'brave_search(query="Python news", count=5)',
                'brave_search(query="weather today")',
            ],
            tags=["search", "web"],
        )
        def brave_search(query: str, count: int = 10) -> str:
            '''Search the web.'''
            ...
    """

    def decorator(func: F) -> F:
        metadata = ToolMetadata(
            description=description,
            examples=examples or [],
            tags=tags or [],
            enabled=enabled,
            deprecated=deprecated,
            deprecated_message=deprecated_message,
        )
        setattr(func, TOOL_METADATA_ATTR, metadata)
        return func

    return decorator


def get_tool_metadata(func: Callable[..., Any]) -> ToolMetadata | None:
    """Extract ToolMetadata from a function if present.

    Args:
        func: Function to check for metadata

    Returns:
        ToolMetadata if decorated with @tool, None otherwise
    """
    return getattr(func, TOOL_METADATA_ATTR, None)


def has_tool_metadata(func: Callable[..., Any]) -> bool:
    """Check if a function has @tool decorator metadata.

    Args:
        func: Function to check

    Returns:
        True if function has ToolMetadata
    """
    return hasattr(func, TOOL_METADATA_ATTR)
