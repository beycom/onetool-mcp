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

    def test_discovers_result_with_trial_metadata(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "task-one" / "codex-skills-smoke-onetool-mcp" / "rep-001"
        trial_dir.mkdir(parents=True)
        (trial_dir / "ot-harness-trial.json").write_text(
            json.dumps(
                {
                    "task_id": "task-one",
                    "variant_id": "codex-skills-smoke-onetool-mcp",
                    "repetition": 1,
                    "variant_metadata": {
                        "variant_id": "codex-skills-smoke-onetool-mcp",
                        "skills_hash": "a" * 64,
                        "mcp": {
                            "server_name": "onetool",
                            "transport": "http",
                            "url": "http://host.docker.internal:8768/mcp",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "verifier": {"passed": True, "score": 1.0},
                    "total_tokens": 123,
                    "total_cost": 0.04,
                }
            ),
            encoding="utf-8",
        )

        results = discover_results(tmp_path)

        assert len(results) == 1
        assert results[0].task_id == "task-one"
        assert results[0].variant_id == "codex-skills-smoke-onetool-mcp"
        assert results[0].tokens == 123
        assert results[0].cost_usd == 0.04

    def test_discovers_harbor_job_level_result(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "task-one" / "codex-skills-smoke-onetool-mcp" / "rep-001"
        trial_dir.mkdir(parents=True)
        (trial_dir / "ot-harness-trial.json").write_text(
            json.dumps(
                {
                    "task_id": "task-one",
                    "variant_id": "codex-skills-smoke-onetool-mcp",
                    "repetition": 1,
                    "variant_metadata": {
                        "variant_id": "codex-skills-smoke-onetool-mcp",
                        "skills_hash": "a" * 64,
                        "mcp": {
                            "server_name": "onetool",
                            "transport": "http",
                            "url": "http://host.docker.internal:8768/mcp",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "started_at": "2026-05-29T17:28:48.789985",
                    "finished_at": "2026-05-29T17:34:16.521377",
                    "n_total_trials": 1,
                    "stats": {
                        "n_completed_trials": 1,
                        "evals": {
                            "codex__gpt-5.2__terminal-bench": {
                                "metrics": [{"mean": 1.0}]
                            }
                        },
                        "n_input_tokens": 535066,
                        "n_output_tokens": 6409,
                        "cost_usd": 0.2555763,
                    },
                }
            ),
            encoding="utf-8",
        )

        results = discover_results(tmp_path)

        assert len(results) == 1
        assert results[0].task_id == "task-one"
        assert results[0].variant_id == "codex-skills-smoke-onetool-mcp"
        assert results[0].accuracy_status == "pass"
        assert results[0].score == 1.0
        assert results[0].tokens == 541475
        assert results[0].cost_usd == 0.2555763
        assert results[0].wall_time_seconds is not None

    def test_discovers_harbor_trial_level_result_once(self, tmp_path: Path) -> None:
        trial_dir = tmp_path / "task-one" / "codex-skills-smoke-onetool-mcp" / "rep-001"
        run_dir = trial_dir / "harbor-run"
        result_dir = run_dir / "fix-git__abc123"
        result_dir.mkdir(parents=True)
        (trial_dir / "ot-harness-trial.json").write_text(
            json.dumps(
                {
                    "task_id": "task-one",
                    "variant_id": "codex-skills-smoke-onetool-mcp",
                    "repetition": 1,
                    "variant_metadata": {
                        "variant_id": "codex-skills-smoke-onetool-mcp",
                        "mcp": {
                            "server_name": "onetool",
                            "transport": "http",
                            "url": "http://host.docker.internal:8768/mcp",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "result.json").write_text(
            json.dumps({"n_total_trials": 1, "stats": {"n_completed_trials": 1}}),
            encoding="utf-8",
        )
        (result_dir / "result.json").write_text(
            json.dumps(
                {
                    "task_id": {
                        "git_url": "https://github.com/laude-institute/terminal-bench-2.git",
                        "path": "fix-git",
                    },
                    "agent_result": {
                        "n_input_tokens": 535066,
                        "n_output_tokens": 6409,
                        "cost_usd": 0.2555763,
                    },
                    "verifier_result": {"rewards": {"reward": 1.0}},
                    "started_at": "2026-05-29T07:28:50.469851Z",
                    "finished_at": "2026-05-29T07:34:16.516775Z",
                }
            ),
            encoding="utf-8",
        )

        results = discover_results(tmp_path)

        assert len(results) == 1
        assert results[0].task_id == "task-one"
        assert results[0].variant_id == "codex-skills-smoke-onetool-mcp"
        assert results[0].accuracy_status == "pass"
        assert results[0].tokens == 541475
        assert results[0].cost_usd == 0.2555763
