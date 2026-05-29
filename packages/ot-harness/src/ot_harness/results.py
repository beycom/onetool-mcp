"""Normalize Harbor trial outputs and aggregate ot-harness reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any


@dataclass(frozen=True)
class TrialResult:
    """Normalized result for one Harbor trial."""

    task_id: str
    variant_id: str
    repetition: int
    accuracy_status: str
    score: float | None
    wall_time_seconds: float | None
    tokens: int | None
    cost_usd: float | None
    tool_calls: int | None
    onetool_calls: int | None
    final_output: str | None
    logs_path: Path | None
    result_json_path: Path

    @property
    def telemetry_status(self) -> str:
        """Return whether token and cost telemetry are complete."""
        if self.tokens is None or self.cost_usd is None:
            return "partial"
        return "complete"


def discover_results(run_output_dir: Path) -> list[TrialResult]:
    """Discover and normalize Harbor result JSON files below a run directory."""
    results: list[TrialResult] = []
    paths = sorted(path for path in run_output_dir.rglob("*.json") if path.name == "result.json")
    for path in paths:
        if path.name != "result.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if _is_harbor_job_summary(data) and _has_descendant_result(path, paths):
            continue
        if _looks_like_result(data):
            results.append(normalize_result(_with_trial_metadata(data, path), path))
    return results


def normalize_result(data: dict[str, Any], path: Path) -> TrialResult:
    """Normalize a Harbor result object into a stable trial result."""
    verifier = _first_present(data, "verifier", "verification", "verifier_output")
    score = _float_or_none(
        _first_present(
            data, "score", "reward", "accuracy", nested=(verifier, "score", "reward")
        )
    )
    if score is None:
        score = _harbor_job_score(data)
    if score is None:
        score = _harbor_trial_score(data)
    accuracy_status = _accuracy_status(data, verifier, score)
    stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
    agent_result = data.get("agent_result") if isinstance(data.get("agent_result"), dict) else {}
    tokens = _int_or_none(
        _first_present(data, "tokens", "token_count", "total_tokens")
    ) or _harbor_total_tokens(stats) or _harbor_total_tokens(agent_result)
    cost_usd = _float_or_none(
        _first_present(data, "cost_usd", "cost", "total_cost")
    )
    if cost_usd is None:
        cost_usd = _float_or_none(stats.get("cost_usd"))
    if cost_usd is None:
        cost_usd = _float_or_none(agent_result.get("cost_usd"))
    wall_time = _float_or_none(
        _first_present(data, "wall_time_seconds", "duration_seconds", "elapsed_seconds")
    )
    if wall_time is None:
        wall_time = _duration_seconds(data.get("started_at"), data.get("finished_at"))
    tool_calls = _int_or_none(_first_present(data, "tool_calls", "tool_call_count"))
    onetool_calls = _int_or_none(
        _first_present(data, "onetool_calls", "onetool_call_count")
    )

    return TrialResult(
        task_id=str(_first_present(data, "task_id", "task", default="unknown")),
        variant_id=str(
            _first_present(data, "variant_id", "variant", default="unknown")
        ),
        repetition=int(_int_or_none(_first_present(data, "repetition", "rep")) or 1),
        accuracy_status=accuracy_status,
        score=score,
        wall_time_seconds=wall_time,
        tokens=tokens,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        onetool_calls=onetool_calls,
        final_output=_str_or_none(
            _first_present(data, "final_output", "output", "answer")
        ),
        logs_path=_path_or_none(_first_present(data, "logs_path", "log_path")),
        result_json_path=path,
    )


def aggregate_by_variant(results: list[TrialResult]) -> dict[str, dict[str, Any]]:
    """Aggregate normalized trial results by variant."""
    grouped: dict[str, list[TrialResult]] = {}
    for result in results:
        grouped.setdefault(result.variant_id, []).append(result)

    aggregates: dict[str, dict[str, Any]] = {}
    for variant_id, items in grouped.items():
        valid = [item for item in items if item.accuracy_status != "invalid"]
        passed = [item for item in valid if item.accuracy_status == "pass"]
        partial = [item for item in items if item.telemetry_status == "partial"]
        invalid = [item for item in items if item.accuracy_status == "invalid"]
        scores = [item.score for item in valid if item.score is not None]
        times = [
            item.wall_time_seconds
            for item in items
            if item.wall_time_seconds is not None
        ]
        tokens = [item.tokens for item in items if item.tokens is not None]
        costs = [item.cost_usd for item in items if item.cost_usd is not None]
        tool_calls = [item.tool_calls for item in items if item.tool_calls is not None]
        onetool_calls = [
            item.onetool_calls for item in items if item.onetool_calls is not None
        ]
        aggregates[variant_id] = {
            "task_count": len({item.task_id for item in items}),
            "repetition_count": len({item.repetition for item in items}),
            "trial_count": len(items),
            "pass_rate": _rate(len(passed), len(valid)),
            "partial_rate": _rate(len(partial), len(items)),
            "invalid_rate": _rate(len(invalid), len(items)),
            "mean_score": _mean_or_none(scores),
            "mean_wall_time_seconds": _mean_or_none(times),
            "median_wall_time_seconds": _median_or_none(times),
            "mean_tokens": _mean_or_none(tokens),
            "mean_cost_usd": _mean_or_none(costs),
            "total_cost_usd": sum(costs) if costs else None,
            "mean_tool_calls": _mean_or_none(tool_calls),
            "mean_onetool_calls": _mean_or_none(onetool_calls),
            "tooling_failure_rate": _rate(len(invalid), len(items)),
        }
    return aggregates


def render_markdown_report(results: list[TrialResult]) -> str:
    """Render a concise Markdown report for normalized results."""
    aggregates = aggregate_by_variant(results)
    lines = [
        "# ot-harness Report",
        "",
        "| Variant | Tasks | Trials | Pass rate | Invalid rate | Mean score | Mean time | Mean tokens | Total cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant_id, values in sorted(aggregates.items()):
        lines.append(
            "| "
            + " | ".join(
                [
                    variant_id,
                    str(values["task_count"]),
                    str(values["trial_count"]),
                    _fmt_rate(values["pass_rate"]),
                    _fmt_rate(values["invalid_rate"]),
                    _fmt_number(values["mean_score"]),
                    _fmt_number(values["mean_wall_time_seconds"]),
                    _fmt_number(values["mean_tokens"]),
                    _fmt_number(values["total_cost_usd"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append(f"Normalized trials: {len(results)}")
    return "\n".join(lines)


def _looks_like_result(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if any(key in data for key in ("task_id", "task")) and any(
        key in data for key in ("variant_id", "variant")
    ):
        return True
    if _is_harbor_job_summary(data):
        return True
    if "agent_result" in data and "verifier_result" in data:
        return True
    return any(key in data for key in ("verifier", "verification", "verifier_output"))


def _is_harbor_job_summary(data: Any) -> bool:
    return isinstance(data, dict) and "stats" in data and "n_total_trials" in data


def _has_descendant_result(path: Path, result_paths: list[Path]) -> bool:
    return any(other != path and path.parent in other.parents for other in result_paths)


def _with_trial_metadata(data: dict[str, Any], path: Path) -> dict[str, Any]:
    metadata_path = _find_trial_metadata(path)
    if metadata_path is None:
        return data
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return data
    merged = dict(data)
    for source_key, target_key in (
        ("task_id", "task_id"),
        ("variant_id", "variant_id"),
        ("repetition", "repetition"),
    ):
        current = merged.get(target_key)
        should_use_metadata = current is None or (
            target_key in {"task_id", "variant_id"} and not isinstance(current, str)
        )
        if should_use_metadata and metadata.get(source_key) is not None:
            merged[target_key] = metadata[source_key]
    variant_metadata = metadata.get("variant_metadata")
    if isinstance(variant_metadata, dict):
        if merged.get("variant_metadata") is None:
            merged["variant_metadata"] = variant_metadata
        if merged.get("onetool_calls") is None and variant_metadata.get("mcp") is not None:
            merged["onetool_calls"] = _int_or_none(merged.get("onetool_call_count"))
    return merged


def _find_trial_metadata(path: Path) -> Path | None:
    for directory in (path.parent, *path.parents):
        metadata_path = directory / "ot-harness-trial.json"
        if metadata_path.is_file():
            return metadata_path
    return None


def _accuracy_status(data: dict[str, Any], verifier: Any, score: float | None) -> str:
    if verifier is None and score is None:
        return "invalid"
    passed = _first_present(
        data, "passed", "success", nested=(verifier, "passed", "success")
    )
    if isinstance(passed, bool):
        return "pass" if passed else "fail"
    if score is None:
        return "invalid"
    return "pass" if score >= 1.0 else "fail"


def _harbor_job_score(data: dict[str, Any]) -> float | None:
    stats = data.get("stats")
    if not isinstance(stats, dict):
        return None
    evals = stats.get("evals")
    if not isinstance(evals, dict):
        return None
    means: list[float] = []
    for evaluation in evals.values():
        if not isinstance(evaluation, dict):
            continue
        metrics = evaluation.get("metrics")
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if isinstance(metric, dict):
                value = _float_or_none(metric.get("mean"))
                if value is not None:
                    means.append(value)
    return _mean_or_none(means)


def _harbor_trial_score(data: dict[str, Any]) -> float | None:
    verifier_result = data.get("verifier_result")
    if not isinstance(verifier_result, dict):
        return None
    rewards = verifier_result.get("rewards")
    if not isinstance(rewards, dict):
        return None
    return _float_or_none(rewards.get("reward"))


def _harbor_total_tokens(stats: dict[str, Any]) -> int | None:
    input_tokens = _int_or_none(stats.get("n_input_tokens"))
    output_tokens = _int_or_none(stats.get("n_output_tokens"))
    if input_tokens is None and output_tokens is None:
        return None
    return (input_tokens or 0) + (output_tokens or 0)


def _duration_seconds(started_at: Any, finished_at: Any) -> float | None:
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if started.tzinfo is None and finished.tzinfo is not None:
        finished = finished.replace(tzinfo=None)
    if started.tzinfo is not None and finished.tzinfo is None:
        started = started.replace(tzinfo=None)
    return (finished - started).total_seconds()


def _first_present(
    data: dict[str, Any],
    *keys: str,
    nested: tuple[Any, ...] = (),
    default: Any = None,
) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    if nested:
        container = nested[0]
        if isinstance(container, dict):
            for key in nested[1:]:
                value = container.get(key)
                if value is not None:
                    return value
    return default


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _path_or_none(value: Any) -> Path | None:
    if value is None:
        return None
    return Path(str(value))


def _mean_or_none(values: list[float] | list[int]) -> float | None:
    return float(mean(values)) if values else None


def _median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _fmt_rate(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_number(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"
