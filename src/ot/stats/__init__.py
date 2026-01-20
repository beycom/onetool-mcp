"""Runtime statistics collection for OneTool.

Two-level statistics:
- Run-level: Tracks run() calls, durations, and calculates context savings estimates.
- Tool-level: Tracks actual tool invocations at the executor dispatch level.

Records are stored in a single JSONL file with a 'type' field discriminator.
Optional anonymous telemetry can be enabled via PostHog.
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
from ot.stats.telemetry import (
    capture_run_completed,
    capture_server_started,
    capture_tool_executed,
    initialize_telemetry,
    is_telemetry_enabled,
    shutdown_telemetry,
)
from ot.stats.timing import timed_tool_call

__all__ = [
    "AggregatedStats",
    "JsonlStatsWriter",
    "Period",
    "StatsReader",
    "ToolStats",
    "capture_run_completed",
    "capture_server_started",
    "capture_tool_executed",
    "generate_html_report",
    "get_client_name",
    "get_stats_writer",
    "initialize_telemetry",
    "is_telemetry_enabled",
    "record_tool_stats",
    "set_client_name",
    "set_stats_writer",
    "shutdown_telemetry",
    "timed_tool_call",
]
