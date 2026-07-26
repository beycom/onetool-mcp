"""Shared typed generation routing."""

from ot.generation.client import generate
from ot.generation.domain import (
    GenerationError,
    GenerationRequest,
    GenerationResult,
    GenerationUsage,
    ResolvedGeneration,
)
from ot.generation.readiness import (
    GenerationReadiness,
    check_generation_readiness,
    get_generation_readiness,
)
from ot.generation.resolver import resolve_generation

__all__ = [
    "GenerationError",
    "GenerationReadiness",
    "GenerationRequest",
    "GenerationResult",
    "GenerationUsage",
    "ResolvedGeneration",
    "check_generation_readiness",
    "generate",
    "get_generation_readiness",
    "resolve_generation",
]
