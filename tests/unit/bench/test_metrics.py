"""Unit tests for benchmark metrics module."""

import pytest

from bench.harness.metrics import LLMCallMetrics, TaskResult
from bench.harness.runner import split_prompts

# =============================================================================
# LLMCallMetrics tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestLLMCallMetrics:
    """Tests for LLMCallMetrics dataclass."""

    def test_create_metrics(self) -> None:
        """Basic creation of LLMCallMetrics."""
        metrics = LLMCallMetrics(
            call_number=1,
            input_tokens=1000,
            output_tokens=200,
            tool_calls_made=2,
            cumulative_input=1000,
            latency_ms=500,
        )
        assert metrics.call_number == 1
        assert metrics.input_tokens == 1000
        assert metrics.output_tokens == 200
        assert metrics.tool_calls_made == 2
        assert metrics.cumulative_input == 1000
        assert metrics.latency_ms == 500

    def test_metrics_cumulative_tracking(self) -> None:
        """Verify cumulative_input tracks across calls."""
        call1 = LLMCallMetrics(
            call_number=1,
            input_tokens=1000,
            output_tokens=100,
            tool_calls_made=1,
            cumulative_input=1000,
            latency_ms=300,
        )
        call2 = LLMCallMetrics(
            call_number=2,
            input_tokens=1500,
            output_tokens=150,
            tool_calls_made=1,
            cumulative_input=2500,  # 1000 + 1500
            latency_ms=400,
        )
        assert call2.cumulative_input == call1.cumulative_input + call2.input_tokens


# =============================================================================
# TaskResult helper methods tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestTaskResultHelpers:
    """Tests for TaskResult base_context and context_growth_avg helpers."""

    def _make_task_result(
        self, llm_call_metrics: list[LLMCallMetrics] | None = None
    ) -> TaskResult:
        """Helper to create a TaskResult for testing."""
        return TaskResult(
            name="test_task",
            server="test_server",
            model="test_model",
            prompt="test prompt",
            response="test response",
            input_tokens=100,
            output_tokens=50,
            llm_calls=1,
            tool_calls=1,
            tools_used=["tool1"],
            duration_seconds=1.5,
            cost_usd=0.01,
            llm_call_metrics=llm_call_metrics or [],
        )

    def test_base_context_empty_metrics(self) -> None:
        """base_context returns 0 when no metrics."""
        result = self._make_task_result()
        assert result.base_context == 0

    def test_base_context_with_metrics(self) -> None:
        """base_context returns first call's input tokens."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=1500,
                output_tokens=150,
                tool_calls_made=0,
                cumulative_input=2500,
                latency_ms=400,
            ),
        ]
        result = self._make_task_result(metrics)
        assert result.base_context == 1000

    def test_context_growth_avg_empty_metrics(self) -> None:
        """context_growth_avg returns 0 when no metrics."""
        result = self._make_task_result()
        assert result.context_growth_avg == 0.0

    def test_context_growth_avg_single_call(self) -> None:
        """context_growth_avg returns 0 for single call."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
        ]
        result = self._make_task_result(metrics)
        assert result.context_growth_avg == 0.0

    def test_context_growth_avg_multiple_calls(self) -> None:
        """context_growth_avg calculates average growth correctly."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=1500,
                output_tokens=150,
                tool_calls_made=1,
                cumulative_input=2500,
                latency_ms=400,
            ),
            LLMCallMetrics(
                call_number=3,
                input_tokens=2000,
                output_tokens=200,
                tool_calls_made=0,
                cumulative_input=4500,
                latency_ms=500,
            ),
        ]
        result = self._make_task_result(metrics)
        # Growth: call1->call2 = 500, call2->call3 = 500
        # Average = (500 + 500) / 2 = 500
        assert result.context_growth_avg == 500.0

    def test_to_dict_includes_llm_call_metrics(self) -> None:
        """to_dict includes llm_call_metrics when present."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=300,
            ),
        ]
        result = self._make_task_result(metrics)
        data = result.to_dict()
        assert "llm_call_metrics" in data
        assert len(data["llm_call_metrics"]) == 1
        assert data["llm_call_metrics"][0]["call_number"] == 1
        assert data["llm_call_metrics"][0]["input_tokens"] == 1000

    def test_to_dict_omits_empty_metrics(self) -> None:
        """to_dict omits llm_call_metrics when empty."""
        result = self._make_task_result()
        data = result.to_dict()
        assert "llm_call_metrics" not in data


# =============================================================================
# split_prompts tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestSplitPrompts:
    """Tests for split_prompts helper function."""

    def test_single_prompt_no_delimiter(self) -> None:
        """Single prompt without delimiter returns as-is."""
        result = split_prompts("Check npm version for express")
        assert result == ["Check npm version for express"]

    def test_empty_prompt(self) -> None:
        """Empty prompt returns list with single empty string."""
        result = split_prompts("")
        assert result == [""]

    def test_multiple_prompts(self) -> None:
        """Multiple prompts are split correctly."""
        prompt = """First prompt here
---PROMPT---
Second prompt here
---PROMPT---
Third prompt here"""
        result = split_prompts(prompt)
        assert len(result) == 3
        assert result[0] == "First prompt here"
        assert result[1] == "Second prompt here"
        assert result[2] == "Third prompt here"

    def test_whitespace_trimmed(self) -> None:
        """Whitespace is trimmed from each prompt."""
        prompt = """  First prompt
---PROMPT---
  Second prompt  """
        result = split_prompts(prompt)
        assert result[0] == "First prompt"
        assert result[1] == "Second prompt"

    def test_empty_segments_skipped(self) -> None:
        """Empty segments between delimiters are skipped."""
        prompt = """First prompt
---PROMPT---

---PROMPT---
Second prompt"""
        result = split_prompts(prompt)
        assert len(result) == 2
        assert result[0] == "First prompt"
        assert result[1] == "Second prompt"

    def test_multiline_prompts(self) -> None:
        """Multi-line prompts within segments are preserved."""
        prompt = """__ot
```python
npm = check_npm()
```
Return versions.
---PROMPT---
__ot
```python
other = check_other()
```
Return values."""
        result = split_prompts(prompt)
        assert len(result) == 2
        assert "```python" in result[0]
        assert "npm = check_npm()" in result[0]
        assert "other = check_other()" in result[1]
