"""Immutable provider-neutral generation domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ot.config.routing import (
        GenerationInterface,
        ModelModality,
        ModelSource,
        ReasoningEffort,
        StructuredOutputMode,
    )


@dataclass(frozen=True, slots=True)
class ResolvedGeneration:
    """One fully resolved and capability-checked generation route."""

    backend: str
    interface: GenerationInterface
    shortcut: str
    model_id: str
    request_model_id: str
    source: ModelSource
    effort: ReasoningEffort | None
    timeout: float
    max_output_tokens: int | None
    base_url: str
    secret_name: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Narrow request surface accepted by the shared adapters."""

    prompt: str
    system: str | None = None
    images: tuple[bytes, ...] = ()
    structured_output: StructuredOutputMode | None = None
    json_schema: dict[str, Any] | None = None

    @property
    def modalities(self) -> frozenset[ModelModality]:
        """Return the input capabilities required by this request."""
        return frozenset({"text", "image"} if self.images else {"text"})


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
