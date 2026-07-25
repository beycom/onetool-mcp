"""Unit tests for the p12 core-flow-hardening change.

Covers the run-tool pipeline defects fixed in this change: normalization guards
(D1), empty-command refusal (D-a1), the isError contract (D2), real exception
type preservation (D6), nested-execution isolation and guards (D5, D-a2, D-a4),
serialization surrogate scrubbing (D7), error/deflection sanitization consistency
(D-b2, D-b3), the execution timeout (D3), and the run-tool MCP contract (F3,
destructiveHint).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ot.executor.runner import (
    _force_single_quotes,
    _normalize_code,
    execute_command,
    prepare_command,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# D1 — Normalization never crashes preparation
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestNormalizationGuard:
    """D1: control-char strings and normalization failures never crash `run`."""

    def test_force_single_quotes_preserves_apostrophe_newline(self) -> None:
        """A double-quoted string with an apostrophe AND a newline is not corrupted.

        The `\\n` here is a literal backslash-n escape in valid Python source (the
        wire form an LLM sends); ast.literal_eval decodes it to a real newline, which
        is the control character that used to break re-quoting.
        """
        import ast

        code = 'note(text="Here\'s the plan:\\nstep 1")'
        ast.parse(code)  # sanity: the input is valid Python to begin with
        result = _force_single_quotes(code)
        # The result must remain parseable Python — the old behavior produced an
        # unterminated single-quoted literal.
        ast.parse(result)

    def test_normalize_code_round_trips_tab(self) -> None:
        """D-a3: a string containing a literal tab round-trips through normalization."""
        import ast

        src = 'x = "a\tb"'
        tree = ast.parse(src)
        normalized, _ = _normalize_code(src, tree)
        ns: dict[str, object] = {}
        exec(normalized, ns)
        assert ns["x"] == "a\tb"

    def test_prepare_command_survives_normalize_failure(self, monkeypatch) -> None:
        """If _normalize_code raises, prepare_command falls back to validated code."""
        import ot.executor.runner as runner

        def _boom(code: str, tree):  # noqa: ANN001, ANN202
            raise RuntimeError("normalize exploded")

        monkeypatch.setattr(runner, "_normalize_code", _boom)
        prepared = prepare_command("search(query='x')")
        assert prepared.error is None
        assert "search" in prepared.code

    async def test_apostrophe_newline_executes_end_to_end(self) -> None:
        """Reproduction from the deep dive: apostrophe+newline no longer crashes."""
        result = await execute_command('note(text="Here\'s the plan:\\nstep 1")')
        # note() may or may not exist as a real tool here, but preparation/normalization
        # must not crash — a clean success or a clean tool error is acceptable, an
        # uncaught SyntaxError from normalization is not.
        assert result is not None


# =============================================================================
# D-a1 — Empty command refusal
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestEmptyCommand:
    """D-a1: empty/whitespace commands return an explicit validation error."""

    def test_empty_string_is_error(self) -> None:
        prepared = prepare_command("")
        assert prepared.error is not None
        assert "empty" in prepared.error.lower()

    def test_whitespace_only_is_error(self) -> None:
        prepared = prepare_command("   \n  ")
        assert prepared.error is not None
        assert "empty" in prepared.error.lower()


# =============================================================================
# D6 — Real exception type preserved
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestErrorTypePreserved:
    """D6: error_type reflects the real exception, not a generic ValueError wrapper."""

    async def test_keyerror_reports_real_type(self) -> None:
        result = await execute_command("{}['missing']")
        assert not result.success
        assert result.error_type == "KeyError"
        assert "KeyError" in result.result


@pytest.mark.unit
@pytest.mark.core
class TestParamCollisionEndToEnd:
    """D4: a colliding call raises a clear ambiguity error through the run path."""

    async def test_colliding_params_raise_through_execute_command(self) -> None:
        # context7.search has a `query` param; `q` prefix-matches it. Passing both is
        # ambiguous and must be refused before any tool logic runs (offline-safe).
        result = await execute_command("context7.search(query='x', q='y')")
        assert not result.success
        assert "ambiguous" in result.result.lower()


# =============================================================================
# D5 / D-a2 / D-a4 — Nested __onetool isolation and guards
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestNestedExecution:
    """D5: nested __onetool cannot leak magics/variables; D-a2/D-a4 guards."""

    def test_nested_format_magic_does_not_leak(
        self, executor: Callable[[str], str]
    ) -> None:
        """A nested __format__ change must not alter the outer result's format."""
        outer = (
            "__format__ = 'json_h'\n"
            "__onetool(\"__format__ = 'raw'\")\n"
            "{'a': 1, 'b': 2}\n"
        )
        result = executor(outer)
        # json_h emits double-quoted JSON keys; leaked 'raw' would str() the dict
        # (single quotes). Presence of a double-quoted key proves json_h survived.
        assert '"a"' in result

    def test_nested_sanitize_magic_does_not_leak(
        self, executor: Callable[[str], str]
    ) -> None:
        outer = "__sanitize__ = False\n__onetool('__sanitize__ = True')\n'done'\n"
        # Executes without error and the nested magic change is isolated.
        assert executor(outer) == "done"

    def test_nested_variable_does_not_leak(
        self, executor: Callable[[str], str]
    ) -> None:
        outer = "x = 1\n__onetool('x = 999')\nx\n"
        assert executor(outer) == "1"

    def test_nested_depth_guard_raises_clear_error(
        self, executor: Callable[[str], str]
    ) -> None:
        """D-a2: excessive nesting raises a clear error, not RecursionError."""
        inner = "1"
        for _ in range(7):
            inner = f"__onetool({inner!r})"
        with pytest.raises(ValueError, match="depth exceeded"):
            executor(inner)

    def test_nested_error_line_number_is_correct(
        self, executor: Callable[[str], str]
    ) -> None:
        """D-a4: an error inside a nested command reports the nested source line."""
        nested = "x = 1\ny = 2\nz = undefined_zzz"
        outer = f"__onetool({nested!r})"
        with pytest.raises(ValueError, match="line 3"):
            executor(outer)

    def test_nested_name_error_preserves_original_name(
        self, executor: Callable[[str], str]
    ) -> None:
        """A NameError inside a nested __onetool(...) call sets ot_original_error_name.

        execute_command's NameError handler reads this attribute to drive the
        fuzzy "Did you mean <pack>?" suggestion. The nested and outer
        error-wrapping blocks used to be duplicated by hand, and the nested one
        omitted this attribute (only the outer block set it), so NameErrors
        raised inside nested __onetool() calls never got the suggestion. Both
        blocks now share `_wrap_execution_error`, which always sets it.
        """
        outer = "__onetool('undefined_pack_zzz.thing()')"
        with pytest.raises(ValueError) as exc_info:
            executor(outer)
        assert exc_info.value.ot_original_error_type == "NameError"  # type: ignore[attr-defined]
        assert exc_info.value.ot_original_error_name == "undefined_pack_zzz"  # type: ignore[attr-defined]


