"""Seam 2: a typo'd pack name yields a fuzzy suggestion + ot.packs() pointer (p13)."""

from __future__ import annotations

import pytest

from ot.executor.runner import execute_command


@pytest.mark.unit
@pytest.mark.core
class TestTypoPackSuggestion:
    """A NameError from an undefined pack name is enriched with recovery guidance."""

    async def test_near_miss_pack_suggests_real_pack(self) -> None:
        result = await execute_command("brvae.search(query='test')")
        assert not result.success
        assert result.error_type == "NameError"
        assert "brave" in result.result
        assert "ot.packs()" in result.result

    async def test_unknown_pack_has_pointer_but_no_false_suggestion(self) -> None:
        result = await execute_command("zzzqqqxxx.thing()")
        assert not result.success
        assert "ot.packs()" in result.result
        assert "Did you mean" not in result.result
