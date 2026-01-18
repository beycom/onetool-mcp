"""Registry models - Pydantic models for tool and argument information."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArgInfo(BaseModel):
    """Information about a function argument."""

    name: str = Field(description="Argument name")
    type: str = Field(default="Any", description="Type annotation")
    default: str | None = Field(default=None, description="Default value if any")
    description: str = Field(
        default="", description="Argument description from docstring"
    )


class ToolInfo(BaseModel):
    """Information about a registered tool function."""

    name: str = Field(description="Function name")
    module: str = Field(description="Module path (e.g., 'tools.gold_prices')")
    signature: str = Field(description="Full function signature")
    description: str = Field(
        default="", description="Function description from docstring"
    )
    args: list[ArgInfo] = Field(default_factory=list, description="Function arguments")
    returns: str = Field(
        default="", description="Return type/description from docstring"
    )
    examples: list[str] = Field(
        default_factory=list, description="Usage examples from @tool decorator"
    )
    tags: list[str] = Field(
        default_factory=list, description="Categorization tags from @tool decorator"
    )
    enabled: bool = Field(default=True, description="Whether the tool is enabled")
    deprecated: bool = Field(
        default=False, description="Whether the tool is deprecated"
    )
    deprecated_message: str | None = Field(
        default=None, description="Deprecation message"
    )