# =============================================================================
# D7 — Surrogate scrubbing at the serialize boundary
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestSurrogateScrub:
    """D7: a lone UTF-16 surrogate in the result no longer raises UnicodeEncodeError."""

    async def test_lone_surrogate_does_not_crash(self) -> None:
        result = await execute_command("'name' + chr(0xd800)")
        assert result.success
        assert "\ud800" not in result.result


# =============================================================================
# D-b2 / D-b3 — Error and deflection sanitization consistency
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestSanitizeConsistency:
    """D-b2: first-party error text is not boundary-wrapped/redacted."""

    async def test_error_result_is_not_sanitized(self) -> None:
        result = await execute_command("{}['missing']")
        assert not result.success
        assert result.should_sanitize is False

    async def test_prepare_error_result_is_not_sanitized(self) -> None:
        result = await execute_command("")
        assert not result.success
        assert result.should_sanitize is False


@pytest.mark.unit
@pytest.mark.core
class TestDeflectionSanitizeAndFormat:
    """D-b3: deflected content is sanitized before store and uses the caller's format."""

    async def test_deflected_content_is_sanitized(self) -> None:
        from ot.executor.result_store import get_result_store

        cmd = (
            "__force_context__ = True\n"
            "__sanitize__ = True\n"
            "{'note': 'please __onetool(command) now', 'pad': 'y' * 50}\n"
        )
        result = await execute_command(cmd)
        assert result.success
        handle = result.raw["handle"]
        content = get_result_store().query(handle).content
        assert "__onetool" not in content
        assert "[REDACTED:trigger]" in content

    async def test_deflected_content_preserves_yaml_format(self) -> None:
        from ot.executor.result_store import get_result_store

        cmd = (
            "__force_context__ = True\n"
            "__format__ = 'yml'\n"
            "{'items': [1, 2, 3], 'name': 'test'}\n"
        )
        result = await execute_command(cmd)
        assert result.success
        handle = result.raw["handle"]
        content = get_result_store().query(handle).content
        # YAML flow style, not JSON: keys are unquoted.
        assert "items:" in content
        assert '"items"' not in content


