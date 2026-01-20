"""Unit tests for stats module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_jsonl_writer_creates_file() -> None:
    """JsonlStatsWriter creates JSONL file on flush."""
    from ot.stats import JsonlStatsWriter

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"
        writer = JsonlStatsWriter(path=jsonl_path, flush_interval=1)

        await writer.start()
        writer.record_run(
            client="test-client",
            chars_in=100,
            chars_out=500,
            duration_ms=1234,
            success=True,
        )
        await writer.stop()

        # Check file contents
        content = jsonl_path.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["type"] == "run"
        assert record["client"] == "test-client"
        assert record["chars_in"] == 100
        assert record["chars_out"] == 500
        assert record["duration_ms"] == 1234
        assert record["success"] is True
        assert "ts" in record


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_jsonl_writer_tool_record() -> None:
    """JsonlStatsWriter records tool-level stats."""
    from ot.stats import JsonlStatsWriter

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"
        writer = JsonlStatsWriter(path=jsonl_path, flush_interval=1)

        await writer.start()
        writer.record_tool(
            client="test-client",
            tool="brave.search",
            duration_ms=500,
            success=True,
        )
        await writer.stop()

        content = jsonl_path.read_text()
        record = json.loads(content.strip())

        assert record["type"] == "tool"
        assert record["client"] == "test-client"
        assert record["tool"] == "brave.search"
        assert record["duration_ms"] == 500
        assert record["success"] is True


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_jsonl_writer_appends() -> None:
    """JsonlStatsWriter appends to existing file."""
    from ot.stats import JsonlStatsWriter

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        # First write
        writer1 = JsonlStatsWriter(path=jsonl_path, flush_interval=1)
        await writer1.start()
        writer1.record_run(
            client="client1",
            chars_in=10,
            chars_out=20,
            duration_ms=50,
            success=True,
        )
        await writer1.stop()

        # Second write
        writer2 = JsonlStatsWriter(path=jsonl_path, flush_interval=1)
        await writer2.start()
        writer2.record_run(
            client="client2",
            chars_in=30,
            chars_out=40,
            duration_ms=60,
            success=True,
        )
        await writer2.stop()

        # Check file contents
        content = jsonl_path.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 2


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_empty_file() -> None:
    """StatsReader returns empty stats for missing file."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "nonexistent.jsonl"
        reader = StatsReader(path=jsonl_path)

        stats = reader.read()

        assert stats.total_calls == 0
        assert stats.tools == []
        assert stats.context_saved == 0


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_aggregates_by_type() -> None:
    """StatsReader aggregates run and tool records separately."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        # Write test data - both run and tool records
        records = [
            {"ts": "2024-01-15T10:00:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": "2024-01-15T10:01:00Z", "type": "run", "client": "test", "chars_in": 150, "chars_out": 600, "duration_ms": 1200, "success": True},
            {"ts": "2024-01-15T10:00:30Z", "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 500, "success": True},
            {"ts": "2024-01-15T10:01:30Z", "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 600, "success": True},
            {"ts": "2024-01-15T10:02:00Z", "type": "tool", "client": "test", "tool": "ot.tools", "duration_ms": 100, "success": True},
        ]
        jsonl_path.write_text("\n".join(json.dumps(r) for r in records))

        reader = StatsReader(path=jsonl_path, context_per_call=30000, time_overhead_per_call_ms=4000)
        stats = reader.read()

        # Run-level stats
        assert stats.total_calls == 2  # Only run records
        assert stats.total_chars_in == 250
        assert stats.total_chars_out == 1100

        # Tool breakdown
        assert len(stats.tools) == 2  # brave.search and ot.tools

        # Check brave.search stats
        brave_stats = next(t for t in stats.tools if t.tool == "brave.search")
        assert brave_stats.total_calls == 2
        assert brave_stats.avg_duration_ms == 550

        # Check savings calculation (based on run count)
        assert stats.context_saved == 2 * 30000  # 60000
        assert stats.time_saved_ms == 2 * 4000  # 8000


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_tool_filter() -> None:
    """StatsReader filters tool records by tool name."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        records = [
            {"ts": "2024-01-15T10:00:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": "2024-01-15T10:00:30Z", "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 500, "success": True},
            {"ts": "2024-01-15T10:01:30Z", "type": "tool", "client": "test", "tool": "ot.tools", "duration_ms": 100, "success": True},
        ]
        jsonl_path.write_text("\n".join(json.dumps(r) for r in records))

        reader = StatsReader(path=jsonl_path)
        stats = reader.read(tool="brave.search")

        # Run records still included
        assert stats.total_calls == 1

        # Only filtered tool in breakdown
        assert len(stats.tools) == 1
        assert stats.tools[0].tool == "brave.search"


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_success_rate() -> None:
    """StatsReader calculates success rate correctly."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        records = [
            {"ts": "2024-01-15T10:00:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": "2024-01-15T10:01:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 0, "duration_ms": 500, "success": False, "error_type": "TimeoutError"},
            {"ts": "2024-01-15T10:02:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": "2024-01-15T10:03:00Z", "type": "run", "client": "test", "chars_in": 100, "chars_out": 0, "duration_ms": 500, "success": False, "error_type": "ValueError"},
        ]
        jsonl_path.write_text("\n".join(json.dumps(r) for r in records))

        reader = StatsReader(path=jsonl_path)
        stats = reader.read()

        assert stats.total_calls == 4
        assert stats.success_count == 2
        assert stats.error_count == 2
        assert stats.success_rate == 50.0


@pytest.mark.unit
@pytest.mark.core
def test_aggregated_stats_to_dict() -> None:
    """AggregatedStats.to_dict() returns serializable dict."""
    from ot.stats import AggregatedStats, ToolStats

    tool_stats = ToolStats(
        tool="test.tool",
        total_calls=10,
        success_count=8,
        error_count=2,
        total_chars_in=1000,
        total_chars_out=5000,
        total_duration_ms=10000,
        avg_duration_ms=1000.0,
    )

    stats = AggregatedStats(
        period="week",
        start_time="2024-01-08T00:00:00Z",
        end_time="2024-01-15T00:00:00Z",
        total_calls=10,
        success_count=8,
        error_count=2,
        total_chars_in=1000,
        total_chars_out=5000,
        total_duration_ms=10000,
        context_saved=300000,
        time_saved_ms=40000,
        tools=[tool_stats],
        model="anthropic/claude-opus-4.5",
        cost_estimate_usd=0.0975,
    )

    d = stats.to_dict()

    assert d["period"] == "week"
    assert d["total_calls"] == 10
    assert d["success_rate"] == 80.0
    assert d["context_saved"] == 300000
    assert d["model"] == "anthropic/claude-opus-4.5"
    assert d["cost_estimate_usd"] == 0.0975
    assert len(d["tools"]) == 1
    assert d["tools"][0]["tool"] == "test.tool"


@pytest.mark.unit
@pytest.mark.core
def test_html_report_generation() -> None:
    """generate_html_report() creates valid HTML."""
    from ot.stats import AggregatedStats, ToolStats, generate_html_report

    stats = AggregatedStats(
        period="day",
        start_time="2024-01-15T00:00:00Z",
        end_time="2024-01-15T23:59:59Z",
        total_calls=100,
        success_count=95,
        error_count=5,
        total_chars_in=10000,
        total_chars_out=50000,
        total_duration_ms=100000,
        context_saved=3000000,
        time_saved_ms=400000,
        tools=[
            ToolStats(
                tool="brave.search",
                total_calls=50,
                success_count=48,
                error_count=2,
                total_chars_in=5000,
                total_chars_out=25000,
                total_duration_ms=50000,
                avg_duration_ms=1000.0,
            ),
        ],
    )

    html = generate_html_report(stats)

    # Check HTML structure
    assert "<!DOCTYPE html>" in html
    assert "<title>OneTool Statistics Report</title>" in html
    assert "100" in html  # total calls
    assert "95.0%" in html  # success rate
    assert "brave.search" in html  # tool name
    assert "3.0M tokens" in html  # context saved


@pytest.mark.unit
@pytest.mark.core
def test_stats_config_defaults() -> None:
    """StatsConfig has correct default values."""
    from ot.config.loader import StatsConfig

    config = StatsConfig()

    assert config.enabled is True
    assert config.persist_path == "stats.jsonl"
    assert config.flush_interval_seconds == 30
    assert config.context_per_call == 30000
    assert config.time_overhead_per_call_ms == 4000
    assert config.model == "anthropic/claude-opus-4.5"
    assert config.cost_per_million_input_tokens == 15.0
    assert config.cost_per_million_output_tokens == 75.0
    assert config.chars_per_token == 4.0


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_cost_estimate() -> None:
    """StatsReader calculates cost estimate correctly."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        # 4000 chars in, 8000 chars out
        # With 4 chars/token: 1000 input tokens, 2000 output tokens
        # Cost: (1000/1M * 15) + (2000/1M * 75) = 0.015 + 0.15 = 0.165
        record = {"ts": "2024-01-15T10:00:00Z", "type": "run", "client": "test", "chars_in": 4000, "chars_out": 8000, "duration_ms": 1000, "success": True}
        jsonl_path.write_text(json.dumps(record))

        reader = StatsReader(
            path=jsonl_path,
            model="test/model",
            cost_per_million_input_tokens=15.0,
            cost_per_million_output_tokens=75.0,
            chars_per_token=4.0,
        )
        stats = reader.read()

        assert stats.model == "test/model"
        # 1000 input tokens / 1M * 15 = 0.015
        # 2000 output tokens / 1M * 75 = 0.15
        # Total: 0.165
        assert abs(stats.cost_estimate_usd - 0.165) < 0.0001


@pytest.mark.unit
@pytest.mark.core
def test_timed_tool_call_context_manager() -> None:
    """timed_tool_call records stats on exit."""
    from unittest.mock import patch

    from ot.stats import timed_tool_call

    with patch("ot.stats.timing.record_tool_stats") as mock_record:
        with timed_tool_call("test.tool", client="test-client"):
            pass  # Simulate successful call

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["tool"] == "test.tool"
        assert call_kwargs["success"] is True
        assert call_kwargs["error_type"] is None
        assert call_kwargs["duration_ms"] >= 0


@pytest.mark.unit
@pytest.mark.core
def test_timed_tool_call_records_error() -> None:
    """timed_tool_call records error details on exception."""
    from unittest.mock import patch

    from ot.stats import timed_tool_call

    with patch("ot.stats.timing.record_tool_stats") as mock_record:
        with pytest.raises(ValueError):
            with timed_tool_call("test.tool", client="test-client"):
                raise ValueError("test error")

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["tool"] == "test.tool"
        assert call_kwargs["success"] is False
        assert call_kwargs["error_type"] == "ValueError"


