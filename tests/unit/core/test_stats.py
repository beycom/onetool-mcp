"""Unit tests for stats module."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
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
@pytest.mark.asyncio
async def test_jsonl_writer_bounds_buffer_on_repeated_write_failures() -> None:
    """JsonlStatsWriter caps in-memory buffer when flush keeps failing."""
    from ot.stats import JsonlStatsWriter

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"
        writer = JsonlStatsWriter(path=jsonl_path, flush_interval=1, max_buffer_records=3)

        async def always_fail(_records):  # type: ignore[no-untyped-def]
            raise OSError("disk full")

        writer._write_records = always_fail  # type: ignore[assignment,method-assign]

        for i in range(5):
            writer.record_run(
                client=f"client-{i}",
                chars_in=1,
                chars_out=1,
                duration_ms=1,
                success=True,
            )
            await writer._flush()

        assert len(writer._buffer) == 3
        assert writer._dropped_records == 2


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

        now = datetime.now(UTC)
        # Write test data - both run and tool records
        records = [
            {"ts": (now - timedelta(hours=1)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": (now - timedelta(minutes=30)).isoformat(), "type": "run", "client": "test", "chars_in": 150, "chars_out": 600, "duration_ms": 1200, "success": True},
            {"ts": (now - timedelta(hours=1)).isoformat(), "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 500, "success": True},
            {"ts": (now - timedelta(minutes=45)).isoformat(), "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 600, "success": True},
            {"ts": (now - timedelta(minutes=20)).isoformat(), "type": "tool", "client": "test", "tool": "ot.tools", "duration_ms": 100, "success": True},
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

        now = datetime.now(UTC)
        records = [
            {"ts": now.isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": now.isoformat(), "type": "tool", "client": "test", "tool": "brave.search", "duration_ms": 500, "success": True},
            {"ts": now.isoformat(), "type": "tool", "client": "test", "tool": "ot.tools", "duration_ms": 100, "success": True},
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

        now = datetime.now(UTC)
        records = [
            {"ts": (now - timedelta(minutes=3)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": (now - timedelta(minutes=2)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 0, "duration_ms": 500, "success": False, "error_type": "TimeoutError"},
            {"ts": (now - timedelta(minutes=1)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": now.isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 0, "duration_ms": 500, "success": False, "error_type": "ValueError"},
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
        model="anthropic/claude-opus-4-6",
        cost_estimate_usd=0.0975,
    )

    d = stats.to_dict()

    assert d["period"] == "week"
    assert d["total_calls"] == 10
    assert d["success_rate"] == 80.0
    assert d["context_saved"] == 300000
    assert d["model"] == "anthropic/claude-opus-4-6"
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
    assert "<strong>brave</strong>" in html  # pack header
    assert "search" in html  # tool function name
    assert "3.0M tokens" in html  # context saved


@pytest.mark.unit
@pytest.mark.core
def test_stats_config_defaults() -> None:
    """StatsConfig has correct default values."""
    from ot.config.models import StatsConfig

    config = StatsConfig()

    assert config.enabled is True
    assert config.persist_dir == "runtime/stats"
    assert config.persist_path == "stats.jsonl"
    assert config.flush_interval_seconds == 30
    assert config.context_per_call == 30000
    assert config.time_overhead_per_call_ms == 4000
    assert config.model == "anthropic/claude-opus-4-6"
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
        record = {"ts": datetime.now(UTC).isoformat(), "type": "run", "client": "test", "chars_in": 4000, "chars_out": 8000, "duration_ms": 1000, "success": True}
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


def _make_mock_cfg(tmpdir: str) -> tuple:
    """Create mock config and stats file for ot.stats() tests."""
    from unittest.mock import MagicMock

    mock_cfg = MagicMock()
    mock_cfg.stats.enabled = True
    mock_cfg.stats.context_per_call = 30000
    mock_cfg.stats.time_overhead_per_call_ms = 4000
    mock_cfg.stats.model = "test/model"
    mock_cfg.stats.cost_per_million_input_tokens = 15.0
    mock_cfg.stats.cost_per_million_output_tokens = 75.0
    mock_cfg.stats.chars_per_token = 4.0

    stats_path = Path(tmpdir) / "stats.jsonl"

    now = datetime.now(UTC)
    # Write 15 tools so we can verify top-10 truncation
    records = [
        {"ts": (now - timedelta(minutes=2)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
        {"ts": (now - timedelta(minutes=1)).isoformat(), "type": "run", "client": "test", "chars_in": 200, "chars_out": 600, "duration_ms": 800, "success": False, "error_type": "Err"},
    ]
    for i in range(15):
        records.append(
            {"ts": (now - timedelta(seconds=i * 10)).isoformat(), "type": "tool", "client": "test", "tool": f"pack.tool_{i}", "duration_ms": 100 * (15 - i), "success": True},
        )
    stats_path.write_text("\n".join(json.dumps(r) for r in records))

    mock_cfg.get_stats_file_path.return_value = stats_path
    mock_cfg.get_result_store_path.return_value = Path(tmpdir)

    return mock_cfg, stats_path


@pytest.mark.unit
@pytest.mark.core
def test_ot_stats_info_list() -> None:
    """ot.stats(info='list') returns compact summary without tools."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_cfg, _ = _make_mock_cfg(tmpdir)
        with patch("ot.meta._stats.get_config", return_value=mock_cfg):
            from ot.meta import stats

            result = stats(info="list")

            assert isinstance(result, dict)
            assert "total_calls" in result
            assert "success_rate" in result
            assert "error_count" in result
            assert "savings_usd" in result
            # Should NOT have tools or verbose fields
            assert "tools" not in result
            assert "top_tools" not in result
            assert "total_chars_in" not in result
            assert "model" not in result


