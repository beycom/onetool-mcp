"""Integration tests for the ot_caveman tool pack.

These tests make live LLM API calls. They require OPENAI_API_KEY,
llm.base_url, and llm.model to be configured.

Run with: uv run pytest -m "integration and tools" tests/integration/tools/test_ot_caveman.py
"""

from __future__ import annotations

import pytest


def _skip_if_not_configured():
    """Skip if ot_caveman is not configured (no API key / base_url / model)."""
    try:
        from otpack import get_secret

        api_key = get_secret("OPENAI_API_KEY") or get_secret("OT_LLM_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not configured")

        from ot.config import get_llm_config

        llm = get_llm_config()
        if not llm.base_url or not llm.model:
            pytest.skip("llm.base_url or llm.model not configured")
    except Exception as e:
        pytest.skip(f"Config unavailable: {e}")


_LONG_PROSE = """\
The meeting was held in order to discuss the various matters that had been brought
to the attention of the committee over the course of the previous quarter. In particular,
the team wanted to make sure that they had an opportunity to review the findings that had
been submitted in the report that was published last month by the research division.
After a thorough and comprehensive discussion, the committee came to the conclusion that
additional follow-up work would need to be completed before any final decisions could
be made regarding the proposed changes to the existing policy framework.
"""

_CODE_BLOCK_TEXT = """\
The function processes the input.

```python
def process(data: list[int]) -> int:
    return sum(x * 2 for x in data if x > 0)
```

Results are returned as an integer.
"""

_SECURITY_WARNING = """\
WARNING: This operation will permanently delete all user data from the database.
This action cannot be undone. Please confirm that you want to proceed.
"""


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.network
class TestCompactIntegration:
    """Live integration tests for compact() tool."""

    def setup_method(self):
        _skip_if_not_configured()
        import ottools.ot_caveman as cav

        cav._client_cache.clear()

    def test_reduces_prose(self):
        from ottools.ot_caveman import compact

        result = compact(text=_LONG_PROSE)
        assert isinstance(result, dict)
        assert result["tokens_out"] < result["tokens_in"]
        assert result["reduction_pct"] > 0
        assert len(result["text"]) > 10

    def test_code_block_untouched(self):
        from ottools.ot_caveman import compact

        result = compact(text=_CODE_BLOCK_TEXT)
        assert isinstance(result, dict)
        # The code block must appear verbatim
        assert "def process(data: list[int]) -> int:" in result["text"]
        assert "return sum(x * 2 for x in data if x > 0)" in result["text"]

    def test_security_warning_untouched(self):
        from ottools.ot_caveman import compact

        result = compact(text=_SECURITY_WARNING)
        assert isinstance(result, dict)
        # The core warning content must be preserved
        assert "permanently delete" in result["text"].lower()
        assert "cannot be undone" in result["text"].lower()

    def test_file_round_trip(self, tmp_path):
        from unittest.mock import patch

        from ottools.ot_caveman import compact

        input_file = tmp_path / "input.md"
        output_file = tmp_path / "output.md"
        input_file.write_text(_LONG_PROSE)

        with patch("ottools.ot_caveman.resolve_cwd_path", side_effect=lambda p: tmp_path / p):
            result = compact(src="input.md", dest="output.md")

        assert isinstance(result, dict)
        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0
        assert len(content) < len(_LONG_PROSE)


@pytest.mark.integration
@pytest.mark.tools
@pytest.mark.network
class TestExpandIntegration:
    """Live integration tests for expand() tool."""

    _PACKED = "meeting held discuss matters committee prev quarter. research report findings reviewed. more follow-up needed before policy changes."

    def setup_method(self):
        _skip_if_not_configured()
        import ottools.ot_caveman as cav

        cav._client_cache.clear()

    def test_expands_packed_prose(self):
        from ottools.ot_caveman import expand

        result = expand(text=self._PACKED)
        assert isinstance(result, dict)
        assert len(result["text"]) > len(self._PACKED)
        assert result["expansion_pct"] > 0

    def test_code_block_untouched(self):
        from ottools.ot_caveman import expand

        packed_with_code = "short text\n\n```python\nprint('hello')\n```"
        result = expand(text=packed_with_code)
        assert isinstance(result, dict)
        assert "print('hello')" in result["text"]

    def test_expand_produces_readable_prose(self):
        from ottools.ot_caveman import expand

        result = expand(text=self._PACKED)
        assert isinstance(result, dict)
        # Expanded text should be longer and contain common words
        expanded = result["text"].lower()
        common_words = ["the", "a", "an", "was", "were", "had", "have", "be"]
        assert any(w in expanded.split() for w in common_words), (
            "Expanded text should contain common articles/verbs for readability"
        )
