"""Deterministic shared generation selection and capability validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ot.config.routing import (
    CLIProxyGenerationConfig,
    OpenAICompatibleGenerationConfig,
    ReasoningEffort,
    StructuredOutputMode,
)
from ot.generation.domain import GenerationError, ResolvedGeneration

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ot.config.models import OneToolConfig
    from ot.config.routing import GenerationSelection

_Complete = CLIProxyGenerationConfig | OpenAICompatibleGenerationConfig


def _complete_backend(
    selections: Iterable[GenerationSelection | None],
) -> _Complete | None:
    for selection in selections:
        if isinstance(
            selection,
            (CLIProxyGenerationConfig, OpenAICompatibleGenerationConfig),
        ):
            return selection
    return None


def _first_value(
    name: str,
    selections: Iterable[GenerationSelection | None],
) -> Any:
    for selection in selections:
        if selection is None:
            continue
        value = getattr(selection, name)
        if value is not None:
            return value
    return None


def resolve_generation(
    *,
    config: OneToolConfig,
    pack: GenerationSelection | None = None,
    operation: GenerationSelection | None = None,
    model: str | None = None,
    effort: ReasoningEffort | None = None,
    required_modalities: frozenset[str] = frozenset({"text"}),
    structured_output: StructuredOutputMode | None = None,
) -> ResolvedGeneration:
    """Resolve call > operation > pack > root with an atomic backend switch."""
    layers = (operation, pack, config.llm)
    backend = _complete_backend(layers)
    if backend is None:
        raise GenerationError(
            "No generation route is configured; configure top-level llm or a "
            "complete tool generation backend"
        )

    selected_model = model if model is not None else _first_value("model", layers)
    if not isinstance(selected_model, str) or not selected_model:
        raise GenerationError("A generation model is required")

    matches = [
        entry
        for entry in config.models.values()
        if selected_model in {entry.shortcut, entry.id, entry.proxy_alias}
    ]
    if len(matches) != 1:
        detail = "unknown" if not matches else "ambiguous"
        raise GenerationError(f"Generation model {selected_model!r} is {detail}")
    entry = matches[0]

    interface = backend.interface
    if interface not in entry.interfaces:
        supported = ", ".join(sorted(entry.interfaces)) or "none"
        raise GenerationError(
            f"Model {entry.shortcut!r} does not support interface {interface!r}; "
            f"supported: {supported}"
        )
    if (
        backend.backend == "cliproxy"
        and entry.source == "codex_subscription"
        and interface != "responses"
    ):
        raise GenerationError(
            "Codex subscription generation through CLIProxyAPI requires "
            "interface 'responses'"
        )

    missing_modalities = set(required_modalities) - set(entry.modalities)
    if missing_modalities:
        raise GenerationError(
            f"Model {entry.shortcut!r} lacks required modalities: "
            f"{', '.join(sorted(missing_modalities))}"
        )
    if structured_output is not None:
        supported_outputs = entry.structured_outputs.get(interface, frozenset())
        if structured_output not in supported_outputs:
            raise GenerationError(
                f"Model {entry.shortcut!r} does not support "
                f"{structured_output!r} on {interface!r}"
            )

    selected_effort = effort or _first_value("effort", layers) or entry.default_effort
    if selected_effort is not None and selected_effort not in entry.efforts:
        supported_efforts = ", ".join(sorted(entry.efforts)) or "none"
        raise GenerationError(
            f"Model {entry.shortcut!r} does not support effort "
            f"{selected_effort!r}; supported: {supported_efforts}"
        )

    timeout = _first_value("timeout", layers)
    output_limit = _first_value("max_output_tokens", layers)
    if backend.backend == "cliproxy":
        request_model_id = entry.proxy_alias or entry.id
        if config.code is None or config.code.proxy is None:
            raise GenerationError(
                "llm.backend 'cliproxy' requires the external code.proxy "
                "inference connection"
            )
        base_url = config.code.proxy.base_url
        secret_name = config.code.proxy.secret_name
    else:
        request_model_id = entry.id
        base_url = backend.base_url
        secret_name = backend.secret_name

    return ResolvedGeneration(
        backend=backend.backend,
        interface=interface,
        shortcut=entry.shortcut,
        model_id=entry.id,
        request_model_id=request_model_id,
        source=entry.source,
        effort=selected_effort,
        timeout=timeout if isinstance(timeout, int | float) else 30.0,
        max_output_tokens=output_limit if isinstance(output_limit, int) else None,
        base_url=base_url,
        secret_name=secret_name,
    )


__all__ = ["resolve_generation"]
