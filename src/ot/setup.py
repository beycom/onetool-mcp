"""Read-only pack requirement and readiness diagnostics."""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from ot.catalog import (
    ComposedPackGuidance,
    PackRequirement,
    RequirementKind,
    load_composed_catalog,
)


class ReadinessStatus(StrEnum):
    """Stable readiness classifications rendered by setup help."""

    READY = "ready"
    MISSING_EXTRA = "missing_extra"
    MISSING_LIBRARY = "missing_library"
    MISSING_EXECUTABLE = "missing_executable"
    UNSET_SECRET = "unset_secret"
    MISSING_CONFIG = "missing_config"
    INVALID_CONFIG = "invalid_config"
    INACTIVE_OPTIONAL = "inactive_optional"
    UNCONFIGURED_SERVER = "unconfigured_server"
    DISABLED_SERVER = "disabled_server"
    CONNECTING_SERVER = "connecting_server"
    DISCONNECTED_SERVER = "disconnected_server"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RequirementReadiness(_FrozenModel):
    """One checked requirement with a non-mutating next step."""

    requirement: PackRequirement | None = None
    status: ReadinessStatus
    detail: str
    next_step: str | None = None
    blocking: bool = False


class PackReadinessReport(_FrozenModel):
    """Structured readiness for one cataloged pack."""

    pack: str
    install_extra: str
    available: bool
    ready: bool
    checks: tuple[RequirementReadiness, ...]
    config_errors: tuple[dict[str, str], ...] = ()


def _get_path(config: Mapping[str, Any], path: str) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def requirement_is_active(
    requirement: PackRequirement,
    config: Mapping[str, Any],
) -> bool:
    """Return whether a conditional requirement applies to active config."""

    if requirement.activation is None:
        return True
    actual = _get_path(config, requirement.activation.field)
    expected = requirement.activation.equals
    if expected is True:
        return bool(actual)
    if expected is False:
        return not bool(actual)
    return bool(actual == expected)


