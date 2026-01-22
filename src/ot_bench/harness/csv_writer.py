"""CSV export for benchmark results with per-call metrics."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ot.logging import LogSpan
from ot.paths import get_effective_cwd

if TYPE_CHECKING:
    from ot_bench.harness.metrics import ScenarioResult


def write_results_csv(
    results: list[ScenarioResult],
    output_dir: Path | str | None = None,
) -> Path:
    """Write benchmark results to CSV with per-call breakdown.

    Generates a CSV file with dynamic columns based on the maximum number
    of LLM calls across all tasks. Each task row includes scenario info,
    totals, and per-call metrics.

    Args:
        results: List of ScenarioResult objects to export.
        output_dir: Directory for output file (default: {cwd}/tmp/).

    Returns:
        Path to the generated CSV file.
    """
    if output_dir is None:
        output_dir = get_effective_cwd() / "tmp"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    output_path = output_dir / f"result-{timestamp}.csv"

    task_count = sum(len(s.tasks) for s in results)

    with LogSpan(span="bench.results.write", path=str(output_path), tasks=task_count):
        _write_csv_file(results, output_path)

    return output_path


def _write_csv_file(results: list[ScenarioResult], output_path: Path) -> None:
    """Write benchmark results to CSV file."""
    headers = [
        "scenario",
        "task",
        "model",
        "server",
        "result",
        "total_input",
        "total_output",
        "llm_calls",
        "tool_calls",
        "duration_s",
        "cost_usd",
        "base_context",
        "context_growth_avg",
    ]

    # Write CSV
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for scenario in results:
            for task in scenario.tasks:
                # Determine result value
                if task.error:
                    result_val = "ERROR"
                elif task.evaluation:
                    if task.evaluation.eval_type == "pass_fail":
                        result_val = "PASS" if task.evaluation.passed else "FAIL"
                    else:
                        result_val = str(task.evaluation.score)
                else:
                    result_val = "-"

                # Format server as comma-separated if list
                server_val = (
                    ",".join(task.server)
                    if isinstance(task.server, list)
                    else (task.server or "-")
                )

                row = [
                    scenario.name,
                    task.name,
                    task.model,
                    server_val,
                    result_val,
                    task.input_tokens,
                    task.output_tokens,
                    task.llm_calls,
                    task.tool_calls,
                    round(task.duration_seconds, 2),
                    round(task.cost_usd, 6),
                    task.base_context,
                    round(task.context_growth_avg, 1),
                ]

                writer.writerow(row)
