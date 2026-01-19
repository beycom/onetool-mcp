"""Unit tests for CSV writer module."""

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ot_bench.harness.csv_writer import write_results_csv
from ot_bench.harness.metrics import (
    EvaluationResult,
    LLMCallMetrics,
    ScenarioResult,
    TaskResult,
)

# =============================================================================
# CSV Writer tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.bench
class TestCSVWriter:
    """Tests for write_results_csv function."""

    def _make_task_result(
        self,
        name: str = "test_task",
        server: str | list[str] | None = "test_server",
        input_tokens: int = 1000,
        output_tokens: int = 100,
        llm_call_metrics: list[LLMCallMetrics] | None = None,
        evaluation: EvaluationResult | None = None,
        error: str | None = None,
    ) -> TaskResult:
        """Helper to create a TaskResult for testing."""
        return TaskResult(
            name=name,
            server=server,
            model="test_model",
            prompt="test prompt",
            response="test response",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            llm_calls=len(llm_call_metrics) if llm_call_metrics else 1,
            tool_calls=1,
            tools_used=["tool1"],
            duration_seconds=1.5,
            cost_usd=0.01,
            llm_call_metrics=llm_call_metrics or [],
            evaluation=evaluation,
            error=error,
        )

    def _make_scenario(
        self, name: str = "test_scenario", tasks: list[TaskResult] | None = None
    ) -> ScenarioResult:
        """Helper to create a ScenarioResult for testing."""
        return ScenarioResult(
            name=name,
            model="test_model",
            tasks=tasks or [],
            timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

    def test_writes_csv_file(self, tmp_path: Path) -> None:
        """CSV file is created in output directory."""
        scenario = self._make_scenario(tasks=[self._make_task_result()])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        assert output_path.exists()
        assert output_path.suffix == ".csv"
        assert output_path.parent == tmp_path

    def test_csv_has_basic_headers(self, tmp_path: Path) -> None:
        """CSV has expected basic headers."""
        scenario = self._make_scenario(tasks=[self._make_task_result()])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            assert headers is not None
            assert "scenario" in headers
            assert "task" in headers
            assert "model" in headers
            assert "server" in headers
            assert "result" in headers
            assert "total_input" in headers
            assert "total_output" in headers
            assert "base_context" in headers
            assert "context_growth_avg" in headers

    def test_csv_data_values(self, tmp_path: Path) -> None:
        """CSV data contains expected values."""
        task = self._make_task_result(
            name="my_task",
            server="my_server",
            input_tokens=1500,
            output_tokens=200,
        )
        scenario = self._make_scenario(name="my_scenario", tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            row = rows[0]
            assert row["scenario"] == "my_scenario"
            assert row["task"] == "my_task"
            assert row["server"] == "my_server"
            assert row["total_input"] == "1500"
            assert row["total_output"] == "200"

    def test_csv_with_list_server(self, tmp_path: Path) -> None:
        """Server list is comma-separated in CSV."""
        task = self._make_task_result(server=["server1", "server2"])
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["server"] == "server1,server2"

    def test_csv_with_null_server(self, tmp_path: Path) -> None:
        """Null server shows as dash."""
        task = self._make_task_result(server=None)
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["server"] == "-"

    def test_csv_result_pass(self, tmp_path: Path) -> None:
        """PASS result is shown correctly."""
        evaluation = EvaluationResult(
            score=100, reason="ok", eval_type="pass_fail", passed=True
        )
        task = self._make_task_result(evaluation=evaluation)
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["result"] == "PASS"

    def test_csv_result_fail(self, tmp_path: Path) -> None:
        """FAIL result is shown correctly."""
        evaluation = EvaluationResult(
            score=0, reason="failed", eval_type="pass_fail", passed=False
        )
        task = self._make_task_result(evaluation=evaluation)
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["result"] == "FAIL"

    def test_csv_result_scored(self, tmp_path: Path) -> None:
        """Scored result shows numeric score."""
        evaluation = EvaluationResult(score=85, reason="good", eval_type="scored")
        task = self._make_task_result(evaluation=evaluation)
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["result"] == "85"

    def test_csv_result_error(self, tmp_path: Path) -> None:
        """ERROR is shown for tasks with errors."""
        task = self._make_task_result(error="Something went wrong")
        scenario = self._make_scenario(tasks=[task])
        output_path = write_results_csv([scenario], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row["result"] == "ERROR"

    def test_csv_creates_output_directory(self, tmp_path: Path) -> None:
        """Output directory is created if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "dir"
        scenario = self._make_scenario(tasks=[self._make_task_result()])
        output_path = write_results_csv([scenario], output_dir=nested_dir)

        assert nested_dir.exists()
        assert output_path.exists()

    def test_csv_multiple_scenarios(self, tmp_path: Path) -> None:
        """Multiple scenarios produce multiple rows."""
        task1 = self._make_task_result(name="task1")
        task2 = self._make_task_result(name="task2")
        scenario1 = self._make_scenario(name="scenario1", tasks=[task1])
        scenario2 = self._make_scenario(name="scenario2", tasks=[task2])
        output_path = write_results_csv([scenario1, scenario2], output_dir=tmp_path)

        with output_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["scenario"] == "scenario1"
            assert rows[1]["scenario"] == "scenario2"
