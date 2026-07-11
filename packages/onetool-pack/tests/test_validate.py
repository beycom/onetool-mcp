"""Tests for shared parameter validation helpers."""

from __future__ import annotations

import pytest

from otpack import validate_choice, validate_int_range


@pytest.mark.unit
@pytest.mark.pkg
class TestValidateChoice:
    def test_valid(self):
        assert validate_choice("topic", "news", {"general", "news"}) is None

    def test_invalid_lists_sorted_choices(self):
        err = validate_choice("topic", "sports", {"general", "news"})
        assert err == "Error: Invalid topic 'sports'. Use ['general', 'news']"

    def test_optional_none_passes(self):
        assert validate_choice("time_range", None, {"day"}, optional=True) is None

    def test_required_none_fails(self):
        assert validate_choice("time_range", None, {"day"}) is not None


@pytest.mark.unit
@pytest.mark.pkg
class TestValidateIntRange:
    def test_valid_bounds(self):
        assert validate_int_range("n", 1, 1, 20) is None
        assert validate_int_range("n", 20, 1, 20) is None

    def test_out_of_range(self):
        assert validate_int_range("n", 0, 1, 20) == "Error: n must be between 1 and 20 (got 0)"
        assert validate_int_range("n", 21, 1, 20) is not None

    def test_bool_and_non_int_rejected(self):
        assert validate_int_range("n", True, 1, 20) is not None
        assert validate_int_range("n", "5", 1, 20) is not None  # type: ignore[arg-type]
