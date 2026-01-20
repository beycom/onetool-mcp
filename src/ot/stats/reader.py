"""Stats reader with aggregation and filtering.

Reads JSONL stats and aggregates by period with savings calculations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger

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
    total_chars_in: int
    total_chars_out: int
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
            "total_chars_in": self.total_chars_in,
            "total_chars_out": self.total_chars_out,
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
        model: str = "anthropic/claude-opus-4.5",
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
        records = self._load_records()
        filtered = self._filter_records(records, period, tool)
        return self._aggregate(filtered, period)

    def _load_records(self) -> list[dict[str, Any]]:
        """Load all records from JSONL."""
        if not self._path.exists():
            logger.debug(f"Stats file not found: {self._path}")
            return []

        records: list[dict[str, Any]] = []
        try:
            with self._path.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.debug(f"Skipping malformed JSON line: {line[:50]}")
        except Exception as e:
            logger.warning(f"Failed to read stats: {e}")
            return []

        return records

    def _filter_records(
        self,
        records: list[dict[str, Any]],
        period: Period,
        tool: str | None,
    ) -> list[dict[str, Any]]:
        """Filter records by period and tool."""
        if not records:
            return []

        # Calculate period cutoff
        cutoff = self._get_period_cutoff(period)

        filtered: list[dict[str, Any]] = []
        for record in records:
            # Filter by period
            if cutoff is not None:
                try:
                    ts = datetime.fromisoformat(record["ts"])
                    if ts < cutoff:
                        continue
                except (KeyError, ValueError):
                    continue

            # Filter by tool (only applies to tool-type records)
            if (
                tool is not None
                and record.get("type") == "tool"
                and record.get("tool") != tool
            ):
                continue

            filtered.append(record)

        return filtered

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

    def _aggregate(
        self, records: list[dict[str, Any]], period: Period
    ) -> AggregatedStats:
        """Aggregate records into summary stats.

        Records are split by type:
        - "run" records: contain chars_in/chars_out, used for run counts and savings
        - "tool" records: contain tool name, used for per-tool breakdown
        """
        if not records:
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

        # Separate run-level and tool-level records
        run_records: list[dict[str, Any]] = []
        tool_records_by_name: dict[str, list[dict[str, Any]]] = {}
        timestamps: list[str] = []

        for record in records:
            record_type = record.get("type", "run")
            ts = record.get("ts")
            if ts:
                timestamps.append(ts)

            if record_type == "run":
                run_records.append(record)
            elif record_type == "tool":
                tool_name = record.get("tool", "unknown")
                if tool_name not in tool_records_by_name:
                    tool_records_by_name[tool_name] = []
                tool_records_by_name[tool_name].append(record)

        # Sort timestamps for range
        timestamps.sort()

        # Aggregate run-level stats
        run_count = len(run_records)
        run_success = sum(1 for r in run_records if r.get("success") is True)
        run_error = run_count - run_success
        total_chars_in = sum(int(r.get("chars_in", 0)) for r in run_records)
        total_chars_out = sum(int(r.get("chars_out", 0)) for r in run_records)
        run_duration = sum(int(r.get("duration_ms", 0)) for r in run_records)

        # Aggregate per-tool stats
        tool_stats: list[ToolStats] = []
        total_tool_duration = 0

        for tool_name, tool_records in sorted(tool_records_by_name.items()):
            calls = len(tool_records)
            success = sum(1 for r in tool_records if r.get("success") is True)
            errors = calls - success
            duration = sum(int(r.get("duration_ms", 0)) for r in tool_records)

            tool_stats.append(
                ToolStats(
                    tool=tool_name,
                    total_calls=calls,
                    success_count=success,
                    error_count=errors,
                    total_chars_in=0,  # Tool records don't have chars
                    total_chars_out=0,
                    total_duration_ms=duration,
                    avg_duration_ms=duration / calls if calls > 0 else 0,
                )
            )

            total_tool_duration += duration

        # Calculate savings (context and time saved by consolidating run calls)
        context_saved = run_count * self._context_per_call
        time_saved = run_count * self._time_overhead_ms

        # Calculate cost estimate (actual cost of tokens used)
        input_tokens = total_chars_in / self._chars_per_token
        output_tokens = total_chars_out / self._chars_per_token
        cost_estimate = (
            (input_tokens / 1_000_000) * self._cost_per_m_input
            + (output_tokens / 1_000_000) * self._cost_per_m_output
        )

        # Calculate savings estimate (cost of context overhead avoided)
        savings_usd = (context_saved / 1_000_000) * self._cost_per_m_input

        return AggregatedStats(
            period=period,
            start_time=timestamps[0] if timestamps else None,
            end_time=timestamps[-1] if timestamps else None,
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
