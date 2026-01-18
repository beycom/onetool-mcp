"""Evaluation module for benchmark responses.

Supports three evaluation methods:
1. Regex - Pattern matching with expect_match flag
2. Deterministic - Contains checks for strings, lists, dicts, scalars
3. LLM-as-judge - AI-based evaluation with custom prompts

Usage:
    The main entry point is `evaluate_task()` which routes to the appropriate
    evaluation method based on the EvaluateConfig.

    Evaluation is called AFTER task completion to ensure task duration excludes
    evaluation time. The runner handles this in the task loop.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from loguru import logger
from openai import OpenAI

from ot_bench.harness.metrics import EvaluationResult, TaskResult
from ot_bench.secrets import get_bench_secret

if TYPE_CHECKING:
    from ot_bench.harness.config import EvaluateConfig, HarnessConfig, TaskConfig


# =============================================================================
# Helper Functions
# =============================================================================


def _normalize_value(value: Any) -> str:
    """Convert a value to string for comparison."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        # Return both Python and JSON representations for matching
        return str(value)  # "True" or "False"
    return json.dumps(value, sort_keys=True)


def _check_pattern(pattern: Any, response: str) -> bool:
    """Check if a pattern matches the response.

    Args:
        pattern: String, dict with 'regex' key, or other value
        response: Response text to check

    Returns:
        True if pattern matches
    """
    if isinstance(pattern, dict) and "regex" in pattern:
        return bool(re.search(pattern["regex"], response))
    elif isinstance(pattern, str):
        return pattern in response
    else:
        # For numbers, bools, etc - convert to string and check contains
        return _normalize_value(pattern) in response


def _list_is_expected_output(lst: list[Any]) -> bool:
    """Check if list represents an expected output (not patterns to check).

    Returns True for lists like [97, 101] or [True, False, True] that should
    be checked as serialized JSON. Returns False for lists with strings or
    regex patterns that should be checked individually.
    """
    # Lists with any strings are treated as patterns to check
    if any(isinstance(item, str) for item in lst):
        return False
    # Lists with regex dicts are patterns
    if any(isinstance(item, dict) and "regex" in item for item in lst):
        return False
    # Pure numeric/boolean lists are expected outputs
    return all(isinstance(item, (int, float, bool)) or item is None for item in lst)


