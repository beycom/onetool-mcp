"""Fzy-style fuzzy matching for file references.

Based on pfzy by Kevin Zhuang (MIT).
https://github.com/kazhala/pfzy

pfzy is a Python port of fzy by John Hawthorn (MIT).
https://github.com/jhawthorn/fzy
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from heapq import nsmallest
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

ScoreIndices = tuple[float, list[int] | None]

SCORE_MIN = float("-inf")
SCORE_MAX = float("inf")
SCORE_GAP_LEADING = -0.005
SCORE_GAP_TRAILING = -0.005
SCORE_GAP_INNER = -0.01
SCORE_MATCH_CONSECUTIVE = 1.0

SCORE_MATCH_SLASH = 0.9
SCORE_MATCH_WORD = 0.8
SCORE_MATCH_CAPITAL = 0.7
SCORE_MATCH_DOT = 0.6


@dataclass(frozen=True)
class FuzzyMatch:
    """Ranked fuzzy match result."""

    value: str
    score: float
    indices: list[int]


def _char_range_with(
    char_start: str,
    char_stop: str,
    value: int | float,
    hash_table: dict[str, int | float],
) -> dict[str, int | float]:
    """Generate index mapping for bonus calculation."""
    updated = hash_table.copy()
    updated.update(
        (chr(uni_char), value)
        for uni_char in range(ord(char_start), ord(char_stop) + 1)
    )
    return updated


lower_with = partial(_char_range_with, "a", "z")
upper_with = partial(_char_range_with, "A", "Z")
digit_with = partial(_char_range_with, "0", "9")

BONUS_MAP = {
    "/": SCORE_MATCH_SLASH,
    "-": SCORE_MATCH_WORD,
    "_": SCORE_MATCH_WORD,
    " ": SCORE_MATCH_WORD,
    ".": SCORE_MATCH_DOT,
}
BONUS_STATES = [{}, BONUS_MAP, lower_with(SCORE_MATCH_CAPITAL, BONUS_MAP)]
BONUS_INDEX = cast("dict[str, int]", digit_with(1, lower_with(1, upper_with(2, {}))))


def _bonus(haystack: str) -> list[float]:
    """Calculate per-character boundary bonuses for a haystack."""
    prev_char = "/"
    bonus = []
    for char in haystack:
        bonus.append(BONUS_STATES[BONUS_INDEX.get(char, 0)].get(prev_char, 0))
        prev_char = char
    return bonus


def _score(needle: str, haystack: str, haystack_for_match: str) -> ScoreIndices:
    """Use fzy dynamic-programming scoring for one needle/haystack pair."""
    needle_len, haystack_len = len(needle), len(haystack)

    if needle_len == 0 or needle_len == haystack_len:
        return SCORE_MAX, list(range(needle_len))

    bonus_score = _bonus(haystack)

    running_score: list[list[float]] = [
        [0 for _ in range(haystack_len)] for _ in range(needle_len)
    ]
    result_score: list[list[float]] = [
        [0 for _ in range(haystack_len)] for _ in range(needle_len)
    ]

    for i in range(needle_len):
        prev_score = SCORE_MIN
        gap_score = SCORE_GAP_TRAILING if i == needle_len - 1 else SCORE_GAP_INNER

        for j in range(haystack_len):
            if needle[i] == haystack_for_match[j]:
                score = SCORE_MIN
                if i == 0:
                    score = j * SCORE_GAP_LEADING + bonus_score[j]
                elif j != 0:
                    score = max(
                        result_score[i - 1][j - 1] + bonus_score[j],
                        running_score[i - 1][j - 1] + SCORE_MATCH_CONSECUTIVE,
                    )
                running_score[i][j] = score
                result_score[i][j] = prev_score = max(score, prev_score + gap_score)
            else:
                running_score[i][j] = SCORE_MIN
                result_score[i][j] = prev_score = prev_score + gap_score

    i, j = needle_len - 1, haystack_len - 1
    match_required = False
    indices = [0 for _ in range(needle_len)]

    while i >= 0:
        while j >= 0:
            if (
                match_required or running_score[i][j] == result_score[i][j]
            ) and running_score[i][j] != SCORE_MIN:
                match_required = (
                    i > 0
                    and j > 0
                    and result_score[i][j]
                    == running_score[i - 1][j - 1] + SCORE_MATCH_CONSECUTIVE
                )
                indices[i] = j
                j -= 1
                break
            j -= 1
        i -= 1

    return result_score[needle_len - 1][haystack_len - 1], indices


def _subsequence(needle: str, haystack_for_match: str) -> bool:
    """Return whether needle is a subsequence of haystack_for_match."""
    if not needle:
        return True
    offset = 0
    for char in needle:
        offset = haystack_for_match.find(char, offset) + 1
        if offset <= 0:
            return False
    return True


def fzy_scorer(needle: str, haystack: str) -> ScoreIndices:
    """Score a fuzzy subsequence match using fzy semantics."""
    haystack_for_match = haystack.lower() if needle.islower() else haystack
    if _subsequence(needle, haystack_for_match):
        return _score(needle, haystack, haystack_for_match)
    return SCORE_MIN, None


def _iter_matches(needle: str, haystacks: list[str]) -> Iterator[FuzzyMatch]:
    """Yield matching haystacks without retaining the full result set."""
    for haystack in haystacks:
        score, indices = fzy_scorer(needle, haystack)
        if indices is None:
            continue
        yield FuzzyMatch(value=haystack, score=score, indices=indices)


def _match_sort_key(match: FuzzyMatch) -> tuple[float, str]:
    """Sort best fuzzy matches first with deterministic tie-breaking."""
    return -match.score, match.value.lower()


def fuzzy_match(
    needle: str,
    haystacks: list[str],
    *,
    limit: int | None = None,
) -> list[FuzzyMatch]:
    """Return haystacks ranked by fzy score.

    Args:
        needle: Query string to match. Spaces are treated as separators and
            removed to support quick-open queries such as ``"wip 2026"``.
        haystacks: Candidate strings.
        limit: Optional maximum number of results to return.

    Returns:
        Ranked fuzzy matches in descending score order.
    """
    query = needle.replace(" ", "")
    if not query:
        return []

    if limit is not None:
        if limit <= 0:
            return []
        return nsmallest(limit, _iter_matches(query, haystacks), key=_match_sort_key)

    matches = list(_iter_matches(query, haystacks))
    matches.sort(key=_match_sort_key)
    return matches
