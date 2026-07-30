"""Immutable launcher domain values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from ot.logging.redact import redact_secrets

if TYPE_CHECKING:
    from ot.config.routing import (
        Harness,
        PermissionMode,
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
    """One unambiguous launcher model."""

    id: str
    label: str | None = None
    claude_context: Literal["standard", "1m"] | None = None
    auto_compact_window: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    """Resolved exact proxy route or direct profile and model."""

    kind: Literal["route", "profile"]
    name: str
    harness: Harness
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
    """Validated process-replacement invocation."""

    target: ResolvedTarget
    executable: str
    argv: tuple[str, ...]
    environment: EnvironmentDelta
    working_directory: str | None

    def redacted(self) -> dict[str, object]:
        """Return a bounded display-safe invocation."""
        return {
            "target": {"kind": self.target.kind, "name": self.target.name},
            "harness": self.target.harness,
            "model": self.target.model.id,
            "permission": self.target.permission,
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

__all__ = [
    "CLAUDE_PROXY_WARNING",
    "EnvironmentDelta",
    "LaunchInvocation",
    "ResolvedModel",
    "ResolvedTarget",
]
