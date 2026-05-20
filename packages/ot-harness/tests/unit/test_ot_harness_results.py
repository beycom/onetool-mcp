from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from ot_harness.results import (
    aggregate_by_variant,
    discover_results,
    normalize_result,
    render_markdown_report,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.bench
class TestResults:
    def test_normalizes_successful_trial(self, tmp_path: Path) -> None:
        path = tmp_path / "result.json"
        result = normalize_result(
            {
                "task_id": "task-one",
                "variant_id": "codex-base",
                "repetition": 2,
                "verifier": {"passed": True, "score": 1.0},
                "wall_time_seconds": 12.5,
                "tokens": 1000,
                "cost_usd": 0.25,
                "tool_calls": 3,
                "onetool_calls": 0,
                "final_output": "done",
                "logs_path": "logs/run.log",
            },
            path,
        )

        assert result.accuracy_status == "pass"
        assert result.score == 1.0
        assert result.telemetry_status == "complete"
        assert result.result_json_path == path

    def test_marks_missing_verifier_as_invalid(self, tmp_path: Path) -> None:
        result = normalize_result(
            {"task_id": "task-one", "variant_id": "codex-base", "repetition": 1},
            tmp_path / "result.json",
        )

        assert result.accuracy_status == "invalid"

    def test_marks_missing_token_or_cost_as_partial(self, tmp_path: Path) -> None:
        result = normalize_result(
            {
                "task_id": "task-one",
                "variant_id": "codex-base",
                "verifier": {"passed": True, "score": 1.0},
            },
            tmp_path / "result.json",
        )

        assert result.tokens is None
        assert result.cost_usd is None
        assert result.telemetry_status == "partial"

    def test_discovers_and_aggregates_results(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "result.json").write_text(
            json.dumps(
                {
                    "task_id": "task-one",
                    "variant_id": "codex-base",
                    "verifier": {"passed": True, "score": 1.0},
                    "wall_time_seconds": 2,
                    "tokens": 10,
                    "cost_usd": 0.01,
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "result.json").write_text(
            json.dumps({"task_id": "task-one", "variant_id": "codex-onetool-mcp"}),
            encoding="utf-8",
        )

        results = discover_results(tmp_path)
        aggregates = aggregate_by_variant(results)
        report = render_markdown_report(results)

        assert len(results) == 2
        assert aggregates["codex-base"]["pass_rate"] == 1.0
        assert aggregates["codex-onetool-mcp"]["invalid_rate"] == 1.0
        assert "| codex-base |" in report
