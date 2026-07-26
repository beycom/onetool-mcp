"""Immutable launcher domain values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from ot.logging.redact import redact_secrets

if TYPE_CHECKING:
    from ot.config.routing import (
        Harness,
        ModelSource,
        PermissionMode,
        Transport,
    )

_MAX_DISPLAY_ARGV = 128
_MAX_DISPLAY_ARG_LENGTH = 512


def _redacted_argv(argv: tuple[str, ...]) -> list[str]:
    """Return bounded, shape-redacted arguments for display only."""
    displayed = []
    for argument in argv[:_MAX_DISPLAY_ARGV]:
        redacted = redact_secrets(argument)
        if len(redacted) > _MAX_DISPLAY_ARG_LENGTH:
            redacted = f"{redacted[:_MAX_DISPLAY_ARG_LENGTH]}…"
        displayed.append(redacted)
    if len(argv) > _MAX_DISPLAY_ARGV:
        displayed.append(f"… {len(argv) - _MAX_DISPLAY_ARGV} argument(s) omitted")
    return displayed


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """One unambiguous shared-registry model."""

    shortcut: str
    id: str
    label: str
    source: ModelSource
    proxy_alias: str | None
    context_window: int
    modalities: frozenset[str]
    harnesses: frozenset[str]

    @property
    def proxy_identity(self) -> str:
        """Return the configured discovery identity for a proxy route."""
        return self.proxy_alias or self.id


@dataclass(frozen=True, slots=True)
class ResolvedRoute:
    """Resolved route and model with no provider fallback."""

    name: str
    harness: Harness
    source: ModelSource
    transport: Transport
    model: ResolvedModel
    permission: PermissionMode
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class EnvironmentDelta:
    """A complete, immutable description of child environment changes."""

    remove: frozenset[str]
    set_values: Mapping[str, str]

    @classmethod
    def create(
        cls,
        *,
        remove: set[str] | frozenset[str],
        set_values: dict[str, str],
    ) -> EnvironmentDelta:
        """Create a read-only environment delta."""
        return cls(
            remove=frozenset(remove),
            set_values=MappingProxyType(dict(set_values)),
        )

    def apply(self, parent: Mapping[str, str]) -> dict[str, str]:
        """Apply this delta to a parent environment copy."""
        child = {key: value for key, value in parent.items() if key not in self.remove}
        child.update(self.set_values)
        return child

    def redacted(self) -> dict[str, object]:
        """Return display-safe delta metadata without any values."""
        return {
            "remove": sorted(self.remove),
            "set": sorted(self.set_values),
        }


@dataclass(frozen=True, slots=True)
class LaunchInvocation:
    """Validated child process invocation."""

    route: ResolvedRoute
    executable: str
    argv: tuple[str, ...]
    environment: EnvironmentDelta
    working_directory: str | None

    def redacted(self) -> dict[str, object]:
        """Return a bounded display-safe invocation."""
        return {
            "route": self.route.name,
            "harness": self.route.harness,
            "model": self.route.model.id,
            "source": self.route.source,
            "transport": self.route.transport,
            "permission": self.route.permission,
            "argv": _redacted_argv(self.argv),
            "environment": self.environment.redacted(),
            "working_directory": self.working_directory,
        }


CLAUDE_PROXY_WARNING = (
    "Proxying a Claude consumer subscription through CLIProxyAPI is not an "
    "approved Anthropic subscription path and may breach Anthropic's terms, "
    "result in account restrictions, or change billing treatment. Use it at "
    "your own risk."
)

RESPONSIBILITY_NOTICE = (
    "OneTool does not guarantee provider compatibility, terms compliance, model "
    "availability, subscription classification, included usage, rate limits, or "
    "billing treatment. The user is responsible for the selected configuration; "
    "CLIProxyAPI owns proxy authentication and provider routing."
)

__all__ = [
    "CLAUDE_PROXY_WARNING",
    "RESPONSIBILITY_NOTICE",
    "EnvironmentDelta",
    "LaunchInvocation",
    "ResolvedModel",
    "ResolvedRoute",
]
