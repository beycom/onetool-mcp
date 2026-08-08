"""Shared typed backend-aware generation."""

from ot.generation.client import generate
from ot.generation.domain import (
    GenerationError,
    GenerationRequest,
    GenerationResult,
    GenerationUsage,
    ResolvedGeneration,
)
from ot.generation.resolver import resolve_generation

__all__ = [
    "GenerationError",
    "GenerationRequest",
    "GenerationResult",
    "GenerationUsage",
    "ResolvedGeneration",
    "generate",
    "resolve_generation",
]
