"""Tests for live launcher model matching and explicit context parsing."""

from __future__ import annotations

import pytest

from onetool.code.selection import (
    ModelResolutionError,
    parse_context,
    resolve_model_query,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]

MODELS = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "z-ai/glm-5.2",
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("gpt-5.6-sol", "gpt-5.6-sol"),
        ("GPT-5.6-SOL", "gpt-5.6-sol"),
        ("sol", "gpt-5.6-sol"),
        ("terra", "gpt-5.6-terra"),
        ("glm", "z-ai/glm-5.2"),
    ],
)
def test_model_query_resolves_exact_and_unique_partial_matches(
    query: str,
    expected: str,
) -> None:
    assert resolve_model_query(query=query, models=MODELS) == expected


def test_model_query_rejects_ambiguous_and_missing_matches() -> None:
    with pytest.raises(ModelResolutionError, match="Ambiguous") as ambiguous:
        resolve_model_query(query="5.6", models=MODELS)
    assert "gpt-5.6-sol" in str(ambiguous.value)
    assert "gpt-5.6-terra" in str(ambiguous.value)

    with pytest.raises(ModelResolutionError, match="No CLIProxyAPI model"):
        resolve_model_query(query="missing", models=MODELS)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("auto", None),
        ("200k", 200_000),
        ("1M", 1_000_000),
        ("372000", 372_000),
    ],
)
def test_context_parser_accepts_documented_values(
    value: str,
    expected: int | None,
) -> None:
    assert parse_context(value) == expected


@pytest.mark.parametrize("value", ("", "0", "-1", "200kb", "auto1"))
def test_context_parser_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="CONTEXT"):
        parse_context(value)
