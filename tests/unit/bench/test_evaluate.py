"""Unit tests for benchmark evaluation module."""

import pytest

from ot_bench.harness.config import EvaluateConfig, HarnessConfig, TaskConfig
from ot_bench.harness.evaluate import (
    evaluate_deterministic,
    evaluate_regex,
    evaluate_task,
    resolve_evaluator,
)
from ot_bench.harness.metrics import TaskResult

# =============================================================================
# evaluate_regex tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestEvaluateRegex:
    """Tests for regex-based evaluation."""

    def test_regex_match_passes(self) -> None:
        """Regex pattern that matches should pass."""
        result = evaluate_regex("hello world", r"hello")
        assert result.passed is True
        assert result.score == 100
        assert "matched" in result.reason.lower()

    def test_regex_no_match_fails(self) -> None:
        """Regex pattern that doesn't match should fail."""
        result = evaluate_regex("hello world", r"goodbye")
        assert result.passed is False
        assert result.score == 0
        assert "did not match" in result.reason.lower()

    def test_regex_expect_no_match_passes(self) -> None:
        """When expect_match=False, no match should pass."""
        result = evaluate_regex("hello world", r"goodbye", expect_match=False)
        assert result.passed is True
        assert result.score == 100
        assert "correctly did not match" in result.reason.lower()

    def test_regex_expect_no_match_fails(self) -> None:
        """When expect_match=False, a match should fail."""
        result = evaluate_regex("hello world", r"hello", expect_match=False)
        assert result.passed is False
        assert result.score == 0
        assert "matched when it should not" in result.reason.lower()

    def test_regex_complex_pattern(self) -> None:
        """Test with a more complex regex pattern."""
        response = "The result is 42 items"
        result = evaluate_regex(response, r"\d+\s+items")
        assert result.passed is True
        assert "42 items" in (result.actual or "")

    def test_regex_multiline(self) -> None:
        """Test regex matching across lines."""
        response = "line1\nline2\nline3"
        result = evaluate_regex(response, r"line\d")
        assert result.passed is True

    def test_regex_case_sensitive(self) -> None:
        """Regex is case sensitive by default."""
        result = evaluate_regex("Hello World", r"hello")
        assert result.passed is False

    def test_regex_case_insensitive_pattern(self) -> None:
        """Use (?i) flag for case insensitive matching."""
        result = evaluate_regex("Hello World", r"(?i)hello")
        assert result.passed is True


# =============================================================================
# evaluate_deterministic tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestEvaluateDeterministic:
    """Tests for deterministic (contains) evaluation."""

    def test_string_contains_passes(self) -> None:
        """String that contains expected value should pass."""
        result = evaluate_deterministic("The answer is 42", "42")
        assert result.passed is True
        assert result.score == 100

    def test_string_not_contains_fails(self) -> None:
        """String that doesn't contain expected value should fail."""
        result = evaluate_deterministic("The answer is 42", "99")
        assert result.passed is False
        assert result.score == 0

    def test_integer_in_response(self) -> None:
        """Integer expected value should be found in response."""
        result = evaluate_deterministic("Result: 123", 123)
        assert result.passed is True

    def test_float_in_response(self) -> None:
        """Float expected value should be found in response."""
        result = evaluate_deterministic("Value: 3.14", 3.14)
        assert result.passed is True

    def test_boolean_true_in_response(self) -> None:
        """Boolean True should be found in response."""
        result = evaluate_deterministic("Status: True", True)
        assert result.passed is True

    def test_boolean_json_format(self) -> None:
        """Boolean in JSON format (lowercase) should be found."""
        result = evaluate_deterministic('{"success": true}', True)
        # Note: This checks for Python "True" not JSON "true"
        # The actual format depends on implementation
        assert result.passed is False  # Python True != JSON true

    def test_list_of_patterns_all_match(self) -> None:
        """All patterns in list should be found."""
        response = "apple, banana, cherry"
        result = evaluate_deterministic(response, ["apple", "banana"])
        assert result.passed is True
        assert "2 expected items found" in result.reason

    def test_list_of_patterns_some_missing(self) -> None:
        """Missing patterns should cause failure."""
        response = "apple, banana"
        result = evaluate_deterministic(response, ["apple", "orange"])
        assert result.passed is False
        assert "Missing" in result.reason

    def test_list_with_regex_pattern(self) -> None:
        """List containing regex dict patterns should work."""
        response = "User: john123"
        result = evaluate_deterministic(response, [{"regex": r"User: \w+"}])
        assert result.passed is True

    def test_numeric_list_as_output(self) -> None:
        """Pure numeric list should be checked as serialized JSON."""
        response = "Results: [1, 2, 3]"
        result = evaluate_deterministic(response, [1, 2, 3])
        assert result.passed is True

    def test_dict_expected_all_keys_found(self) -> None:
        """Dict expected with all keys present should pass."""
        response = '{"name": "test", "value": 42}'
        result = evaluate_deterministic(response, {"name": "test", "value": 42})
        # Exact dict match or keys check
        assert result.passed is True

    def test_dict_expected_missing_keys(self) -> None:
        """Dict expected with missing keys should fail."""
        response = '{"name": "test"}'
        result = evaluate_deterministic(response, {"name": "test", "missing": "value"})
        assert result.passed is False
        assert "Missing keys" in result.reason

    def test_expect_error_pattern_matches(self) -> None:
        """When expect_error=True and error pattern matches."""
        response = "Error: Something went wrong"
        result = evaluate_deterministic(response, ["Error"], expect_error=True)
        assert result.passed is True
        assert "Error returned" in result.reason

    def test_expect_error_pattern_not_matches(self) -> None:
        """When expect_error=True and error pattern doesn't match (LLM fixed it)."""
        response = "Success: Operation completed"
        result = evaluate_deterministic(response, ["Error"], expect_error=True)
        assert result.passed is True
        assert "fixed" in result.reason.lower()


