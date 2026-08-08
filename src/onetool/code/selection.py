"""Live CLIProxyAPI model matching and explicit context parsing."""

from __future__ import annotations

import re
from collections.abc import Sequence

_CONTEXT_ALIASES = {
    "200k": 200_000,
    "1m": 1_000_000,
}
_TOKEN_BOUNDARY = re.compile(r"[/_.-]+")


class ModelResolutionError(ValueError):
    """A deterministic live-inventory model resolution failure."""


def resolve_model_query(*, query: str, models: Sequence[str]) -> str:
    """Resolve an exact or unique case-insensitive partial model query."""
    if not query:
        raise ModelResolutionError("MODEL query must not be empty")
    if query in models:
        return query

    folded = query.casefold()
    casefold_exact = [model for model in models if model.casefold() == folded]
    if len(casefold_exact) == 1:
        return casefold_exact[0]
    if len(casefold_exact) > 1:
        _raise_ambiguous(query=query, matches=casefold_exact)

    matches = [
        model
        for model in models
        if _is_partial_match(query=folded, model=model.casefold())
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        _raise_ambiguous(query=query, matches=matches)
    raise ModelResolutionError(f"No CLIProxyAPI model matches {query!r}")


def _is_partial_match(*, query: str, model: str) -> bool:
    """Return whether a query is a token, suffix, or substring match."""
    return (
        query in _TOKEN_BOUNDARY.split(model) or model.endswith(query) or query in model
    )


def _raise_ambiguous(*, query: str, matches: Sequence[str]) -> None:
    candidates = ", ".join(sorted(matches, key=str.casefold))
    raise ModelResolutionError(
        f"Ambiguous CLIProxyAPI model query {query!r}; candidates: {candidates}"
    )


def parse_context(value: str) -> int | None:
    """Parse an explicit context label into decimal tokens, or auto as None."""
    normalized = value.strip().casefold()
    if normalized == "auto":
        return None
    if normalized in _CONTEXT_ALIASES:
        return _CONTEXT_ALIASES[normalized]
    if normalized.isdecimal():
        tokens = int(normalized)
        if tokens > 0:
            return tokens
    raise ValueError("CONTEXT must be auto, 200k, 1m, or a positive integer")


__all__ = ["ModelResolutionError", "parse_context", "resolve_model_query"]