def _library_available(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _missing_step(requirement: PackRequirement) -> str:
    if requirement.install_extra:
        suffix = (
            "" if requirement.install_extra.value == "core" else requirement.install_extra
        )
        return f"Install onetool-mcp{suffix}, then reload OneTool."
    if requirement.authoritative_url:
        return (
            f"Follow the publisher's current installation documentation at "
            f"{requirement.authoritative_url}, then reload OneTool."
        )
    if requirement.kind is RequirementKind.SECRET:
        return f"Configure secret {requirement.name}, then reload OneTool."
    if requirement.kind is RequirementKind.SERVER:
        return (
            f"Configure and enable MCP server {requirement.name!r} using its current "
            "authoritative MCP documentation."
        )
    return f"Configure tools field {requirement.name!r}, then reload OneTool."


def evaluate_pack_readiness(
    item: ComposedPackGuidance,
    *,
    secret_is_set: Callable[[str], bool],
    server_states: Mapping[str, Mapping[str, Any]],
    library_available: Callable[[str], bool] = _library_available,
    executable_available: Callable[[str], bool] = lambda name: (
        shutil.which(name) is not None
    ),
) -> PackReadinessReport:
    """Evaluate one composed pack without mutating packages, config, or services."""

    guidance = item.guidance
    runtime = item.runtime
    if runtime is None:
        suffix = "" if guidance.extra.value == "core" else guidance.extra
        check = RequirementReadiness(
            status=ReadinessStatus.MISSING_EXTRA,
            detail=f"Pack {guidance.pack!r} is not installed.",
            next_step=f"Install onetool-mcp{suffix}, then reload OneTool.",
            blocking=True,
        )
        return PackReadinessReport(
            pack=guidance.pack,
            install_extra=guidance.extra.value,
            available=False,
            ready=False,
            checks=(check,),
        )

    checks: list[RequirementReadiness] = []
    for requirement in runtime.requirements:
        active = requirement_is_active(requirement, runtime.active_config)
        if not active:
            checks.append(
                RequirementReadiness(
                    requirement=requirement,
                    status=ReadinessStatus.INACTIVE_OPTIONAL,
                    detail="Requirement is inactive for the current configuration.",
                )
            )
            continue

        status = ReadinessStatus.READY
        detail = "Requirement is satisfied."
        if requirement.kind is RequirementKind.LIB and not library_available(
            requirement.import_name or requirement.name
        ):
            status = ReadinessStatus.MISSING_LIBRARY
            detail = f"Python import {requirement.import_name!r} is unavailable."
        elif requirement.kind is RequirementKind.CLI and not executable_available(
            requirement.executable or requirement.name
        ):
            status = ReadinessStatus.MISSING_EXECUTABLE
            detail = f"Executable {requirement.executable!r} is not on PATH."
        elif requirement.kind is RequirementKind.SECRET and not secret_is_set(
            requirement.name
        ):
            status = ReadinessStatus.UNSET_SECRET
            detail = f"Secret {requirement.name!r} is unset."
        elif requirement.kind is RequirementKind.CONFIG and _get_path(
            runtime.active_config, requirement.name
        ) in (None, "", [], {}):
            status = ReadinessStatus.MISSING_CONFIG
            detail = f"Configuration field {requirement.name!r} is unset."
        elif requirement.kind is RequirementKind.SERVER:
            server = server_states.get(requirement.name)
            if server is None:
                status = ReadinessStatus.UNCONFIGURED_SERVER
                detail = f"Proxy server {requirement.name!r} is not configured."
            elif not server.get("enabled", False):
                status = ReadinessStatus.DISABLED_SERVER
                detail = f"Proxy server {requirement.name!r} is disabled."
            elif server.get("status") == "connecting":
                status = ReadinessStatus.CONNECTING_SERVER
                detail = f"Proxy server {requirement.name!r} is connecting."
            elif not server.get("connected", False):
                status = ReadinessStatus.DISCONNECTED_SERVER
                detail = f"Proxy server {requirement.name!r} is disconnected."

        blocking = status is not ReadinessStatus.READY and not requirement.optional
        checks.append(
            RequirementReadiness(
                requirement=requirement,
                status=status,
                detail=detail,
                next_step=_missing_step(requirement)
                if status is not ReadinessStatus.READY
                else None,
                blocking=blocking,
            )
        )

    for error in runtime.config_errors:
        checks.append(
            RequirementReadiness(
                status=ReadinessStatus.INVALID_CONFIG,
                detail=(
                    f"Invalid config at {error['path'] or '<root>'}: "
                    f"{error['message']}"
                ),
                next_step="Correct the reported tools config field, then reload OneTool.",
                blocking=True,
            )
        )

    if not checks:
        checks.append(
            RequirementReadiness(
                status=ReadinessStatus.READY,
                detail="Pack is installed and declares no external requirements.",
            )
        )
    return PackReadinessReport(
        pack=guidance.pack,
        install_extra=guidance.extra.value,
        available=True,
        ready=not any(check.blocking for check in checks),
        checks=tuple(checks),
        config_errors=runtime.config_errors,
    )


def get_pack_readiness(pack: str) -> PackReadinessReport:
    """Build a live read-only readiness report for one cataloged pack."""

    from ot.config.loader import get_config
    from ot.config.secrets import get_secret
    from ot.proxy import get_proxy_manager

    item = next(
        (entry for entry in load_composed_catalog() if entry.guidance.pack == pack),
        None,
    )
    if item is None:
        raise ValueError(f"Unknown catalog pack {pack!r}")

    config = get_config()
    proxy = get_proxy_manager()
    readiness = proxy.readiness(tuple(config.servers))
    proxy_servers = readiness.get("servers", {})
    server_states = {
        name: {
            "enabled": server.enabled,
            "connected": state.get("status") == "connected",
            "status": state.get("status", "disconnected"),
        }
        for name, server in config.servers.items()
        for state in [proxy_servers.get(name, {})]
    }
    return evaluate_pack_readiness(
        item,
        secret_is_set=lambda name: bool(get_secret(name)),
        server_states=server_states,
    )