# =============================================================================
# resolve_evaluator tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestResolveEvaluator:
    """Tests for evaluator resolution."""

    def test_no_evaluate_config(self) -> None:
        """Task without evaluate returns None."""
        task = TaskConfig(name="test", prompt="test prompt")
        config = HarnessConfig()
        result = resolve_evaluator(task, config)
        assert result is None

    def test_inline_evaluate_config(self) -> None:
        """Inline EvaluateConfig is returned directly."""
        eval_config = EvaluateConfig(expected="test")
        task = TaskConfig(name="test", prompt="test prompt", evaluate=eval_config)
        config = HarnessConfig()
        result = resolve_evaluator(task, config)
        assert result is eval_config

    def test_named_evaluator_found(self) -> None:
        """Named evaluator is resolved from harness config."""
        eval_config = EvaluateConfig(regex=r"\d+")
        task = TaskConfig(name="test", prompt="test prompt", evaluate="my_evaluator")
        config = HarnessConfig(evaluators={"my_evaluator": eval_config})
        result = resolve_evaluator(task, config)
        assert result is eval_config

    def test_named_evaluator_not_found(self) -> None:
        """Unknown named evaluator returns None with warning."""
        task = TaskConfig(name="test", prompt="test prompt", evaluate="unknown")
        config = HarnessConfig()
        result = resolve_evaluator(task, config)
        assert result is None


# =============================================================================
# evaluate_task tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestEvaluateTask:
    """Tests for the main evaluate_task function."""

    def _make_task_result(self, response: str) -> TaskResult:
        """Helper to create a TaskResult for testing."""
        return TaskResult(
            name="test_task",
            server="test_server",
            model="test_model",
            prompt="test prompt",
            response=response,
            input_tokens=100,
            output_tokens=50,
            llm_calls=1,
            tool_calls=1,
            tools_used=["tool1"],
            duration_seconds=1.5,
            cost_usd=0.01,
        )

    def test_no_evaluation_configured(self) -> None:
        """Returns None when no evaluation is configured."""
        task = TaskConfig(name="test", prompt="test prompt")
        config = HarnessConfig()
        result = evaluate_task(self._make_task_result("response"), task, config)
        assert result is None

    def test_routes_to_regex_evaluation(self) -> None:
        """Routes to regex evaluation when regex is set."""
        eval_config = EvaluateConfig(regex=r"hello")
        task = TaskConfig(name="test", prompt="test prompt", evaluate=eval_config)
        config = HarnessConfig()

        result = evaluate_task(self._make_task_result("hello world"), task, config)
        assert result is not None
        assert result.passed is True
        assert result.eval_type == "pass_fail"

    def test_routes_to_deterministic_evaluation(self) -> None:
        """Routes to deterministic evaluation when expected is set."""
        eval_config = EvaluateConfig(expected="hello")
        task = TaskConfig(name="test", prompt="test prompt", evaluate=eval_config)
        config = HarnessConfig()

        result = evaluate_task(self._make_task_result("hello world"), task, config)
        assert result is not None
        assert result.passed is True

    def test_regex_takes_priority_over_expected(self) -> None:
        """When both regex and expected are set, regex is used."""
        eval_config = EvaluateConfig(regex=r"goodbye", expected="hello")
        task = TaskConfig(name="test", prompt="test prompt", evaluate=eval_config)
        config = HarnessConfig()

        # Response has "hello" but not "goodbye"
        result = evaluate_task(self._make_task_result("hello world"), task, config)
        assert result is not None
        # Should fail because regex "goodbye" doesn't match
        assert result.passed is False

    def test_uses_named_evaluator(self) -> None:
        """Can use a named evaluator from config."""
        eval_config = EvaluateConfig(expected="success")
        task = TaskConfig(name="test", prompt="test prompt", evaluate="check_success")
        config = HarnessConfig(evaluators={"check_success": eval_config})

        result = evaluate_task(
            self._make_task_result("Operation success"), task, config
        )
        assert result is not None
        assert result.passed is True


# =============================================================================
# Integration tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestEvaluationIntegration:
    """Integration tests for evaluation scenarios."""

    def test_yaml_style_output_evaluation(self) -> None:
        """Test evaluation of YAML-style tool output."""
        response = """registry:
  status: ok
  tool_count: 43"""
        result = evaluate_regex(response, r"(registry|status)[\":].*ok")
        assert result.passed is True

    def test_json_style_output_evaluation(self) -> None:
        """Test evaluation of JSON-style tool output."""
        response = '{"registry": {"status": "ok", "tool_count": 43}}'
        result = evaluate_regex(response, r"(registry|status)[\":].*ok")
        assert result.passed is True

    def test_namespaced_tool_pattern(self) -> None:
        """Test matching namespaced tool names like brave.search."""
        response = """- brave.search
- info.tools
- demo.foo"""
        result = evaluate_regex(response, r"[a-z]+\.[a-z_]+")
        assert result.passed is True

    def test_evaluation_result_structure(self) -> None:
        """Test that EvaluationResult has all expected fields."""
        result = evaluate_regex("test", r"test")
        assert hasattr(result, "score")
        assert hasattr(result, "reason")
        assert hasattr(result, "eval_type")
        assert hasattr(result, "passed")
        assert hasattr(result, "expected")
        assert hasattr(result, "actual")
        assert result.eval_type == "pass_fail"
