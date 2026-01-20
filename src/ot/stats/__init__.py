"""Runtime statistics collection for OneTool.

Two-level statistics:
- Run-level: Tracks run() calls, durations, and calculates context savings estimates.
- Tool-level: Tracks actual tool invocations at the executor dispatch level.

Records are stored in a single JSONL file with a 'type' field discriminator.
"""

from ot.stats.html import generate_html_report
from ot.stats.jsonl_writer import (
    JsonlStatsWriter,
    get_client_name,
    get_stats_writer,
    record_tool_stats,
    set_client_name,
    set_stats_writer,
)
from ot.stats.reader import AggregatedStats, Period, StatsReader, ToolStats
from ot.stats.timing import timed_tool_call

__all__ = [
    "AggregatedStats",
    "JsonlStatsWriter",
    "Period",
    "StatsReader",
    "ToolStats",
    "generate_html_report",
    "get_client_name",
    "get_stats_writer",
    "record_tool_stats",
    "set_client_name",
    "set_stats_writer",
    "timed_tool_call",
]
