"""Unit tests for vendored fuzzy file reference matching."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
def test_fzy_scorer_prefers_path_word_initials() -> None:
    """Verify compact initials can match path word starts."""
    from otutil.tools._file_resolve_match import fuzzy_match

    paths = [
        "src/otutil/tools/file.py",
        "docs/reference/tools/file.md",
        "tests/unit/core/test_log_format.py",
        "tests/otutil/unit/tools/test_file.py",
    ]

    results = fuzzy_match("tlf", paths, limit=3)

    assert results[0].value == "tests/unit/core/test_log_format.py"
    assert results[0].indices == [16, 21, 25]


@pytest.mark.unit
@pytest.mark.tools
def test_fzy_scorer_supports_space_separated_quick_open_query() -> None:
    """Verify spaces are removed for quick-open style matching."""
    from otutil.tools._file_resolve_match import fuzzy_match

    paths = [
        "wip/backups/chat_ops-pre-v3-20260506-111941.zip",
        "wip/notes/onetool-mcp-2026.md",
        "wip/test-output/compare-runtime-20260516.md",
        "wip/test-output/runtime-pack-test-2026-05-23.md",
    ]

    results = fuzzy_match("wip 2026", paths, limit=4)

    assert [item.value for item in results] == [
        "wip/notes/onetool-mcp-2026.md",
        "wip/backups/chat_ops-pre-v3-20260506-111941.zip",
        "wip/test-output/compare-runtime-20260516.md",
        "wip/test-output/runtime-pack-test-2026-05-23.md",
    ]


@pytest.mark.unit
@pytest.mark.tools
def test_fzy_scorer_returns_no_match_for_non_subsequence() -> None:
    """Verify non-subsequence candidates are excluded."""
    from otutil.tools._file_resolve_match import fuzzy_match

    assert fuzzy_match("zzzz", ["tests/unit/core/test_log_format.py"]) == []


@pytest.mark.unit
@pytest.mark.tools
def test_fzy_scorer_returns_empty_for_empty_query() -> None:
    """Verify empty queries do not score every candidate."""
    from otutil.tools._file_resolve_match import fuzzy_match

    assert fuzzy_match("", ["tests/unit/core/test_log_format.py"]) == []
    assert fuzzy_match("   ", ["tests/unit/core/test_log_format.py"]) == []


@pytest.mark.unit
@pytest.mark.tools
def test_fzy_scorer_returns_empty_for_non_positive_limit() -> None:
    """Verify non-positive limits avoid retaining results."""
    from otutil.tools._file_resolve_match import fuzzy_match

    assert fuzzy_match("tlf", ["tests/unit/core/test_log_format.py"], limit=0) == []
    assert fuzzy_match("tlf", ["tests/unit/core/test_log_format.py"], limit=-1) == []
