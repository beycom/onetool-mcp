"""Deterministic shared model and launcher-route resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from onetool.code.domain import (
    CLAUDE_PROXY_WARNING,
    ResolvedModel,
    ResolvedRoute,
)

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import Harness, PermissionMode


def _identity_index(config: OneToolConfig) -> dict[str, str]:
    """Return identity-to-shortcut mappings from validated configuration."""
    identities: dict[str, str] = {}
    for shortcut, model in config.models.items():
        for identity in (shortcut, model.id, model.proxy_alias):
            if identity is not None:
                identities[identity] = shortcut
    return identities


def resolve_model(config: OneToolConfig, selection: str) -> ResolvedModel:
    """Resolve one shortcut, concrete id, or proxy alias without substitution."""
    shortcut = _identity_index(config).get(selection)
    if shortcut is None:
        suggestions = ", ".join(sorted(config.models)) or "none configured"
        raise ValueError(
            f"Unknown model {selection!r}. Configured shortcuts: {suggestions}"
        )
    model = config.models[shortcut]
    return ResolvedModel(
        shortcut=model.shortcut,
        id=model.id,
        label=model.label,
        source=model.source,
        proxy_alias=model.proxy_alias,
        context_window=model.context_window,
        modalities=frozenset(model.modalities),
        harnesses=frozenset(model.harnesses),
    )


def resolve_route(
    *,
    config: OneToolConfig,
    harness: Harness,
    model: str | None,
    route: str | None,
    permission: PermissionMode | None,
) -> ResolvedRoute:
    """Resolve the selected harness route deterministically."""
    code = config.code
    if code is None:
        raise ValueError(
            "Code routing is not configured. Run `onetool code setup` or add "
            "`models` and `code` to onetool.yaml."
        )

    route_name = route
    if route_name is None:
        route_name = (
            code.defaults.claude_route
            if harness == "claude"
            else code.defaults.codex_route
        )
    if route_name is None:
        raise ValueError(
            f"No default {harness} route is configured. Pass --route explicitly."
        )

    selected_route = code.routes.get(route_name)
    if selected_route is None:
        compatible = sorted(
            name
            for name, candidate in code.routes.items()
            if candidate.harness == harness and candidate.enabled
        )
        raise ValueError(
            f"Unknown route {route_name!r}. Compatible routes: "
            f"{', '.join(compatible) or 'none'}"
        )
    if selected_route.harness != harness:
        raise ValueError(
            f"Route {route_name!r} is for {selected_route.harness}, not {harness}"
        )
    if not selected_route.enabled:
        raise ValueError(f"Route {route_name!r} is disabled")

    resolved_model = resolve_model(
        config,
        model if model is not None else selected_route.model,
    )
    if resolved_model.source != selected_route.source:
        raise ValueError(
            f"Model {resolved_model.shortcut!r} uses {resolved_model.source}, "
            f"but route {route_name!r} uses {selected_route.source}"
        )
    if harness not in resolved_model.harnesses:
        raise ValueError(
            f"Model {resolved_model.shortcut!r} is not verified for {harness}"
        )

    warning = None
    if (
        harness == "claude"
        and selected_route.source == "claude_subscription"
        and selected_route.transport == "cliproxy"
    ):
        if not code.claude_subscription_proxy_enabled:
            raise ValueError(
                "Claude subscription proxying is disabled. Set "
                "code.claude_subscription_proxy_enabled: true to select this route."
            )
        warning = CLAUDE_PROXY_WARNING

    return ResolvedRoute(
        name=route_name,
        harness=harness,
        source=selected_route.source,
        transport=selected_route.transport,
        model=resolved_model,
        permission=permission or code.defaults.permission,
        warning=warning,
    )


__all__ = ["resolve_model", "resolve_route"]
