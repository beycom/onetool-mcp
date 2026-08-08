"""Immutable values for direct-model harness launches."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

Harness = Literal["claude", "codex"]


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
        """Apply this delta to a copy of the parent environment."""
        child = {key: value for key, value in parent.items() if key not in self.remove}
        child.update(self.set_values)
        return child


@dataclass(frozen=True, slots=True)
class LaunchInvocation:
    """One process-replacement invocation for an official harness."""

    harness: Harness
    model: str
    proxy_origin: str
    argv: tuple[str, ...]
    environment: EnvironmentDelta

    @property
    def executable(self) -> str:
        """Return the official harness executable name resolved through PATH."""
        return self.harness


__all__ = ["EnvironmentDelta", "Harness", "LaunchInvocation"]
