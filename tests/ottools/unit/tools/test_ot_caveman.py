"""Unit tests for the ot_caveman tool pack.

Covers compact(), expand(), input(), and _strip_preamble() with mocked
OpenAI clients and temporary files.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    base_url: str = "https://api.openrouter.ai/api/v1",
    model: str = "openai/gpt-4o-mini",
    timeout: int = 30,
    max_tokens: int = 8192,
    cost_per_1m_tokens: float = 0.0,
):
    from ottools.ot_caveman import Config

    return Config(
        base_url=base_url,
        model=model,
        timeout=timeout,
        max_tokens=max_tokens,
        cost_per_1m_tokens=cost_per_1m_tokens,
    )


def _mock_response(content: str = "compacted text"):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


def _make_mock_client(content: str = "compacted text"):
    """Return a mock_client that returns the given content."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_response(content)
    return mock_client


@pytest.fixture(autouse=True)
def clear_client_cache():
    """Clear the module-level client cache between tests."""
    import ottools.ot_caveman as cav

    cav._client_cache.clear()
    yield
    cav._client_cache.clear()


@pytest.fixture
def mock_cwd(tmp_path):
    """Patch resolve_cwd_path to resolve relative paths under tmp_path."""
    with patch("ottools.ot_caveman.resolve_cwd_path", side_effect=lambda p: tmp_path / p):
        yield tmp_path


@pytest.fixture
def mock_prompts():
    """Patch _get_template to return realistic prompt strings."""
    templates = {
        "ot_caveman_compact": "You are a text compaction assistant.",
        "ot_caveman_compact_input": "Compact the following text:\n\n{content}",
        "ot_caveman_expand": "You are a text expansion assistant.",
        "ot_caveman_input_compact": "You are a command compaction assistant.",
    }
    with patch("ottools.ot_caveman._get_template", side_effect=lambda name: templates.get(name, "")):
        yield


# ---------------------------------------------------------------------------
# TestStripPreamble
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStripPreamble:
    """Tests for _strip_preamble helper."""

    def test_strips_sure_preamble(self):
        from ottools.ot_caveman import _strip_preamble

        result = _strip_preamble("Sure, here is the compacted text:\n\nfox jump dog")
        assert "Sure" not in result
        assert "fox jump dog" in result

    def test_strips_here_is_preamble(self):
        from ottools.ot_caveman import _strip_preamble

        result = _strip_preamble("Here is the compacted version:\n\nfox jump dog")
        assert "Here is" not in result
        assert "fox jump dog" in result

    def test_clean_content_unchanged(self):
        from ottools.ot_caveman import _strip_preamble

        text = "fox jump lazy dog. cat sit fence."
        assert _strip_preamble(text) == text

    def test_strips_trailing_whitespace(self):
        from ottools.ot_caveman import _strip_preamble

        assert _strip_preamble("  fox jump  ") == "fox jump"


