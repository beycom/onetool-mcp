"""Stats reader with aggregation and filtering.

Reads JSONL stats and aggregates by period with savings calculations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger

from ot.logging import LogEntry

if TYPE_CHECKING:
    from pathlib import Path

Period = Literal["day", "week", "month", "all"]


@dataclass
class ToolStats:
    """Aggregated statistics for a single tool."""

    tool: str
    total_calls: int
    success_count: int
    error_count: int
    total_duration_ms: int
    avg_duration_ms: float

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.success_count / self.total_calls) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "tool": self.tool,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 1),
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": round(self.avg_duration_ms, 1),
        }


# Cost per coffee for savings display (hardcoded)
COFFEE_COST_USD = 5.0


@dataclass
class AggregatedStats:
    """Aggregated statistics summary."""

    period: Period
    start_time: str | None
    end_time: str | None
    total_calls: int
    success_count: int
    error_count: int
    total_chars_in: int
    total_chars_out: int
    total_duration_ms: int
    context_saved: int
    time_saved_ms: int
    tools: list[ToolStats]
    model: str = ""
    cost_estimate_usd: float = 0.0
    savings_usd: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.success_count / self.total_calls) * 100

    @property
    def coffees(self) -> float:
        """Calculate coffee equivalent of savings."""
        return self.savings_usd / COFFEE_COST_USD

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "period": self.period,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 1),
            "total_chars_in": self.total_chars_in,
            "total_chars_out": self.total_chars_out,
            "total_duration_ms": self.total_duration_ms,
            "context_saved": self.context_saved,
            "time_saved_ms": self.time_saved_ms,
            "model": self.model,
            "cost_estimate_usd": round(self.cost_estimate_usd, 4),
            "savings_usd": round(self.savings_usd, 2),
            "coffees": round(self.coffees, 1),
            "tools": [t.to_dict() for t in self.tools],
        }


class StatsReader:
    """Reads and aggregates statistics from JSONL.

    Usage:
        reader = StatsReader(path, context_per_call=30000, time_overhead_ms=4000)
        stats = reader.read(period="week", tool="brave.search")
    """

    def __init__(
        self,
        path: Path,
        context_per_call: int = 30000,
        time_overhead_per_call_ms: int = 4000,
        model: str = "anthropic/claude-opus-4-6",
        cost_per_million_input_tokens: float = 15.0,
        cost_per_million_output_tokens: float = 75.0,
        chars_per_token: float = 4.0,
    ) -> None:
        """Initialize reader.

        Args:
            path: Path to JSONL file
            context_per_call: Context tokens saved per consolidated call
            time_overhead_per_call_ms: Time overhead in ms saved per call
            model: Model name for cost estimation
            cost_per_million_input_tokens: Cost in USD per million input tokens
            cost_per_million_output_tokens: Cost in USD per million output tokens
            chars_per_token: Average characters per token for estimation
        """
        self._path = path
        self._context_per_call = context_per_call
        self._time_overhead_ms = time_overhead_per_call_ms
        self._model = model
        self._cost_per_m_input = cost_per_million_input_tokens
        self._cost_per_m_output = cost_per_million_output_tokens
        self._chars_per_token = chars_per_token

    @classmethod
    def from_config(cls, cfg: Any) -> StatsReader:
        """Create a StatsReader from a config object."""
        return cls(
            path=cfg.get_stats_file_path(),
            context_per_call=cfg.stats.context_per_call,
            time_overhead_per_call_ms=cfg.stats.time_overhead_per_call_ms,
            model=cfg.stats.model,
            cost_per_million_input_tokens=cfg.stats.cost_per_million_input_tokens,
            cost_per_million_output_tokens=cfg.stats.cost_per_million_output_tokens,
            chars_per_token=cfg.stats.chars_per_token,
        )

    def read(
        self,
        period: Period = "all",
        tool: str | None = None,
    ) -> AggregatedStats:
        """Read and aggregate stats.

        Args:
            period: Time period to filter (day/week/month/all)
            tool: Optional tool name filter

        Returns:
            Aggregated statistics
        """
        # Stream records to avoid loading full JSONL into memory.
        return self._aggregate_stream(period, tool)

    def _aggregate_stream(
        self,
        period: Period,
        tool: str | None,
    ) -> AggregatedStats:
        """Aggregate records directly from file stream for bounded memory usage."""
        if not self._path.exists():
            logger.debug(f"Stats file not found: {self._path}")
            return AggregatedStats(
                period=period,
                start_time=None,
                end_time=None,
                total_calls=0,
                success_count=0,
                error_count=0,
                total_chars_in=0,
                total_chars_out=0,
                total_duration_ms=0,
                context_saved=0,
                time_saved_ms=0,
                tools=[],
            )

        cutoff = self._get_period_cutoff(period)

        start_time: str | None = None
        end_time: str | None = None

        run_count = 0
        run_success = 0
        total_chars_in = 0
        total_chars_out = 0
        run_duration = 0

        # tool_name -> [calls, success, duration_ms]
        tool_acc: dict[str, list[int]] = {}

        try:
            with self._path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping malformed JSON line: {line[:50]}")
                        continue

                    ts = record.get("ts")
                    if not isinstance(ts, str):
                        # Records without a valid timestamp are malformed; skip
                        # regardless of period (including "all").
                        continue

                    if cutoff is not None:
                        try:
                            ts_dt = datetime.fromisoformat(ts)
                        except ValueError:
                            continue
                        if ts_dt < cutoff:
                            continue

                    if start_time is None or ts < start_time:
                        start_time = ts
                    if end_time is None or ts > end_time:
                        end_time = ts

                    record_type = record.get("type", "run")
                    if record_type == "run":
                        run_count += 1
                        if record.get("success") is True:
                            run_success += 1
                        total_chars_in += int(record.get("chars_in", 0))
                        total_chars_out += int(record.get("chars_out", 0))
                        run_duration += int(record.get("duration_ms", 0))
                    elif record_type == "tool":
                        tool_name = record.get("tool", "unknown")
                        if tool is not None and tool_name != tool:
                            continue
                        acc = tool_acc.setdefault(tool_name, [0, 0, 0])
                        acc[0] += 1
                        if record.get("success") is True:
                            acc[1] += 1
                        acc[2] += int(record.get("duration_ms", 0))
        except Exception as e:
            logger.warning(LogEntry(event="stats.read.failed", path=self._path).failure(e))
            return AggregatedStats(
                period=period,
                start_time=None,
                end_time=None,
                total_calls=0,
                success_count=0,
                error_count=0,
                total_chars_in=0,
                total_chars_out=0,
                total_duration_ms=0,
                context_saved=0,
                time_saved_ms=0,
                tools=[],
            )

        tool_stats: list[ToolStats] = []
        for tool_name in sorted(tool_acc):
            calls, success, duration = tool_acc[tool_name]
            tool_stats.append(
                ToolStats(
                    tool=tool_name,
                    total_calls=calls,
                    success_count=success,
                    error_count=calls - success,
                    total_duration_ms=duration,
                    avg_duration_ms=duration / calls if calls > 0 else 0,
                )
            )

        run_error = run_count - run_success
        context_saved = run_count * self._context_per_call
        time_saved = run_count * self._time_overhead_ms
        input_tokens = total_chars_in / self._chars_per_token
        output_tokens = total_chars_out / self._chars_per_token
        cost_estimate = (
            (input_tokens / 1_000_000) * self._cost_per_m_input
            + (output_tokens / 1_000_000) * self._cost_per_m_output
        )
        # Savings are avoided context re-sends (input tokens only — no output avoided).
        savings_usd = (context_saved / 1_000_000) * self._cost_per_m_input

        return AggregatedStats(
            period=period,
            start_time=start_time,
            end_time=end_time,
            total_calls=run_count,
            success_count=run_success,
            error_count=run_error,
            total_chars_in=total_chars_in,
            total_chars_out=total_chars_out,
            total_duration_ms=run_duration,
            context_saved=context_saved,
            time_saved_ms=time_saved,
            tools=tool_stats,
            model=self._model,
            cost_estimate_usd=cost_estimate,
            savings_usd=savings_usd,
        )

    def _get_period_cutoff(self, period: Period) -> datetime | None:
        """Get cutoff datetime for period."""
        if period == "all":
            return None

        now = datetime.now(UTC)
        if period == "day":
            return now - timedelta(days=1)
        elif period == "week":
            return now - timedelta(weeks=1)
        elif period == "month":
            return now - timedelta(days=30)

        return None