def _truncate(s: str, max_len: int = 100) -> str:
    """Truncate string for display."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def _find_actual_match(
    response: str, pattern: str, max_context: int = 50
) -> str | None:
    """Find where a pattern appears in response and extract context."""
    idx = response.find(pattern)
    if idx == -1:
        return None
    start = max(0, idx - 10)
    end = min(len(response), idx + len(pattern) + max_context)
    return response[start:end]


# =============================================================================
# Evaluation Methods
# =============================================================================


def evaluate_deterministic(
    response: str,
    expected: str | list[Any] | dict[str, Any] | int | float | bool,
    expect_error: bool = False,
) -> EvaluationResult:
    """Evaluate response against expected value(s) deterministically.

    Args:
        response: The response text to evaluate
        expected: Expected value(s) - string, list, dict, or scalar
        expect_error: If True, test expects an error. Failure to match means LLM fixed the code.

    Returns:
        EvaluationResult with pass/fail status and expected/actual values
    """
    if isinstance(expected, list):
        # For lists of pure numbers/booleans, check if the serialized list appears
        if _list_is_expected_output(expected):
            # Try multiple representations
            representations = [
                json.dumps(expected),  # [true, false, ...]
                str(expected),  # [True, False, ...] - Python repr
                repr(expected),  # [True, False, ...]
            ]
            for rep in representations:
                if rep in response:
                    actual = _find_actual_match(response, rep)
                    return EvaluationResult(
                        score=100,
                        reason="Expected list found",
                        eval_type="pass_fail",
                        passed=True,
                        expected=_truncate(rep),
                        actual=actual,
                    )
            return EvaluationResult(
                score=0,
                reason="Expected list not found",
                eval_type="pass_fail",
                passed=False,
                expected=_truncate(representations[0]),
                actual=_truncate(response, 200),
            )

        # For lists with patterns (regex dicts), check each item
        missing = []
        found = []
        for item in expected:
            if _check_pattern(item, response):
                if isinstance(item, dict) and "regex" in item:
                    found.append(f"regex:{item['regex'][:30]}")
                else:
                    found.append(str(item)[:30])
            else:
                if isinstance(item, dict) and "regex" in item:
                    missing.append(f"regex:{item['regex']}")
                else:
                    missing.append(str(item))

        if missing:
            # When expect_error=True and LLM fixed the code (no error patterns matched),
            # this is a PASS - demonstrates LLM's ability to fix small errors
            if expect_error:
                return EvaluationResult(
                    score=100,
                    reason="LLM fixed the error",
                    eval_type="pass_fail",
                    passed=True,
                    expected="error or fix",
                    actual="LLM fixed code",
                )
            reason = (
                f"Missing: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}"
            )
            return EvaluationResult(
                score=0,
                reason=reason,
                eval_type="pass_fail",
                passed=False,
                expected=_truncate(str(expected)),
                actual=f"Found: {', '.join(found[:3])}" if found else "None matched",
            )
        # When expect_error=True and error patterns matched, the error was returned
        reason = (
            "Error returned"
            if expect_error
            else f"All {len(expected)} expected items found"
        )
        actual = (
            "Error in response"
            if expect_error
            else f"All {len(expected)} patterns matched"
        )
        return EvaluationResult(
            score=100,
            reason=reason,
            eval_type="pass_fail",
            passed=True,
            expected="error or fix" if expect_error else _truncate(str(expected)),
            actual=actual,
        )

    elif isinstance(expected, dict):
        # Check if dict is in response (JSON serialized)
        expected_str = _normalize_value(expected)
        if expected_str in response:
            actual = _find_actual_match(response, expected_str)
            return EvaluationResult(
                score=100,
                reason="Expected dict found in response",
                eval_type="pass_fail",
                passed=True,
                expected=_truncate(expected_str),
                actual=actual,
            )
        # Try checking each key-value pair
        missing = []
        found_keys = []
        for key, _value in expected.items():
            pattern = f'"{key}"' if isinstance(key, str) else str(key)
            if pattern not in response:
                missing.append(key)
            else:
                found_keys.append(key)
        if missing:
            return EvaluationResult(
                score=0,
                reason=f"Missing keys: {', '.join(str(k) for k in missing[:3])}",
                eval_type="pass_fail",
                passed=False,
                expected=_truncate(expected_str),
                actual=f"Found keys: {', '.join(str(k) for k in found_keys[:3])}"
                if found_keys
                else "No keys found",
            )
        return EvaluationResult(
            score=100,
            reason="All expected keys found",
            eval_type="pass_fail",
            passed=True,
            expected=_truncate(expected_str),
            actual=f"All {len(expected)} keys present",
        )

    else:
        # String or scalar - simple contains check
        expected_str = _normalize_value(expected)
        if expected_str in response:
            actual = _find_actual_match(response, expected_str)
            return EvaluationResult(
                score=100,
                reason="Expected value found",
                eval_type="pass_fail",
                passed=True,
                expected=_truncate(expected_str),
                actual=actual,
            )
        return EvaluationResult(
            score=0,
            reason="Expected value not found in response",
            eval_type="pass_fail",
            passed=False,
            expected=_truncate(expected_str),
            actual=_truncate(response, 200),
        )


def evaluate_llm(
    response: str,
    config: EvaluateConfig,
    expected: Any = None,
) -> EvaluationResult:
    """Evaluate response using LLM-as-judge.

    Args:
        response: The response text to evaluate
        config: Evaluation config with prompt and model
        expected: Optional expected value for substitution

    Returns:
        EvaluationResult with score (0-100) and reason
    """
    if not config.prompt:
        return EvaluationResult(
            score=0,
            reason="No evaluation prompt configured",
            eval_type="scored",
        )

    if not config.model:
        return EvaluationResult(
            score=0,
            reason="No evaluation model configured - set evaluator.model in YAML",
            eval_type="scored",
        )

    client = OpenAI(
        api_key=get_bench_secret("OPENAI_API_KEY"),
        base_url=get_bench_secret("OPENAI_BASE_URL"),
    )

    # Format the evaluation prompt
    prompt = config.prompt.replace("{response}", response)
    if expected is not None:
        expected_str = _normalize_value(expected)
        prompt = prompt.replace("{expected}", expected_str)

    try:
        llm_response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
        )

        content = llm_response.choices[0].message.content or ""

        # Strip markdown code blocks if present
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)

        # Try to parse JSON response
        brace_start = content.find("{")
        if brace_start != -1:
            depth = 0
            brace_end = -1
            for i, c in enumerate(content[brace_start:], brace_start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        brace_end = i + 1
                        break

            if brace_end > brace_start:
                json_str = content[brace_start:brace_end]
                try:
                    data = json.loads(json_str)
                    score = int(data.get("score") or 5)
                    reason = data.get("reason", "No reason provided")
                    if isinstance(reason, dict):
                        reason = json.dumps(reason)
                    return EvaluationResult(
                        score=score,
                        reason=str(reason),
                        eval_type="scored",
                    )
                except (json.JSONDecodeError, ValueError):
                    pass

        # Fallback: try to extract score from text (e.g., "7/10")
        score_match = re.search(r"(\d+)\s*/?\s*10", content)
        if score_match:
            # Scale from 0-10 to 0-100
            score = int(score_match.group(1)) * 10
            return EvaluationResult(
                score=score,
                reason=_truncate(content, 200),
                eval_type="scored",
            )

        logger.warning(f"Could not parse evaluation response: {content[:100]}")
        return EvaluationResult(
            score=5,
            reason="Could not parse evaluation response",
            eval_type="scored",
        )

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return EvaluationResult(
            score=0,
            reason=f"Evaluation error: {e}",
            eval_type="scored",
        )


# =============================================================================
# Evaluator Resolution and Task Evaluation
# =============================================================================


def resolve_evaluator(
    task: TaskConfig,
    harness_config: HarnessConfig,
) -> EvaluateConfig | None:
    """Resolve the evaluator config for a task.

    Args:
        task: The task configuration
        harness_config: The harness configuration with evaluators dict

    Returns:
        Resolved EvaluateConfig or None if no evaluation
    """
    if task.evaluate is None:
        return None

    if isinstance(task.evaluate, str):
        # Reference to named evaluator
        if task.evaluate in harness_config.evaluators:
            return harness_config.evaluators[task.evaluate]
        logger.warning(f"Unknown evaluator '{task.evaluate}', skipping evaluation")
        return None

    # Inline EvaluateConfig
    return task.evaluate


def evaluate_regex(
    response: str,
    pattern: str,
    expect_match: bool = True,
) -> EvaluationResult:
    """Evaluate response against a regex pattern.

    Args:
        response: The response text to evaluate
        pattern: Regex pattern to match
        expect_match: If True, pattern must match. If False, must NOT match.

    Returns:
        EvaluationResult with pass/fail status
    """
    match = re.search(pattern, response)

    if expect_match:
        if match:
            return EvaluationResult(
                score=100,
                reason="Regex pattern matched",
                eval_type="pass_fail",
                passed=True,
                expected=f"match: {_truncate(pattern, 50)}",
                actual=_truncate(match.group(0), 100),
            )
        return EvaluationResult(
            score=0,
            reason="Regex pattern did not match",
            eval_type="pass_fail",
            passed=False,
            expected=f"match: {_truncate(pattern, 50)}",
            actual=_truncate(response, 200),
        )
    else:
        # expect_match=False means pattern must NOT match
        if not match:
            return EvaluationResult(
                score=100,
                reason="Regex pattern correctly did not match",
                eval_type="pass_fail",
                passed=True,
                expected=f"no match: {_truncate(pattern, 50)}",
                actual="No match found",
            )
        return EvaluationResult(
            score=0,
            reason="Regex pattern matched when it should not",
            eval_type="pass_fail",
            passed=False,
            expected=f"no match: {_truncate(pattern, 50)}",
            actual=_truncate(match.group(0), 100),
        )


def evaluate_task(
    task_result: TaskResult,
    task: TaskConfig,
    harness_config: HarnessConfig,
) -> EvaluationResult | None:
    """Evaluate a task result.

    Args:
        task_result: The task result with response
        task: The task configuration
        harness_config: The harness configuration

    Returns:
        EvaluationResult or None if no evaluation configured
    """
    eval_config = resolve_evaluator(task, harness_config)

    if eval_config is None:
        return None

    # Regex evaluation if regex pattern is set
    if eval_config.regex is not None:
        return evaluate_regex(
            task_result.response,
            eval_config.regex,
            expect_match=eval_config.expect_match,
        )

    # Deterministic evaluation if expected is set
    if eval_config.expected is not None:
        return evaluate_deterministic(
            task_result.response,
            eval_config.expected,
            expect_error=eval_config.expect_error,
        )

    # LLM evaluation if prompt is set
    if eval_config.prompt:
        return evaluate_llm(task_result.response, eval_config)

    # No evaluation method configured
    return None
