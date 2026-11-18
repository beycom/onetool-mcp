"""Bounded local includes and source provenance. No runtime or transport imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from onetool.config import ConfigError, read_document


@dataclass(frozen=True)
class Composition:
    document: dict[str, Any]
    sources: tuple[Path, ...]
    origins: dict[tuple[str, ...], Path]
    lines: dict[Path, dict[tuple[str, ...], int]]

    def origin(self, location: tuple[str, ...]) -> Path:
        for length in range(len(location), -1, -1):
            if location[:length] in self.origins:
                return self.origins[location[:length]]
        return self.sources[-1]

    def location(self, location: tuple[str, ...]) -> str:
        if len(location) > 2 and location[0] == "servers" and location[2] in {"stdio", "http"}:
            location = (*location[:2], *location[3:])
        source = self.origin(location)
        lines = self.lines[source]
        for length in range(len(location), -1, -1):
            if location[:length] in lines:
                return f"{source}:{lines[location[:length]]}"
        return f"{source}:1"


def compose(path: Path) -> Composition:
    sources: list[Path] = []
    lines: dict[Path, dict[tuple[str, ...], int]] = {}
    total = 0
    reads = 0

    def visit(
        current: Path, stack: tuple[Path, ...]
    ) -> tuple[dict[str, Any], dict[tuple[str, ...], Path]]:
        nonlocal total, reads
        canonical = current.resolve()
        if canonical in stack:
            raise ConfigError(f"{current}:1 include: cycle")
        if len(stack) >= 8:
            raise ConfigError(f"{current}:1 include: depth exceeds 8")
        reads += 1
        if reads > 32:
            raise ConfigError(f"{current}:1 include: file count exceeds 32")
        metadata: dict[str, Any] = {}
        data = read_document(current, metadata=metadata)
        total += metadata["size"]
        if total > 1048576:
            raise ConfigError(f"{current}:1 include: combined size exceeds 1 MiB")
        lines[current] = metadata["lines"]
        if (not stack or "version" in data) and (
            type(data.get("version")) is not int or data["version"] != 4
        ):
            line = lines[current].get(("version",), 1)
            raise ConfigError(f"{current}:{line} version: must be integer 4")
        includes = data.pop("include", [])
        if not isinstance(includes, list) or any(
            not isinstance(item, str)
            or not item
            or "${" in item
            or "://" in item
            or any(ord(char) < 32 for char in item)
            or any(char in item for char in "*?[]")
            for item in includes
        ):
            line = lines[current].get(("include",), 1)
            raise ConfigError(f"{current}:{line} include: expected literal local path list")
        merged: dict[str, Any] = {}
        origins: dict[tuple[str, ...], Path] = {}

        def overlay(document: dict[str, Any], incoming: dict[tuple[str, ...], Path]) -> None:
            for key, value in document.items():
                if isinstance(value, dict) and isinstance(merged.get(key, {}), dict):
                    merged[key] = {**merged.get(key, {}), **value}
                    for prop in value:
                        origins[(key, str(prop))] = incoming.get((key, str(prop)), current)
                else:
                    merged[key] = value
                    for old in [old for old in origins if old and old[0] == key]:
                        del origins[old]
                origins[(key,)] = incoming.get((key,), current)

        for include in includes:
            included = Path(include)
            target = Path(current.parent / included).absolute()
            document, incoming = visit(target, (*stack, canonical))
            overlay(document, incoming)
        overlay(data, {})
        sources.append(current)
        origins[()] = current
        return merged, origins

    document, origins = visit(path.absolute(), ())
    return Composition(document, tuple(sources), origins, lines)
