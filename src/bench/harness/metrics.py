"""Metrics collection and cost calculation for benchmark runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Get current UTC datetime in a timezone-aware manner."""
    return datetime.now(UTC)


# Cached pricing from OpenRouter API: model_id -> (input_per_1M, output_per_1M)
_openrouter_pricing: dict[str, tuple[float, float]] | None = None


def get_openrouter_pricing() -> dict[str, tuple[float, float]]:
    """Fetch model pricing from OpenRouter API and cache it.

    Returns:
        Dictionary mapping model IDs to (input_price, output_price) per 1M tokens.
    """
    global _openrouter_pricing
    if _openrouter_pricing is not None:
        return _openrouter_pricing

    try:
        response = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)
        response.raise_for_status()
        data = response.json()

        pricing = {}
        for model in data.get("data", []):
            model_id = model.get("id")
            model_pricing = model.get("pricing", {})
            prompt_price = model_pricing.get("prompt")
            completion_price = model_pricing.get("completion")

            if model_id and prompt_price and completion_price:
                # API returns price per token as string, convert to per 1M tokens
                pricing[model_id] = (
                    float(prompt_price) * 1_000_000,
                    float(completion_price) * 1_000_000,
                )

        _openrouter_pricing = pricing
        logger.debug(f"Loaded pricing for {len(pricing)} models from OpenRouter")
        return pricing
    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter pricing: {e}")
        _openrouter_pricing = {}
        return {}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate estimated cost in USD for a completion.

    Args:
        model: Model identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Estimated cost in USD, or 0 if model pricing unknown.
    """
    pricing = get_openrouter_pricing().get(model)
    if pricing is None:
        logger.warning(f"No pricing found for model: {model}")
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return round(input_cost + output_cost, 6)


@dataclass
class LLMCallMetrics:
    """Metrics captured for a single LLM API call within a task.

    Tracks token usage, latency, and tool call count for each individual
    LLM call in an agentic loop.
    """

    call_number: int
    input_tokens: int
    output_tokens: int
    tool_calls_made: int
    cumulative_input: int
    latency_ms: int


@dataclass
class EvaluationResult:
    """Result from evaluation (pass/fail or scored).

    Two evaluation modes:
    - pass_fail: Binary outcome from deterministic checks (expected value matching)
    - scored: Numeric 0-100 score from LLM-as-judge evaluation

    Attributes:
        score: Numeric score (100 for pass, 0 for fail in pass_fail mode; 0-100 in scored mode)
        reason: Explanation of the evaluation result
        eval_type: Type of evaluation ("pass_fail" or "scored")
        passed: Whether the evaluation passed (only meaningful for pass_fail type)
        expected: The expected value (for pass_fail evaluations)
        actual: What was actually found/matched (for verbose logging)
    """

    score: int
    reason: str
    eval_type: str = "scored"  # "pass_fail" or "scored"
    passed: bool | None = None  # True/False for pass_fail, None for scored
    expected: Any = None  # Expected value for deterministic checks
    actual: str | None = None  # Actual matched value for logging


@dataclass
class TaskResult:
    """Result from running a single benchmark task."""

    name: str
    server: str | list[str] | None
    model: str
    prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    llm_calls: int
    tool_calls: int
    tools_used: list[str]
    duration_seconds: float
    cost_usd: float
    evaluation: EvaluationResult | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=_utc_now)
    executor: str = "simple"
    # Tool results for evaluation (actual output from tools)
    tool_results: list[str] = field(default_factory=list)
    # Tags from task config
    tags: list[str] = field(default_factory=list)
    # Per-LLM-call metrics for context growth analysis
    llm_call_metrics: list[LLMCallMetrics] = field(default_factory=list)

    @property
    def base_context(self) -> int:
        """Return first call's input tokens (base context size)."""
        if self.llm_call_metrics:
            return self.llm_call_metrics[0].input_tokens
        return 0

    @property
    def context_growth_avg(self) -> float:
        """Calculate average context growth per turn.

        Returns average increase in input tokens between consecutive LLM calls.
        Returns 0 if fewer than 2 calls.
        """
        if len(self.llm_call_metrics) < 2:
            return 0.0
        total_growth = 0
        for i in range(1, len(self.llm_call_metrics)):
            growth = (
                self.llm_call_metrics[i].input_tokens
                - self.llm_call_metrics[i - 1].input_tokens
            )
            total_growth += growth
        return total_growth / (len(self.llm_call_metrics) - 1)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML output."""
        result: dict[str, Any] = {
            "name": self.name,
            "server": self.server,
            "model": self.model,
            "metrics": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tools_used": self.tools_used,
                "duration_seconds": round(self.duration_seconds, 2),
                "cost_usd": round(self.cost_usd, 6),
                "executor": self.executor,
            },
            "response": self.response,
        }
        if self.evaluation:
            eval_dict: dict[str, Any] = {
                "type": self.evaluation.eval_type,
                "reason": self.evaluation.reason,
            }
            if self.evaluation.eval_type == "pass_fail":
                eval_dict["passed"] = self.evaluation.passed
            else:
                eval_dict["score"] = self.evaluation.score
            if self.evaluation.expected is not None:
                eval_dict["expected"] = self.evaluation.expected
            if self.evaluation.actual is not None:
                eval_dict["actual"] = self.evaluation.actual
            result["evaluation"] = eval_dict
        if self.error:
            result["error"] = self.error
        if self.llm_call_metrics:
            result["llm_call_metrics"] = [
                {
                    "call_number": m.call_number,
                    "input_tokens": m.input_tokens,
                    "output_tokens": m.output_tokens,
                    "tool_calls_made": m.tool_calls_made,
                    "cumulative_input": m.cumulative_input,
                    "latency_ms": m.latency_ms,
                }
                for m in self.llm_call_metrics
            ]
        return result


@dataclass
class ScenarioResult:
    """Result from running a benchmark scenario."""

    name: str
    model: str
    tasks: list[TaskResult]
    timestamp: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML output."""
        return {
            "scenario": self.name,
            "model": self.model,
            "timestamp": self.timestamp.isoformat(),
            "tasks": [task.to_dict() for task in self.tasks],
        }

    def calculate_totals(self) -> dict[str, Any]:
        """Calculate total metrics across all tasks."""
        # Basic metrics
        totals: dict[str, Any] = {
            "total_input_tokens": sum(t.input_tokens for t in self.tasks),
            "total_output_tokens": sum(t.output_tokens for t in self.tasks),
            "total_llm_calls": sum(t.llm_calls for t in self.tasks),
            "total_tool_calls": sum(t.tool_calls for t in self.tasks),
            "total_duration_seconds": sum(t.duration_seconds for t in self.tasks),
            "total_cost_usd": sum(t.cost_usd for t in self.tasks),
            "task_count": len(self.tasks),
            "error_count": sum(1 for t in self.tasks if t.error),
        }

        # Evaluation aggregation
        pass_fail_tasks = [
            t
            for t in self.tasks
            if t.evaluation and t.evaluation.eval_type == "pass_fail"
        ]
        scored_tasks = [
            t for t in self.tasks if t.evaluation and t.evaluation.eval_type == "scored"
        ]

        if pass_fail_tasks:
            passed = sum(
                1 for t in pass_fail_tasks if t.evaluation and t.evaluation.passed
            )
            failed = len(pass_fail_tasks) - passed
            totals["pass_count"] = passed
            totals["fail_count"] = failed

        if scored_tasks:
            scores = [t.evaluation.score for t in scored_tasks if t.evaluation]
            totals["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0

        return totals
