"""Integration tests for context metrics and multi-prompt tasks.

These tests verify the end-to-end integration of per-call metrics tracking,
multi-prompt task execution, and CSV export without making actual LLM API calls.
"""

import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ot_bench.harness.csv_writer import write_results_csv
from ot_bench.harness.metrics import LLMCallMetrics, ScenarioResult, TaskResult
from ot_bench.harness.runner import split_prompts


@pytest.mark.unit
@pytest.mark.bench
class TestContextMetricsUnit:
    """Unit tests for context metrics and CSV export."""

    def test_task_result_with_metrics_to_csv(self, tmp_path: Path) -> None:
        """Verify CSV export includes base_context and context_growth_avg."""
        # Create task results with per-call metrics
        onetool_metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=5000,
                output_tokens=500,
                tool_calls_made=1,
                cumulative_input=5000,
                latency_ms=1200,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=6000,
                output_tokens=200,
                tool_calls_made=0,
                cumulative_input=11000,
                latency_ms=800,
            ),
        ]

        mcp_metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=5000,
                output_tokens=300,
                tool_calls_made=1,
                cumulative_input=5000,
                latency_ms=600,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=5800,
                output_tokens=250,
                tool_calls_made=1,
                cumulative_input=10800,
                latency_ms=500,
            ),
            LLMCallMetrics(
                call_number=3,
                input_tokens=6500,
                output_tokens=200,
                tool_calls_made=1,
                cumulative_input=17300,
                latency_ms=400,
            ),
            LLMCallMetrics(
                call_number=4,
                input_tokens=7200,
                output_tokens=150,
                tool_calls_made=0,
                cumulative_input=24500,
                latency_ms=350,
            ),
        ]

        onetool_task = TaskResult(
            name="version-check-onetool",
            server="onetool",
            model="test-model",
            prompt="Check npm versions",
            response="express: 5.0.0",
            input_tokens=11000,
            output_tokens=700,
            llm_calls=2,
            tool_calls=1,
            tools_used=["run"],
            duration_seconds=3.5,
            cost_usd=0.015,
            llm_call_metrics=onetool_metrics,
        )

        mcp_task = TaskResult(
            name="version-check-mcp",
            server="multiple-mcp",
            model="test-model",
            prompt="Check npm versions",
            response="express: 5.0.0",
            input_tokens=24500,
            output_tokens=900,
            llm_calls=4,
            tool_calls=3,
            tools_used=["check_npm", "check_pypi", "check_go"],
            duration_seconds=8.2,
            cost_usd=0.035,
            llm_call_metrics=mcp_metrics,
        )

        scenario = ScenarioResult(
            name="compare",
            model="test-model",
            tasks=[onetool_task, mcp_task],
        )

        # Export to CSV
        csv_path = write_results_csv([scenario], output_dir=tmp_path)

        # Verify CSV content
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have 2 rows
        assert len(rows) == 2

        # Verify onetool task
        onetool_row = rows[0]
        assert onetool_row["task"] == "version-check-onetool"
        assert onetool_row["base_context"] == "5000"
        assert int(onetool_row["llm_calls"]) == 2

        # Verify mcp task
        mcp_row = rows[1]
        assert mcp_row["task"] == "version-check-mcp"
        assert mcp_row["base_context"] == "5000"
        assert int(mcp_row["llm_calls"]) == 4

        # Verify context growth calculation
        onetool_growth = float(onetool_row["context_growth_avg"])
        mcp_growth = float(mcp_row["context_growth_avg"])
        # onetool: (6000-5000)/1 = 1000
        # mcp: ((5800-5000) + (6500-5800) + (7200-6500))/3 = 733
        assert 900 <= onetool_growth <= 1100
        assert 600 <= mcp_growth <= 850

    def test_context_efficiency_calculation(self) -> None:
        """Verify base_context and context_growth_avg calculations."""
        metrics = [
            LLMCallMetrics(
                call_number=1,
                input_tokens=1000,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=1000,
                latency_ms=200,
            ),
            LLMCallMetrics(
                call_number=2,
                input_tokens=1200,
                output_tokens=100,
                tool_calls_made=1,
                cumulative_input=2200,
                latency_ms=200,
            ),
            LLMCallMetrics(
                call_number=3,
                input_tokens=1400,
                output_tokens=100,
                tool_calls_made=0,
                cumulative_input=3600,
                latency_ms=200,
            ),
        ]

        task = TaskResult(
            name="test",
            server="test",
            model="test",
            prompt="test",
            response="test",
            input_tokens=3600,
            output_tokens=300,
            llm_calls=3,
            tool_calls=2,
            tools_used=["tool1"],
            duration_seconds=1.0,
            cost_usd=0.01,
            llm_call_metrics=metrics,
        )

        # base_context = first call's input tokens
        assert task.base_context == 1000

        # context_growth_avg = average of (call2-call1, call3-call2)
        # = ((1200-1000) + (1400-1200)) / 2 = (200 + 200) / 2 = 200
        assert task.context_growth_avg == 200.0


