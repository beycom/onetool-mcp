"""Bounded startup readiness for explicitly configured proxy generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from onetool.code.proxy import ModelDiscovery, ProxyDiscoveryError
from ot.config.routing import (
    CLIProxyGenerationConfig,
    GenerationSelection,
    OpenAICompatibleGenerationConfig,
)
from ot.config.secrets import get_secret
from ot.generation.domain import GenerationError, ResolvedGeneration
from ot.generation.resolver import resolve_generation

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig


class _PackRoutes(BaseModel):
    """Generation fields needed for startup readiness inspection."""

    model_config = ConfigDict(extra="ignore")

    llm: GenerationSelection | None = None


class _KnowledgeRoutes(_PackRoutes):
    """Knowledge pack and operation-scoped generation fields."""

    ask: _PackRoutes | None = None
    rerank: _PackRoutes | None = None
    enrich: _PackRoutes | None = None


class _ConfiguredToolRoutes(BaseModel):
    """Typed view of generation-capable tool configuration."""

    model_config = ConfigDict(extra="ignore")

    ot_llm: _PackRoutes | None = None
    ot_image: _PackRoutes | None = None
    ot_context: _PackRoutes | None = None
    mem: _PackRoutes | None = None
    knowledge: _KnowledgeRoutes | None = None


@dataclass(frozen=True, slots=True)
class GenerationReadiness:
    """Safe startup state for the configured shared generation route."""

    configured: bool
    available: bool
    diagnostic: str


_state = GenerationReadiness(
    configured=False,
    available=False,
    diagnostic="No proxy generation route configured",
)


def _uses_proxy(
    config: OneToolConfig,
    *,
    pack: GenerationSelection | None = None,
    operation: GenerationSelection | None = None,
) -> bool:
    """Return whether the effective atomic backend is CLIProxyAPI."""
    for selection in (operation, pack, config.llm):
        if isinstance(
            selection,
            (CLIProxyGenerationConfig, OpenAICompatibleGenerationConfig),
        ):
            return isinstance(selection, CLIProxyGenerationConfig)
    return False


def _proxy_routes(config: OneToolConfig) -> tuple[ResolvedGeneration, ...]:
    """Resolve every explicitly configured effective proxy route."""
    tools = _ConfiguredToolRoutes.model_validate(config.tools.model_dump())
    layers: list[
        tuple[GenerationSelection | None, GenerationSelection | None]
    ] = []

    if isinstance(config.llm, CLIProxyGenerationConfig):
        layers.append((None, None))

    for pack_config in (
        tools.ot_llm,
        tools.ot_image,
        tools.ot_context,
        tools.mem,
    ):
        if pack_config is not None and pack_config.llm is not None:
            layers.append((pack_config.llm, None))

    knowledge = tools.knowledge
    if knowledge is not None:
        if knowledge.llm is not None:
            layers.append((knowledge.llm, None))
        for operation_config in (
            knowledge.ask,
            knowledge.rerank,
            knowledge.enrich,
        ):
            if operation_config is not None and operation_config.llm is not None:
                layers.append((knowledge.llm, operation_config.llm))

    routes: list[ResolvedGeneration] = []
    for pack, operation in layers:
        if _uses_proxy(config, pack=pack, operation=operation):
            routes.append(
                resolve_generation(
                    config=config,
                    pack=pack,
                    operation=operation,
                )
            )
    return tuple(routes)


def check_generation_readiness(config: OneToolConfig) -> GenerationReadiness:
    """Check only discovery/model presence; never perform billable generation."""
    global _state
    try:
        routes = _proxy_routes(config)
    except (GenerationError, ValueError) as exc:
        _state = GenerationReadiness(
            configured=True,
            available=False,
            diagnostic=f"Invalid proxy generation route: {exc}",
        )
        return _state
    if not routes:
        _state = GenerationReadiness(
            configured=False,
            available=False,
            diagnostic="No proxy generation route configured",
        )
        return _state
    assert config.code is not None
    assert config.code.cliproxy is not None
    secret = get_secret(config.code.cliproxy.secret_name)
    if not secret:
        _state = GenerationReadiness(
            configured=True,
            available=False,
            diagnostic=(
                f"Named inference secret "
                f"{config.code.cliproxy.secret_name!r} is missing"
            ),
        )
        return _state
    identities = tuple(
        dict.fromkeys(
            (
                route.proxy_identity,
                route.model_id,
            )
            if route.proxy_identity != route.model_id
            else (route.model_id,)
            for route in routes
        )
    )
    try:
        discovery = ModelDiscovery(config=config.code.cliproxy, secret=secret)
        for route_identities in identities:
            discovery.validate(*route_identities)
    except ProxyDiscoveryError:
        _state = GenerationReadiness(
            configured=True,
            available=False,
            diagnostic=(
                f"CLIProxyAPI generation is unavailable at "
                f"{config.code.cliproxy.base_url}; check the external service "
                "and configured model"
            ),
        )
        return _state
    _state = GenerationReadiness(
        configured=True,
        available=True,
        diagnostic="CLIProxyAPI generation route is ready",
    )
    return _state


def get_generation_readiness() -> GenerationReadiness:
    """Return the most recent safe readiness state."""
    return _state


__all__ = [
    "GenerationReadiness",
    "check_generation_readiness",
    "get_generation_readiness",
]
