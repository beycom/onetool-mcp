"""Executable registry for the canonical 35-outcome acceptance matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

pytestmark = [pytest.mark.unit, pytest.mark.tools]

ROOT = Path(__file__).parents[4]
MATRIX = ARCH_V2_FIXTURES / "acceptance-matrix.json"


def test_canonical_35_outcome_acceptance_matrix() -> None:
    """Every outcome maps to a named executable test, never a manual placeholder."""
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    outcomes = payload["outcomes"]
    assert payload["schema_version"] == 1
    assert len(outcomes) == 35
    assert len({item["id"] for item in outcomes}) == 35
    assert len({item["test"] for item in outcomes}) == 35
    for outcome in outcomes:
        path_value, test_name = outcome["test"].split("::", maxsplit=1)
        path = ROOT / path_value
        assert path.is_file(), outcome
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            assert f"def {test_name}(" in source, outcome
        else:
            assert test_name in source, outcome
        assert not any(token in outcome["test"].lower() for token in ("manual", "skip", "xfail"))