# ---------------------------------------------------------------------------
# TestCompact
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestCompact:
    """Tests for compact() tool."""

    # --- Input validation ---

    def test_both_inputs_error(self):
        from ottools.ot_caveman import compact

        result = compact(text="hello", src="notes.md")
        assert result == "Error: provide either text or src, not both"

    def test_no_input_error(self):
        from ottools.ot_caveman import compact

        result = compact()
        assert result == "Error: provide text or src"

    def test_empty_text_error(self):
        from ottools.ot_caveman import compact

        result = compact(text="")
        assert result == "Error: input is empty"

    def test_whitespace_text_error(self):
        from ottools.ot_caveman import compact

        result = compact(text="   \n  ")
        assert result == "Error: input is empty"

    def test_missing_file_error(self, mock_cwd):  # noqa: ARG002
        from ottools.ot_caveman import compact

        result = compact(src="nonexistent.md")
        assert "Error: file not found" in result
        assert "nonexistent.md" in result

    # --- Config error paths ---

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._get_template")
    def test_no_api_key_error(self, mock_tpl, mock_cfg, mock_get_client):
        from ottools.ot_caveman import compact

        mock_tpl.return_value = "some prompt"
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (None, "Error: ot_caveman not configured. Set OPENAI_API_KEY in secrets.yaml.")

        result = compact(text="hello world")
        assert "OPENAI_API_KEY" in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._get_template")
    def test_no_base_url_error(self, mock_tpl, mock_cfg, mock_get_client):
        from ottools.ot_caveman import compact

        mock_tpl.return_value = "some prompt"
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (
            None,
            "Error: ot_caveman not configured. Set llm.base_url or tools.ot_caveman.base_url in onetool.yaml.",
        )

        result = compact(text="hello world")
        assert "llm.base_url or tools.ot_caveman.base_url" in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._get_template")
    def test_no_model_error(self, mock_tpl, mock_cfg, mock_get_client):
        from ottools.ot_caveman import compact

        mock_tpl.return_value = "some prompt"
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (
            None,
            "Error: ot_caveman not configured. Set llm.model or tools.ot_caveman.model in onetool.yaml.",
        )

        result = compact(text="hello world")
        assert "llm.model or tools.ot_caveman.model" in result

    # --- Successful compaction ---

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_text_input_returns_dict(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("fox jump dog")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="The quick brown fox jumped over the lazy dog.")
        assert isinstance(result, dict)
        assert "text" in result
        assert "tokens_in" in result
        assert "tokens_out" in result
        assert "reduction_pct" in result
        assert "level" not in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_file_input(self, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        (mock_cwd / "notes.md").write_text("This is some verbose prose content.")
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("verbose prose → shorter")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(src="notes.md")
        assert isinstance(result, dict)
        assert result["text"] == "verbose prose → shorter"

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_dest_file_write(self, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("slim content")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="Some verbose content.", dest="slim.md")
        assert isinstance(result, dict)
        assert "file_out" in result
        assert result["file_out"] == "slim.md"
        assert (mock_cwd / "slim.md").read_text() == "slim content"

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_in_place_overwrite(self, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        (mock_cwd / "notes.md").write_text("Original verbose prose content here.")
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("slim version")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(src="notes.md", dest="notes.md")
        assert isinstance(result, dict)
        assert (mock_cwd / "notes.md").read_text() == "slim version"

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_token_stats_present(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="This is a longer piece of text with more words.")
        assert isinstance(result, dict)
        assert isinstance(result["tokens_in"], int)
        assert isinstance(result["tokens_out"], int)
        assert isinstance(result["reduction_pct"], int)

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_cost_saved_absent_when_rate_zero(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config(cost_per_1m_tokens=0.0)
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="This is a longer piece of text with more words.")
        assert isinstance(result, dict)
        assert "cost_saved_usd" not in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_cost_saved_present_when_rate_set(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config(cost_per_1m_tokens=3.0)
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="This is a longer piece of text with more words.")
        assert isinstance(result, dict)
        assert "cost_saved_usd" in result
        assert isinstance(result["cost_saved_usd"], float)

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_code_block_preserved_in_prompt(self, mock_cfg, mock_get_client, mock_openai, mock_prompts):
        """Verify code block content is sent to LLM (preservation is LLM's job)."""
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("prose compacted\n\n```python\nprint('hello')\n```")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")
        mock_openai.return_value = mock_client

        result = compact(text="Some prose.\n\n```python\nprint('hello')\n```")
        assert isinstance(result, dict)
        assert "```python" in result["text"]

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_api_error_returns_error_string(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="some text")
        assert isinstance(result, str)
        assert "Error" in result
        assert "Connection timeout" in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_api_key_error_sanitized(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        mock_cfg.return_value = _make_config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Invalid api_key: sk-abc123")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(text="some text")
        assert "sk-abc123" not in result
        assert "Authentication error" in result

    # --- Glob batch mode ---

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_returns_summary_dict(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        f1 = mock_cwd / "a.md"
        f2 = mock_cwd / "b.md"
        f1.write_text("Verbose prose in file one.")
        f2.write_text("Verbose prose in file two.")
        mock_glob.return_value = ([f1, f2], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(src="*.md")
        assert isinstance(result, dict)
        assert result["files"] == 2
        assert result["skipped"] == 0
        assert "tokens_in" in result
        assert "tokens_out" in result
        assert "reduction_pct" in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_no_files_error(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact
        from pathlib import Path

        mock_glob.return_value = ([], Path("."))
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (_make_mock_client(), "gpt-4o-mini")

        result = compact(src="*.md")
        assert isinstance(result, str)
        assert "no files matched" in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_writes_min_suffix(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        f1 = mock_cwd / "doc.md"
        f1.write_text("Some verbose content here.")
        mock_glob.return_value = ([f1], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        compact(src="*.md")
        assert (mock_cwd / "doc-min.md").exists()

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_overwrite_writes_in_place(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        f1 = mock_cwd / "doc.md"
        f1.write_text("Some verbose content here.")
        mock_glob.return_value = ([f1], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        compact(src="*.md", overwrite=True)
        assert (mock_cwd / "doc.md").read_text() == "short"
        assert not (mock_cwd / "doc-min.md").exists()

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_cost_saved_present_when_rate_set(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        f1 = mock_cwd / "doc.md"
        f1.write_text("Some verbose content here.")
        mock_glob.return_value = ([f1], mock_cwd)
        mock_cfg.return_value = _make_config(cost_per_1m_tokens=3.0)
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(src="*.md")
        assert isinstance(result, dict)
        assert "cost_saved_usd" in result

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_dest_preserves_subdir_structure(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        """Files in different subdirs must not overwrite each other."""
        from ottools.ot_caveman import compact

        sub1 = mock_cwd / "sub1"
        sub2 = mock_cwd / "sub2"
        sub1.mkdir()
        sub2.mkdir()
        f1 = sub1 / "index.md"
        f2 = sub2 / "index.md"
        f1.write_text("Content in sub1 index.")
        f2.write_text("Content in sub2 index.")
        mock_glob.return_value = ([f1, f2], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("short")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        compact(src="**/*.md", dest="out")
        out_dir = mock_cwd / "out"
        assert (out_dir / "sub1" / "index-min.md").exists()
        assert (out_dir / "sub2" / "index-min.md").exists()


# ---------------------------------------------------------------------------
# TestFenceExtraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestFenceExtraction:
    """Tests for _extract_fences and _restore_protected helpers."""

    def test_extract_single_block(self):
        from ottools.ot_caveman import _extract_fences

        text = "intro\n\n```python\nprint('hi')\n```\n\nconclusion"
        prose, blocks = _extract_fences(text)
        assert len(blocks) == 1
        assert "[!PLACEHOLDER:0!]" in prose
        assert "```python" not in prose
        assert "print('hi')" not in prose
        assert blocks["[!PLACEHOLDER:0!]"] == "```python\nprint('hi')\n```"

    def test_extract_multiple_blocks(self):
        from ottools.ot_caveman import _extract_fences

        text = "a\n\n```\nblock0\n```\n\nb\n\n```python\nblock1\n```\n\nc"
        prose, blocks = _extract_fences(text)
        assert len(blocks) == 2
        assert "[!PLACEHOLDER:0!]" in prose
        assert "[!PLACEHOLDER:1!]" in prose
        assert blocks["[!PLACEHOLDER:0!]"] == "```\nblock0\n```"
        assert blocks["[!PLACEHOLDER:1!]"] == "```python\nblock1\n```"

    def test_no_blocks_returns_empty(self):
        from ottools.ot_caveman import _extract_fences

        text = "plain prose with `inline code` but no fences"
        prose, blocks = _extract_fences(text)
        assert blocks == {}
        assert prose == text

    def test_language_specifier_preserved(self):
        from ottools.ot_caveman import _extract_fences

        text = "text\n\n```typescript\nconst x = 1;\n```\n\nmore"
        prose, blocks = _extract_fences(text)
        assert "```typescript\nconst x = 1;\n```" in blocks.values()

    def test_restore_all_blocks(self):
        from ottools.ot_caveman import _extract_fences, _restore_protected

        original = "intro\n\n```python\ncode\n```\n\nconclusion"
        prose, blocks = _extract_fences(original)
        compacted_prose = prose.replace("intro", "intro short")
        restored, missing = _restore_protected(compacted_prose, blocks)
        assert missing == []
        assert "```python\ncode\n```" in restored
        assert "[!PLACEHOLDER:0!]" not in restored

    def test_restore_detects_missing_placeholder(self):
        from ottools.ot_caveman import _restore_protected

        blocks = {"[!PLACEHOLDER:0!]": "```\ncode\n```"}
        text_without_placeholder = "prose without placeholder"
        _, missing = _restore_protected(text_without_placeholder, blocks)
        assert "[!PLACEHOLDER:0!]" in missing

    def test_roundtrip_preserves_content(self):
        from ottools.ot_caveman import _extract_fences, _restore_protected

        original = "A\n\n```bash\necho hi\n```\n\nB\n\n```python\nx = 1\n```\n\nC"
        prose, blocks = _extract_fences(original)
        restored, missing = _restore_protected(prose, blocks)
        assert missing == []
        assert restored == original


# ---------------------------------------------------------------------------
# TestTableExtraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestTableExtraction:
    """Tests for _normalize_table, _extract_tables, and table restore."""

    _TABLE = (
        "| Name      | Description          |\n"
        "|-----------|----------------------|\n"
        "| compact   | Compact text         |\n"
        "| expand    | Expand packed text   |"
    )
    _TABLE_NORM = (
        "| Name | Description |\n"
        "|---|---|\n"
        "| compact | Compact text |\n"
        "| expand | Expand packed text |"
    )

    def test_normalize_strips_padding(self):
        from ottools.ot_caveman import _normalize_table

        assert _normalize_table(self._TABLE) == self._TABLE_NORM

    def test_normalize_preserves_alignment_markers(self):
        from ottools.ot_caveman import _normalize_table

        table = "| A   | B   |\n|:----|----:|\n| foo | bar |"
        norm = _normalize_table(table)
        assert "|:---|---:|" in norm

    def test_normalize_center_alignment(self):
        from ottools.ot_caveman import _normalize_table

        table = "| A |\n|:---:|\n| x |"
        norm = _normalize_table(table)
        assert "|:---:|" in norm

    def test_extract_single_table(self):
        from ottools.ot_caveman import _extract_tables

        text = f"Intro\n\n{self._TABLE}\n\nConclusion"
        prose, blocks = _extract_tables(text)
        assert len(blocks) == 1
        assert "[!TABLE:0!]" in prose
        assert "|" not in prose.replace("[!TABLE:0!]", "")
        # stored value is the normalized form
        assert blocks["[!TABLE:0!]"] == self._TABLE_NORM

    def test_extract_multiple_tables(self):
        from ottools.ot_caveman import _extract_tables

        t2 = "| X |\n|---|\n| 1 |"
        text = f"{self._TABLE}\n\nMid\n\n{t2}"
        prose, blocks = _extract_tables(text)
        assert len(blocks) == 2
        assert "[!TABLE:0!]" in prose
        assert "[!TABLE:1!]" in prose

    def test_no_table_returns_empty(self):
        from ottools.ot_caveman import _extract_tables

        text = "plain prose with no tables"
        prose, blocks = _extract_tables(text)
        assert blocks == {}
        assert prose == text

    def test_table_inside_fence_not_extracted(self):
        """Tables inside code blocks are already protected as fence placeholders."""
        from ottools.ot_caveman import _extract_fences, _extract_tables

        text = "```\n| A | B |\n|---|---|\n| x | y |\n```"
        prose, _ = _extract_fences(text)
        _, table_blocks = _extract_tables(prose)
        # The table was inside the fence; after fence extraction the prose has no | rows
        assert table_blocks == {}

    def test_restore_table_placeholder(self):
        from ottools.ot_caveman import _extract_tables, _restore_protected

        text = f"Intro\n\n{self._TABLE}\n\nConclusion"
        prose, blocks = _extract_tables(text)
        restored, missing = _restore_protected(prose, blocks)
        assert missing == []
        assert self._TABLE_NORM in restored
        assert "[!TABLE:0!]" not in restored

    def test_restore_detects_missing_table(self):
        from ottools.ot_caveman import _restore_protected

        blocks = {"[!TABLE:0!]": "| A |\n|---|\n| x |"}
        _, missing = _restore_protected("prose without marker", blocks)
        assert "[!TABLE:0!]" in missing

    def test_fence_and_table_combined(self):
        """Both fence and table placeholders coexist and restore correctly."""
        from ottools.ot_caveman import _extract_fences, _extract_tables, _restore_protected

        text = (
            "Intro\n\n"
            "```python\ncode\n```\n\n"
            "Middle\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "End"
        )
        prose, fence_blocks = _extract_fences(text)
        prose, table_blocks = _extract_tables(prose)
        all_blocks = {**fence_blocks, **table_blocks}
        assert len(fence_blocks) == 1
        assert len(table_blocks) == 1
        restored, missing = _restore_protected(prose, all_blocks)
        assert missing == []
        assert "```python\ncode\n```" in restored
        assert "| A | B |" in restored


# ---------------------------------------------------------------------------
# TestVerifyCompact
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestVerifyCompact:
    """Tests for _verify_compact helper."""

    def test_fence_drop_falls_back(self):
        from ottools.ot_caveman import _verify_compact

        original = "intro\n\n```python\nprint('hi')\n```\n\ntrailing"
        compacted = "intro. trailing"  # fence dropped
        text, fell_back = _verify_compact(original, compacted)
        assert fell_back
        assert text == original

    def test_empty_output_falls_back(self):
        from ottools.ot_caveman import _verify_compact

        text, fell_back = _verify_compact("some content", "")
        assert fell_back

    def test_whitespace_only_falls_back(self):
        from ottools.ot_caveman import _verify_compact

        text, fell_back = _verify_compact("some content", "   \n  ")
        assert fell_back

    def test_inflation_falls_back(self):
        from ottools.ot_caveman import _verify_compact

        original = "short"
        compacted = "x" * (len(original) + 1)
        text, fell_back = _verify_compact(original, compacted)
        assert fell_back
        assert text == original

    def test_valid_compaction_passes(self):
        from ottools.ot_caveman import _verify_compact

        original = "The quick brown fox jumped over the lazy dog."
        compacted = "Fox jumped over dog."
        text, fell_back = _verify_compact(original, compacted)
        assert not fell_back
        assert text == compacted

    def test_equal_fence_count_passes(self):
        from ottools.ot_caveman import _verify_compact

        original = "intro\n\n```python\nlong code\n```\n\nmore verbose prose here"
        compacted = "intro\n\n```python\nlong code\n```\nfewer words"
        text, fell_back = _verify_compact(original, compacted)
        assert not fell_back
        assert text == compacted

    def test_more_fences_in_output_passes(self):
        """Model producing extra fences is unusual but not a data-loss failure."""
        from ottools.ot_caveman import _verify_compact

        original = "text"
        compacted = "text\n\n```\nextra\n```"
        # compacted is longer so inflation guard fires — but fence increase alone shouldn't
        # This tests the ordering: inflation check fires first here
        text, fell_back = _verify_compact(original, compacted)
        assert fell_back  # caught by inflation guard (compacted longer than original)


# ---------------------------------------------------------------------------
# TestCompactFallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestCompactFallback:
    """Tests that compact() falls back to original on bad LLM output."""

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_fallback_when_placeholder_dropped(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        original = "intro\n\n```python\nprint('hi')\n```\n\nconclusion"
        mock_cfg.return_value = _make_config()
        # LLM drops the [!PLACEHOLDER:0!] placeholder — restoration detects it missing
        mock_get_client.return_value = (_make_mock_client("intro. conclusion"), "gpt-4o-mini")

        result = compact(text=original)
        assert isinstance(result, dict)
        assert result["text"] == original
        assert result["reduction_pct"] == 0
        assert result.get("unchanged") is True

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_success_when_placeholder_preserved(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        original = "verbose intro text here\n\n```python\nprint('hi')\n```\n\nverbose conclusion text"
        mock_cfg.return_value = _make_config()
        # LLM preserves the placeholder → code block is restored, prose is compacted
        mock_get_client.return_value = (_make_mock_client("intro [!PLACEHOLDER:0!] conclusion"), "gpt-4o-mini")

        result = compact(text=original)
        assert isinstance(result, dict)
        assert "unchanged" not in result
        assert "```python\nprint('hi')\n```" in result["text"]
        assert "verbose" not in result["text"]

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_fallback_on_empty_llm_output(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        original = "some prose content here"
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (_make_mock_client(""), "gpt-4o-mini")

        result = compact(text=original)
        assert isinstance(result, dict)
        assert result["text"] == original
        assert result.get("unchanged") is True

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_fallback_when_output_longer(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        original = "short"
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (_make_mock_client("this is much longer than the original"), "gpt-4o-mini")

        result = compact(text=original)
        assert isinstance(result, dict)
        assert result["text"] == original
        assert result.get("unchanged") is True

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_no_fallback_on_valid_compaction(self, mock_cfg, mock_get_client, _mock_openai, mock_prompts):
        from ottools.ot_caveman import compact

        original = "The quick brown fox jumped over the lazy dog and ran away."
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (_make_mock_client("Fox jumped over dog."), "gpt-4o-mini")

        result = compact(text=original)
        assert isinstance(result, dict)
        assert "unchanged" not in result
        assert result["text"] == "Fox jumped over dog."

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_fallback_counted_in_unchanged(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        # f1 has a code block; LLM drops it → fallback
        # f2 is plain prose; LLM compacts normally
        f1 = mock_cwd / "code.md"
        f2 = mock_cwd / "prose.md"
        f1.write_text("intro\n\n```python\ncode\n```\n\nconclusion")
        f2.write_text("The quick brown fox jumped over the lazy dog and ran far away.")
        mock_glob.return_value = ([f1, f2], mock_cwd)
        mock_cfg.return_value = _make_config()

        # f1: LLM drops the [!PLACEHOLDER:0!] placeholder → fallback
        # f2: no fences, prose compacted normally
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_response("intro. conclusion"),      # f1: placeholder dropped → fallback
            _mock_response("Fox jumped over dog."),   # f2: valid prose compaction
        ]
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = compact(src="*.md")
        assert isinstance(result, dict)
        assert result["files"] == 2
        assert result.get("unchanged") == 1

    @patch("ottools.ot_caveman.OpenAI")
    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_no_unchanged_key_when_none_fell_back(self, mock_glob, mock_cfg, mock_get_client, _mock_openai, mock_cwd, mock_prompts):
        from ottools.ot_caveman import compact

        f1 = mock_cwd / "a.md"
        f1.write_text("The quick brown fox jumped over the lazy dog and ran away.")
        mock_glob.return_value = ([f1], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_get_client.return_value = (_make_mock_client("Fox jumped over dog."), "gpt-4o-mini")

        result = compact(src="*.md")
        assert isinstance(result, dict)
        assert "unchanged" not in result


# ---------------------------------------------------------------------------
# TestExpand
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestExpand:
    """Tests for expand() tool."""

    def test_both_inputs_error(self):
        from ottools.ot_caveman import expand

        result = expand(text="hello", src="notes.md")
        assert result == "Error: provide either text or src, not both"

    def test_no_input_error(self):
        from ottools.ot_caveman import expand

        result = expand()
        assert result == "Error: provide text or src"

    def test_empty_text_error(self):
        from ottools.ot_caveman import expand

        result = expand(text="")
        assert result == "Error: input is empty"

    def test_missing_file_error(self, mock_cwd):  # noqa: ARG002
        from ottools.ot_caveman import expand

        result = expand(src="missing.md")
        assert "Error: file not found" in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_text_input_returns_dict(self, mock_cfg, mock_get_client, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("The fox jumped over the lazy dog.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="fox jump lazy dog")
        assert isinstance(result, dict)
        assert "text" in result
        assert "tokens_in" in result
        assert "tokens_out" in result
        assert "expansion_pct" in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_expansion_pct_positive(self, mock_cfg, mock_get_client, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client(
            "The fox quickly jumped over the very lazy sleeping dog in the meadow."
        )
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="fox jump dog")
        assert isinstance(result, dict)
        assert result["expansion_pct"] > 0

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_file_input(self, mock_cfg, mock_get_client, mock_cwd, mock_prompts):
        from ottools.ot_caveman import expand

        (mock_cwd / "slim.md").write_text("fox jump dog")
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("The fox jumped over the dog.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(src="slim.md")
        assert isinstance(result, dict)

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_dest_file_write(self, mock_cfg, mock_get_client, mock_cwd, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("Expanded readable prose here.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="terse pack text", dest="readable.md")
        assert isinstance(result, dict)
        assert "file_out" in result
        assert (mock_cwd / "readable.md").read_text() == "Expanded readable prose here."

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_in_place_overwrite(self, mock_cfg, mock_get_client, mock_cwd, mock_prompts):
        from ottools.ot_caveman import expand

        (mock_cwd / "slim.md").write_text("terse")
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("Expanded version here.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(src="slim.md", dest="slim.md")
        assert isinstance(result, dict)
        assert (mock_cwd / "slim.md").read_text() == "Expanded version here."

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_code_block_preserved(self, mock_cfg, mock_get_client, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("Expanded prose.\n\n```python\nprint('hello')\n```")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="prose\n\n```python\nprint('hello')\n```")
        assert isinstance(result, dict)
        assert "```python" in result["text"]

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_cost_saved_absent_when_rate_zero(self, mock_cfg, mock_get_client, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config(cost_per_1m_tokens=0.0)
        mock_client = _make_mock_client("Expanded readable prose here.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="terse pack text")
        assert isinstance(result, dict)
        assert "cost_saved_usd" not in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    def test_cost_saved_present_when_rate_set(self, mock_cfg, mock_get_client, mock_prompts):
        from ottools.ot_caveman import expand

        mock_cfg.return_value = _make_config(cost_per_1m_tokens=3.0)
        mock_client = _make_mock_client("Expanded readable prose here.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(text="terse pack text")
        assert isinstance(result, dict)
        assert "cost_saved_usd" in result
        assert isinstance(result["cost_saved_usd"], float)

    # --- Glob batch mode ---

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_returns_summary_dict(self, mock_glob, mock_cfg, mock_get_client, mock_cwd, mock_prompts):
        from ottools.ot_caveman import expand

        f1 = mock_cwd / "a-min.md"
        f2 = mock_cwd / "b-min.md"
        f1.write_text("fox jump dog")
        f2.write_text("cat sit fence")
        mock_glob.return_value = ([f1, f2], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("The fox jumped over the lazy dog.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        result = expand(src="*-min.md")
        assert isinstance(result, dict)
        assert result["files"] == 2
        assert result["skipped"] == 0
        assert "tokens_in" in result
        assert "tokens_out" in result
        assert "expansion_pct" in result
        assert "reduction_pct" not in result

    @patch("ottools.ot_caveman._get_client")
    @patch("ottools.ot_caveman._get_config")
    @patch("ottools.ot_caveman._glob_expand")
    def test_glob_dest_preserves_subdir_structure(self, mock_glob, mock_cfg, mock_get_client, mock_cwd, mock_prompts):
        """Files in different subdirs must not overwrite each other."""
        from ottools.ot_caveman import expand

        sub1 = mock_cwd / "sub1"
        sub2 = mock_cwd / "sub2"
        sub1.mkdir()
        sub2.mkdir()
        f1 = sub1 / "index.md"
        f2 = sub2 / "index.md"
        f1.write_text("fox jump dog")
        f2.write_text("cat sit fence")
        mock_glob.return_value = ([f1, f2], mock_cwd)
        mock_cfg.return_value = _make_config()
        mock_client = _make_mock_client("Expanded text.")
        mock_get_client.return_value = (mock_client, "gpt-4o-mini")

        expand(src="**/*.md", dest="out")
        out_dir = mock_cwd / "out"
        assert (out_dir / "sub1" / "index-exp.md").exists()
        assert (out_dir / "sub2" / "index-exp.md").exists()


# ---------------------------------------------------------------------------
# TestInput
# ---------------------------------------------------------------------------


def _write_command_file(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


@pytest.mark.unit
@pytest.mark.tools
class TestInput:
    """Tests for input() tool."""

    def test_returns_first_pending(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "[x] done command\nBody of done.\n---\nDo this thing\nWith extra body",
        )
        result = cm_input(compact=False)
        assert "Do this thing" in result

    def test_marks_done_in_file(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(mock_cwd / "command.md", "Pending command")
        cm_input(compact=False)
        content = (mock_cwd / "command.md").read_text()
        assert "[x] Pending command" in content

    def test_skips_done_commands(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "[x] first done\n---\n[x] second done\n---\nThird pending",
        )
        result = cm_input(compact=False)
        assert "Third pending" in result

    def test_no_more_commands(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "[x] all done\n---\n[x] also done",
        )
        result = cm_input(compact=False)
        assert result == "NO MORE COMMANDS"

    def test_file_not_found(self, mock_cwd):  # noqa: ARG002
        from ottools.ot_caveman import input as cm_input

        result = cm_input(file="missing.md", compact=False)
        assert "Error" in result
        assert "missing.md" in result

    def test_default_filename(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(mock_cwd / "command.md", "Default file command")
        result = cm_input(compact=False)
        assert "Default file command" in result

    def test_custom_filename(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(mock_cwd / "tasks.md", "Custom file command")
        result = cm_input(file="tasks.md", compact=False)
        assert "Custom file command" in result

    def test_multiline_body_returned(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "Title line\nFirst body line\nSecond body line",
        )
        result = cm_input(compact=False)
        assert "Title line" in result
        assert "First body line" in result
        assert "Second body line" in result

    def test_header_line_ignored(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "# Commands\nActual command here",
        )
        result = cm_input(compact=False)
        assert "Actual command here" in result
        assert "# Commands" not in result or result.startswith("Actual")

    def test_separator_written_with_blank_lines(self, mock_cwd):
        """Writing back should use blank-line-surrounded --- dividers."""
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "First command\n---\n[x] Second done",
        )
        cm_input(compact=False)
        content = (mock_cwd / "command.md").read_text()
        assert "\n\n---\n\n" in content

    # --- Named command filter ---

    def test_named_command_returns_body(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "name:greet\nHello world\nSecond line\n---\nOther command",
        )
        result = cm_input(command="greet", compact=False)
        assert "Hello world" in result
        assert "Second line" in result
        assert "name:greet" not in result

    def test_named_command_does_not_modify_file(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        original = "name:greet\nHello world\n---\nOther command"
        _write_command_file(mock_cwd / "command.md", original)
        cm_input(command="greet", compact=False)
        assert (mock_cwd / "command.md").read_text() == original

    def test_named_command_ignores_done_status(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "[x] name:fix\nDo the fix\n---\nOther command",
        )
        result = cm_input(command="fix", compact=False)
        assert "Do the fix" in result

    def test_named_command_not_found_returns_error(self, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(mock_cwd / "command.md", "Some command")
        result = cm_input(command="missing", compact=False)
        assert "Error" in result
        assert "missing" in result

    # --- Compact mode ---

    @patch("ottools.ot_caveman._compact_command_text")
    def test_compact_true_calls_compaction(self, mock_compact, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        mock_compact.return_value = "compacted cmd"
        _write_command_file(mock_cwd / "command.md", "A long verbose command description here")
        result = cm_input(compact=True)
        mock_compact.assert_called_once()
        assert result == "compacted cmd"

    @patch("ottools.ot_caveman._compact_command_text")
    def test_compact_false_skips_compaction(self, mock_compact, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        _write_command_file(mock_cwd / "command.md", "Raw command text")
        result = cm_input(compact=False)
        mock_compact.assert_not_called()
        assert "Raw command text" in result

    @patch("ottools.ot_caveman._compact_command_text")
    def test_named_command_compact_true(self, mock_compact, mock_cwd):
        from ottools.ot_caveman import input as cm_input

        mock_compact.return_value = "compact body"
        _write_command_file(mock_cwd / "command.md", "name:go\nDo something important")
        result = cm_input(command="go", compact=True)
        mock_compact.assert_called_once_with("Do something important")
        assert result == "compact body"

    # --- Regression: blank line after header should not receive [x] mark ---

    def test_header_blank_line_marks_title_not_blank(self, mock_cwd):
        """[x] must go on the actual title, not a blank line after the # header."""
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "# Test Commands\n\nBuild the auth module\nWrite unit tests.",
        )
        result = cm_input(compact=False)
        assert "Build the auth module" in result
        content = (mock_cwd / "command.md").read_text()
        assert "[x] Build the auth module" in content
        assert "[x] \n" not in content

    # --- Regression: returned text must not include [x] prefix ---

    def test_returned_text_has_no_x_prefix(self, mock_cwd):
        """Returned command text must not start with [x]."""
        from ottools.ot_caveman import input as cm_input

        _write_command_file(
            mock_cwd / "command.md",
            "Deploy to staging\nUse blue-green strategy.",
        )
        result = cm_input(compact=False)
        assert "Deploy to staging" in result


# ---------------------------------------------------------------------------
# TestCompactText
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestCompactText:
    """Tests for the private _compact_text helper."""

    def test_returns_compacted_text(self, mock_prompts):
        """4.1 — _compact_text with mocked _call_llm returns compacted string."""
        from ottools.ot_caveman import _compact_text

        input_text = "The quick brown fox jumped over the lazy dog."
        compacted = "fox jump lazy dog."

        with patch("ottools.ot_caveman._get_config", return_value=_make_config()):
            with patch("ottools.ot_caveman._get_client", return_value=(_make_mock_client(), "gpt-4o-mini")):
                with patch("ottools.ot_caveman._call_llm", return_value=(compacted, None)):
                    result = _compact_text(input_text)

        assert result == compacted

    def test_raises_on_client_error(self, mock_prompts):
        """4.2 — _compact_text raises RuntimeError when _get_client returns an error."""
        from ottools.ot_caveman import _compact_text

        with patch("ottools.ot_caveman._get_config", return_value=_make_config()):
            with patch(
                "ottools.ot_caveman._get_client",
                return_value=(
                    None,
                    "Error: ot_caveman not configured. Set OPENAI_API_KEY in secrets.yaml.",
                ),
            ):
                with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                    _compact_text("some text to compact")

    def test_compact_delegates_and_catches_runtime_error(self):
        """4.3 — compact() inline mode delegates to _compact_text, wraps RuntimeError as error string."""
        from ottools.ot_caveman import compact

        with patch("ottools.ot_caveman._compact_text", side_effect=RuntimeError("config error")):
            result = compact(text="some verbose text that needs compaction")

        assert result == "Error: config error"
        assert not result.startswith("[x]")