@pytest.mark.unit
@pytest.mark.core
def test_ot_stats_info_min() -> None:
    """ot.stats(info='min') returns richer summary without tool breakdown."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_cfg, _ = _make_mock_cfg(tmpdir)
        with patch("ot.meta._stats.get_config", return_value=mock_cfg):
            from ot.meta import stats

            result = stats(info="min")

            assert isinstance(result, dict)
            assert "total_calls" in result
            assert "success_rate" in result
            assert "savings_usd" in result
            assert "coffees" in result
            assert "total_duration_ms" in result
            # Should NOT have tool breakdown
            assert "top_tools" not in result
            assert "tools" not in result
            # Should NOT have verbose fields
            assert "model" not in result


@pytest.mark.unit
@pytest.mark.core
def test_ot_stats_info_full() -> None:
    """ot.stats(info='full') returns all fields including support."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_cfg, _ = _make_mock_cfg(tmpdir)
        with patch("ot.meta._stats.get_config", return_value=mock_cfg):
            from ot.meta import stats

            result = stats(info="full")

            assert isinstance(result, dict)
            assert "total_calls" in result
            assert "total_chars_in" in result
            assert "total_chars_out" in result
            assert "model" in result
            assert "tools" in result
            assert "support" in result
            # All 15 tools present
            assert len(result["tools"]) == 15


@pytest.mark.unit
@pytest.mark.core
def test_ot_stats_default_has_top_tools() -> None:
    """ot.stats() defaults to info='default' — includes top_tools."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_cfg, _ = _make_mock_cfg(tmpdir)
        with patch("ot.meta._stats.get_config", return_value=mock_cfg):
            from ot.meta import stats

            result = stats()

            assert isinstance(result, dict)
            assert "top_tools" in result
            assert "tools" not in result


@pytest.mark.unit
@pytest.mark.core
def test_ot_stats_html_write_error() -> None:
    """ot.stats() returns error message when HTML write fails."""
    from unittest.mock import MagicMock, patch

    # Mock config
    mock_cfg = MagicMock()
    mock_cfg.stats.enabled = True
    mock_cfg.stats.context_per_call = 30000
    mock_cfg.stats.time_overhead_per_call_ms = 4000
    mock_cfg.stats.model = "test/model"
    mock_cfg.stats.cost_per_million_input_tokens = 15.0
    mock_cfg.stats.cost_per_million_output_tokens = 75.0
    mock_cfg.stats.chars_per_token = 4.0

    with tempfile.TemporaryDirectory() as tmpdir:
        stats_path = Path(tmpdir) / "stats.jsonl"
        stats_path.write_text("")  # Empty file

        mock_cfg.get_stats_file_path.return_value = stats_path
        # Return a read-only directory that will fail on mkdir
        mock_cfg.get_result_store_path.return_value = Path("/nonexistent/readonly")

        with patch("ot.meta._stats.get_config", return_value=mock_cfg):
            from ot.meta import stats

            result = stats(output="report.html")

            assert isinstance(result, str)
            assert result.startswith("Error: Cannot write to")
            assert "report.html" in result


@pytest.mark.unit
@pytest.mark.core
def test_stats_reader_period_day_filters_old_records() -> None:
    """StatsReader with period='day' excludes records older than 24 hours."""
    from ot.stats import StatsReader

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_stats.jsonl"

        now = datetime.now(UTC)
        records = [
            # Recent — within 24h, should be included
            {"ts": (now - timedelta(hours=1)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": (now - timedelta(hours=23)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            # Old — more than 24h ago, should be excluded
            {"ts": (now - timedelta(hours=25)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
            {"ts": (now - timedelta(days=7)).isoformat(), "type": "run", "client": "test", "chars_in": 100, "chars_out": 500, "duration_ms": 1000, "success": True},
        ]
        jsonl_path.write_text("\n".join(json.dumps(r) for r in records))

        reader = StatsReader(path=jsonl_path)
        stats_day = reader.read(period="day")
        stats_all = reader.read(period="all")

        assert stats_day.total_calls == 2   # Only recent 2 records
        assert stats_all.total_calls == 4   # All 4 records