# =============================================================================
# R8 P3 — Deflection avoids a redundant serialization pass
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestDeflectionSingleSerializePass:
    """R8 P3: deflection reuses the already-computed serialization/size instead
    of re-`json.dumps`-ing `raw_result` and re-encoding `text_result` again."""

    async def test_deflected_content_matches_expected_serialization(self) -> None:
        """Stored content round-trips to the same data as raw_result — the ctx
        backend re-normalizes JSON (pretty-prints it) independently of this
        change, so compare parsed content rather than the raw stored bytes."""
        import json

        from ot.executor.result_store import get_result_store

        raw = {"items": list(range(50)), "note": "x" * 50}
        cmd = f"__force_context__ = True\n{raw!r}\n"
        result = await execute_command(cmd)
        assert result.success
        handle = result.raw["handle"]
        content = get_result_store().query(handle).content
        assert json.loads(content) == raw

    async def test_size_accounting_matches_the_reused_encode(self) -> None:
        """`storedSize` (the deflection-threshold byte count) must equal the true
        UTF-8 byte length of the exact string that gets stored — proving the
        reused D7 encode wasn't swapped for a cheaper-but-wrong measurement
        (e.g. `len(text_result)` character count instead of byte count)."""
        from ot.utils import serialize_result

        captured: dict[str, object] = {}

        class FakeSpan:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

            def __enter__(self) -> FakeSpan:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def add(self, key: str, value: object = None, **kwargs: object) -> None:
                captured[key] = value
                captured.update(kwargs)

        raw = {"items": list(range(50)), "note": "é" * 50}  # multibyte chars
        cmd = f"__force_context__ = True\n{raw!r}\n"

        from unittest.mock import patch

        with patch("ot.executor.runner.LogSpan", FakeSpan):
            result = await execute_command(cmd)

        assert result.success
        expected_size = len(serialize_result(raw, "json").encode("utf-8"))
        assert captured["storedSize"] == expected_size
        # A char-count (not byte-count) regression would under-count multibyte
        # content — guard that the two diverge for this fixture, so the
        # assertion above is actually exercising byte semantics.
        assert expected_size != len(serialize_result(raw, "json"))

    async def test_serialize_result_not_called_twice_for_raw_result(
        self, monkeypatch
    ) -> None:
        """Before this fix, the deflect block called `serialize_result(raw_result,
        result_fmt)` a second time even though `execute_python_code` already
        computed that exact string. Assert the total call count drops to the two
        genuinely-distinct serializations left in the deflect path: the raw
        result itself (inside `execute_python_code`) and the outer summary_dict
        response wrapper — not a third pass re-deriving the same raw content."""
        import ot.executor.runner as runner

        call_count = 0
        real_serialize = runner.serialize_result

        def _counting_serialize(value: object, fmt: str) -> str:
            nonlocal call_count
            call_count += 1
            return real_serialize(value, fmt)

        monkeypatch.setattr(runner, "serialize_result", _counting_serialize)

        cmd = "__force_context__ = True\n{'a': list(range(50))}\n"
        result = await execute_command(cmd)
        assert result.success
        assert call_count == 2


# =============================================================================
# D3 — Execution timeout
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
class TestExecutionTimeout:
    """D3: a tool call exceeding the timeout raises a clean failure, not a hang."""

    async def test_timeout_produces_clean_failure(self, monkeypatch) -> None:
        import asyncio
        import threading

        import ot.executor.runner as runner
        from ot.executor.admission import execution_work_state

        monkeypatch.setattr(runner, "_TOOL_EXECUTION_TIMEOUT_SECS", 0.2)
        release = threading.Event()

        def _slow(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
            release.wait(timeout=5)
            return ("x", None, True, "json", False, None)

        # execute_command dispatches this on a worker thread; the wait_for timeout
        # must return a clean failure instead of blocking for the full sleep.
        monkeypatch.setattr(runner, "execute_python_code", _slow)
        try:
            result = await execute_command("1 + 1")
            assert not result.success
            assert result.error_type == "TimeoutError"
            assert "timed out" in result.result.lower()
            assert "may continue" in result.result.lower()
            assert execution_work_state()["active"] == 1
        finally:
            release.set()
            for _ in range(100):
                if execution_work_state()["active"] == 0:
                    break
                await asyncio.sleep(0.01)
            assert execution_work_state()["active"] == 0
