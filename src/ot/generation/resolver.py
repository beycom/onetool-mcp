"""Direct model and connection selection for shared generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ot.generation.domain import GenerationError, ResolvedGeneration

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import ReasoningEffort


def resolve_generation(
    *,
    config: OneToolConfig,
    pack_model: str | None = None,
    pack_effort: ReasoningEffort | None = None,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
) -> ResolvedGeneration:
    """Resolve model and effort in call, pack, then root order."""
    connection = config.llm

    selected_model = (
        model
        if model is not None
        else pack_model
        if pack_model is not None
        else connection.model
    )
    if not selected_model:
        raise GenerationError("A direct generation model ID is required")

    return ResolvedGeneration(
        backend=connection.backend,
        interface=connection.interface,
        model_id=selected_model,
        effort=effort or pack_effort or connection.effort,
        base_url=connection.base_url,
        secret_name=connection.secret_name,
        timeout=connection.timeout,
        max_output_tokens=connection.max_tokens,
    )


__all__ = ["resolve_generation"]