@pytest.mark.integration
@pytest.mark.bench
class TestMultiPromptIntegration:
    """Integration tests for multi-prompt task execution."""

    def test_split_prompts_integration(self) -> None:
        """Verify split_prompts works with realistic multi-prompt YAML content."""
        # Simulating what a user might write in YAML
        prompt = """__ot
```python
npm = check_npm_versions(dependencies={"express": "4.0.0"})
```
Return only latest versions.
---PROMPT---
__ot
```python
pypi = check_pypi_versions(dependencies={"requests": "2.0.0"})
```
Return only latest versions.
---PROMPT---
Now combine all the results and list them as a markdown table with columns:
| Package | Current | Latest |"""

        prompts = split_prompts(prompt)

        assert len(prompts) == 3
        assert "check_npm_versions" in prompts[0]
        assert "check_pypi_versions" in prompts[1]
        assert "markdown table" in prompts[2]

    def test_multi_prompt_metrics_accumulation(self) -> None:
        """Verify metrics would accumulate correctly across prompts.

        This tests the data structure expectations - actual runner behavior
        would be tested with mocked LLM calls in a more comprehensive test.
        """
        # Simulate what the runner would produce for a 3-prompt task
        # Each prompt completes its agentic loop, metrics accumulate
        metrics = [
            # Prompt 1: initial context + response
            LLMCallMetrics(
                call_number=1,
                input_tokens=3000,
                output_tokens=200,
                tool_calls_made=1,
                cumulative_input=3000,
                latency_ms=800,
            ),
            # Prompt 1: tool result + response
            LLMCallMetrics(
                call_number=2,
                input_tokens=3500,
                output_tokens=150,
                tool_calls_made=0,
                cumulative_input=6500,
                latency_ms=600,
            ),
            # Prompt 2: accumulated history + new prompt
            LLMCallMetrics(
                call_number=3,
                input_tokens=4000,
                output_tokens=250,
                tool_calls_made=1,
                cumulative_input=10500,
                latency_ms=900,
            ),
            # Prompt 2: tool result + response
            LLMCallMetrics(
                call_number=4,
                input_tokens=4600,
                output_tokens=180,
                tool_calls_made=0,
                cumulative_input=15100,
                latency_ms=700,
            ),
            # Prompt 3: full history + summary prompt
            LLMCallMetrics(
                call_number=5,
                input_tokens=5200,
                output_tokens=400,
                tool_calls_made=0,
                cumulative_input=20300,
                latency_ms=1100,
            ),
        ]

        task = TaskResult(
            name="multi-prompt-test",
            server="onetool",
            model="test",
            prompt="Multi-prompt task",
            response="Final summary table",
            input_tokens=20300,
            output_tokens=1180,
            llm_calls=5,
            tool_calls=2,
            tools_used=["run"],
            duration_seconds=5.0,
            cost_usd=0.025,
            llm_call_metrics=metrics,
        )

        # Verify the task captures expected patterns
        assert task.llm_calls == 5
        assert task.base_context == 3000
        assert len(task.llm_call_metrics) == 5

        # Cumulative input should grow with each call
        cumulatives = [m.cumulative_input for m in task.llm_call_metrics]
        assert cumulatives == [3000, 6500, 10500, 15100, 20300]

        # Context growth should reflect the pattern
        growth = task.context_growth_avg
        # Average of (500, 500, 600, 600) = 550
        assert 500 <= growth <= 600

    def test_to_dict_preserves_multi_call_structure(self) -> None:
        """Verify to_dict correctly serializes multi-call metrics."""
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

        task = TaskResult(
            name="test",
            server="test",
            model="test",
            prompt="test",
            response="test",
            input_tokens=2500,
            output_tokens=250,
            llm_calls=2,
            tool_calls=1,
            tools_used=["tool1"],
            duration_seconds=1.0,
            cost_usd=0.01,
            llm_call_metrics=metrics,
        )

        data = task.to_dict()

        # Verify structure
        assert "llm_call_metrics" in data
        assert len(data["llm_call_metrics"]) == 2

        # Verify first call
        call1 = data["llm_call_metrics"][0]
        assert call1["call_number"] == 1
        assert call1["input_tokens"] == 1000
        assert call1["cumulative_input"] == 1000

        # Verify second call
        call2 = data["llm_call_metrics"][1]
        assert call2["call_number"] == 2
        assert call2["input_tokens"] == 1500
        assert call2["cumulative_input"] == 2500
