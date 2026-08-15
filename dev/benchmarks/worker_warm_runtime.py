"""Repeatable pre-turn benchmark for the episodic worker app-server runtime."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
from pathlib import Path

from ottools._worker.app_server import benchmark_runtime_startup


def _codex_version() -> str:
    completed = subprocess.run(
        ["codex", "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (completed.stdout or completed.stderr).strip()


def main() -> None:
    """Run one cold and repeated warm thread-start probes and print JSON."""
    parser = argparse.ArgumentParser(
        description="Measure worker app-server startup without starting a model turn."
    )
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    project = args.project.resolve(strict=True)
    project_kind = (
        "onetool-mcp-worktree"
        if (project / "pyproject.toml").is_file()
        else "minimal-temporary-project"
    )
    measurements = benchmark_runtime_startup(
        cwd=str(project),
        iterations=args.iterations,
    )
    rows = [
        {
            "classification": item.classification,
            "initialization_seconds": round(item.initialization_seconds, 6),
            "first_event_seconds": round(item.first_event_seconds, 6),
            "thread_start_seconds": round(item.thread_start_seconds, 6),
            "pre_turn_seconds": round(item.pre_turn_seconds, 6),
        }
        for item in measurements
    ]
    cold = rows[0]
    warm_pre_turn = [row["pre_turn_seconds"] for row in rows[1:]]
    warm_median = statistics.median(warm_pre_turn)
    improvement = (
        0.0
        if cold["pre_turn_seconds"] == 0
        else 1.0 - warm_median / cold["pre_turn_seconds"]
    )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "platform": platform.platform(),
                "codex_version": _codex_version(),
                "project_kind": project_kind,
                "iterations": rows,
                "cold_pre_turn_seconds": cold["pre_turn_seconds"],
                "warm_median_pre_turn_seconds": round(warm_median, 6),
                "warm_improvement_fraction": round(improvement, 6),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
