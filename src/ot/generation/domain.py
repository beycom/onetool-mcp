"""Immutable provider-neutral values for shared generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ot.config.routing import (
        GenerationBackend,
        GenerationInterface,
        ReasoningEffort,
        StructuredOutputMode,
    )


@dataclass(frozen=True, slots=True)
class ResolvedGeneration:
    """One fully resolved direct-model generation request target."""

    backend: GenerationBackend
    interface: GenerationInterface
    model_id: str
    effort: ReasoningEffort | None
    base_url: str
    secret_name: str
    timeout: float
    max_output_tokens: int | None


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Narrow request surface accepted by the generation adapters."""

    prompt: str
    system: str | None = None
    images: tuple[bytes, ...] = ()
    structured_output: StructuredOutputMode | None = None
    json_schema: dict[str, Any] | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationUsage:
    """Normalized token usage returned by a generation interface."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Normalized generation content and safe returned metadata."""

    content: str
    usage: GenerationUsage
    latency_seconds: float
    route: ResolvedGeneration


class GenerationError(RuntimeError):
    """Safe, redacted generation configuration or transport failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


__all__ = [
    "GenerationError",
    "GenerationRequest",
    "GenerationResult",
    "GenerationUsage",
    "ResolvedGeneration",
]
