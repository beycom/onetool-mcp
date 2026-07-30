"""Exact launcher model and target resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from onetool.code.domain import (
    CLAUDE_PROXY_WARNING,
    ResolvedModel,
    ResolvedTarget,
)
from ot.config.routing import CodeModelConfig

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import Harness, ModelSource, PermissionMode

type TargetKind = Literal["route", "profile"]
type ModelCandidate = tuple[TargetKind, str, CodeModelConfig]

_COMPATIBLE_ROUTES: dict[Harness, frozenset[ModelSource]] = {
    "claude": frozenset(
        {"claude_subscription", "codex_subscription", "openrouter"}
    ),
    "codex": frozenset({"codex_subscription", "openrouter"}),
}


def compatible_routes(harness: Harness) -> frozenset[ModelSource]:
    """Return the verified canonical proxy routes for one harness."""
    return _COMPATIBLE_ROUTES[harness]


def compatible_models(
    *,
    config: OneToolConfig,
    harness: Harness,
    route: ModelSource | None = None,
    profile: str | None = None,
) -> tuple[ModelCandidate, ...]:
    """Enumerate models within one exact compatible target scope."""
    code = config.code
    if code is None:
        raise ValueError(
            "Code routing is not configured. Use `onetool init` or add a "
            "`code` section to onetool.yaml."
        )
    if route is not None and profile is not None:
        raise ValueError("--route and --profile are mutually exclusive")
    if profile is not None:
        if harness != "codex":
            raise ValueError("Direct profiles are supported only by Codex")
        profiles = (
            code.direct.codex.profiles if code.direct is not None else {}
        )
        models = profiles.get(profile)
        if models is None:
            configured = ", ".join(sorted(profiles)) or "none"
            raise ValueError(
                f"Profile {profile!r} is not configured. "
                f"Configured profiles: {configured}"
            )
        return tuple(("profile", profile, model) for model in models)

    proxy_routes = code.proxy.routes if code.proxy is not None else {}
    if route is not None:
        if route not in compatible_routes(harness):
            raise ValueError(f"Route {route!r} is not supported by {harness}")
        models = proxy_routes.get(route)
        if models is None:
            configured = ", ".join(sorted(proxy_routes)) or "none"
            raise ValueError(
                f"Route {route!r} is not configured. Configured routes: {configured}"
            )
        return tuple(("route", route, model) for model in models)

    candidates: list[ModelCandidate] = [
        ("route", candidate_route, model)
        for candidate_route, models in proxy_routes.items()
        if candidate_route in compatible_routes(harness)
        for model in models
    ]
    if harness == "codex" and code.direct is not None:
        candidates.extend(
            ("profile", candidate_profile, model)
            for candidate_profile, models in code.direct.codex.profiles.items()
            for model in models
        )
    return tuple(candidates)


def configured_harnesses(config: OneToolConfig) -> tuple[Harness, ...]:
    """Return harnesses that have at least one compatible configured target."""
    harnesses = cast("tuple[Harness, ...]", ("claude", "codex"))
    return tuple(
        harness
        for harness in harnesses
        if compatible_models(config=config, harness=harness)
    )


def _format_candidates(candidates: tuple[ModelCandidate, ...]) -> str:
    """Format exact ids, shortcuts, and targets for actionable errors."""
    values = []
    for kind, target, model in candidates:
        shortcut = f", shortcut={model.shortcut}" if model.shortcut else ""
        values.append(f"{model.id} ({kind}={target}{shortcut})")
    return ", ".join(values) or "none"


def _select_model(
    *,
    selection: str,
    candidates: tuple[ModelCandidate, ...],
) -> ModelCandidate:
    """Resolve one exact model id or shortcut."""
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate[2].id == selection or candidate[2].shortcut == selection
    )
    if not matches:
        raise ValueError(
            f"Unknown model {selection!r}. Compatible configured models: "
            f"{_format_candidates(candidates)}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Model {selection!r} is configured under multiple targets; pass exact "
            f"--route or --profile. Matches: {_format_candidates(matches)}"
        )
    return matches[0]


def resolve_target(
    *,
    config: OneToolConfig,
    harness: Harness,
    model: str | None,
    route: ModelSource | None,
    profile: str | None = None,
    permission: PermissionMode | None,
) -> ResolvedTarget:
    """Resolve one harness, exact target, model, and permission."""
    code = config.code
    if code is None:
        raise ValueError(
            "Code routing is not configured. Use `onetool init` or add a "
            "`code` section to onetool.yaml."
        )
    if route is not None and profile is not None:
        raise ValueError("--route and --profile are mutually exclusive")

    selection = model
    route_scope = route
    profile_scope = profile
    if selection is None:
        if code.default is None:
            candidates = compatible_models(
                config=config,
                harness=harness,
                route=route_scope,
                profile=profile_scope,
            )
            raise ValueError(
                f"No default model is configured for {harness}. Pass a model or "
                f"choose from: {_format_candidates(candidates)}"
            )
        selection = code.default.model
        if route_scope is None and profile_scope is None:
            route_scope = code.default.route
            profile_scope = code.default.profile

    candidates = compatible_models(
        config=config,
        harness=harness,
        route=route_scope,
        profile=profile_scope,
    )
    kind, target_name, selected_model = _select_model(
        selection=selection,
        candidates=candidates,
    )
    warning = (
        CLAUDE_PROXY_WARNING
        if harness == "claude"
        and kind == "route"
        and target_name == "claude_subscription"
        else None
    )
    claude_policy = selected_model.claude
    return ResolvedTarget(
        kind=kind,
        name=target_name,
        harness=harness,
        model=ResolvedModel(
            id=selected_model.id,
            label=selected_model.label,
            claude_context=(
                claude_policy.context if claude_policy is not None else None
            ),
            auto_compact_window=(
                claude_policy.auto_compact_window
                if claude_policy is not None
                else None
            ),
        ),
        permission=permission or code.permission,
        warning=warning,
    )


__all__ = [
    "compatible_models",
    "compatible_routes",
    "configured_harnesses",
    "resolve_target",
]
