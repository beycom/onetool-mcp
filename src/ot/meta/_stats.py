"""Stats and result query functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.logging import LogSpan

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel

log = LogSpan


def stats(
    *,
    period: str = "all",
    tool: str = "",
    info: InfoLevel = "default",
    output: str = "",
) -> dict[str, Any] | str:
    """Get runtime statistics for OneTool usage.

    Returns aggregated statistics including call counts, success rates,
    durations, and estimated context/time savings from tool consolidation.

    Args:
        period: Time period to filter - "day", "week", "month", or "all" (default: "all").
            "day"/"week"/"month" use a rolling window (e.g. "day" = last 24 hours from now,
            not a calendar day).
        tool: Filter by tool name (e.g., "brave.search"). Empty for all tools.
        info: Output verbosity level:
            - "list": compact summary only (period, calls, success_rate, error_count, savings_usd)
            - "min": summary with duration and coffees, no tool breakdown
            - "default": summary + top 10 tools sorted by calls (default)
            - "full": all fields including per-tool durations, model info
        output: Path to write HTML report. Empty for JSON output only.

    Returns:
        Dict with aggregated statistics. Detail depends on info level:
        - "list": minimal fields, no tool breakdown
        - "min": richer summary fields, no tool breakdown
        - "default": summary stats + top 10 tools sorted by calls
        - "full": all fields including per-tool durations, model info

    Example:
        ot.stats()
        ot.stats(period="day")
        ot.stats(info="full")
        ot.stats(period="week", tool="brave.search")
        ot.stats(output="stats_report.html")
    """
    from ot.stats import Period, StatsReader
    from ot.support import get_support_dict

    with log(span="ot.stats", period=period, tool=tool or None, info=info) as s:
        cfg = get_config()

        # Validate period
        valid_periods: list[Period] = ["day", "week", "month", "all"]
        if period not in valid_periods:
            s.add("error", "invalid_period")
            return f"Error: Invalid period '{period}'. Valid: day, week, month, all. Example: ot.stats(period='day')"

        # Validate info level
        valid_info: list[InfoLevel] = ["list", "min", "default", "full"]
        if info not in valid_info:
            s.add("error", "invalid_info")
            return f"Error: Invalid info level '{info}'. Valid: list, min, default, full. Example: ot.stats(info='default')"

        # Check if stats are enabled
        if not cfg.stats.enabled:
            s.add("error", "stats_disabled")
            return "Error: Statistics collection is disabled in configuration"

        # Read stats
        reader = StatsReader.from_config(cfg)

        aggregated = reader.read(
            period=period,
            tool=tool if tool else None,
        )

        full_result = aggregated.to_dict()
        s.add("totalCalls", full_result["total_calls"])
        s.add("toolCount", len(full_result["tools"]))

        # Format based on info level
        if info == "list":
            # Minimal compact summary, no tool breakdown
            result: dict[str, Any] = {
                "period": full_result["period"],
                "total_calls": full_result["total_calls"],
                "success_rate": full_result["success_rate"],
                "error_count": full_result["error_count"],
                "savings_usd": full_result["savings_usd"],
            }
        elif info == "min":
            # Richer summary with duration and coffees, no tool breakdown
            result = {
                "period": full_result["period"],
                "total_calls": full_result["total_calls"],
                "success_rate": full_result["success_rate"],
                "error_count": full_result["error_count"],
                "total_duration_ms": full_result["total_duration_ms"],
                "savings_usd": full_result["savings_usd"],
                "coffees": full_result["coffees"],
            }
        elif info == "default":
            # Summary + top 10 tools by calls
            top_tools = sorted(
                full_result["tools"], key=lambda t: t["total_calls"], reverse=True
            )[:10]
            compact_tools = [
                {
                    "tool": t["tool"],
                    "calls": t["total_calls"],
                    "success_rate": t["success_rate"],
                    "avg_ms": t["avg_duration_ms"],
                }
                for t in top_tools
            ]
            result = {
                "period": full_result["period"],
                "total_calls": full_result["total_calls"],
                "success_rate": full_result["success_rate"],
                "error_count": full_result["error_count"],
                "total_duration_ms": full_result["total_duration_ms"],
                "savings_usd": full_result["savings_usd"],
                "coffees": full_result["coffees"],
                "top_tools": compact_tools,
            }
        else:
            # info == "full" — everything
            result = full_result
            result["support"] = get_support_dict()

        # Generate HTML report if output path specified
        if output:
            from ot.stats.html import generate_html_report

            # Resolve output path relative to tmp directory
            output_path = cfg.get_result_store_path() / output
            html_content = generate_html_report(aggregated)
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(html_content)
                result["html_report"] = str(output_path)
                s.add("htmlReport", str(output_path))
            except OSError as e:
                s.add("error", "write_failed")
                return f"Error: Cannot write to '{output}': {e.strerror}"

        return result


def result(
    *,
    handle: str,
    offset: int = 1,
    limit: int = 100,
    search: str = "",
    fuzzy: bool = False,
    tail: int = 0,
    context: int = 0,
) -> dict[str, Any]:
    """Query stored large output results with pagination and filtering.

    When tool outputs exceed max_inline_size, they are stored to disk and a
    handle is returned. Use this function to retrieve the content. You do NOT
    need to page through everything — use search or tail to target what you need.

    Args:
        handle: The result handle from a stored output
        offset: Starting line number (1-indexed, like Claude's Read tool)
        limit: Maximum lines to return (default 100)
        search: Regex pattern to filter lines — avoids full pagination
        fuzzy: Deprecated — raises ValueError if True. Use ctx.ask() for natural-language queries.
        tail: Return last N lines — useful for logs/output without knowing total
        context: Lines of context before/after each search match (like grep -C)

    Returns:
        Dict with:
        - lines: List of matching lines
        - total_lines: Total lines in stored result (after search filter)
        - returned: Number of lines returned in this chunk
        - offset: Starting offset used
        - has_more: True if more lines exist after this chunk
        - progress: Human-readable position e.g. "lines 1-50 of 343 (15%)"
        - total_size_bytes: Full size of stored result in bytes
        - next_query: Exact call to fetch next chunk (omitted when has_more=False)

    Raises:
        ValueError: If handle not found or expired

    Example:
        ot.result(handle="abc123")                          # first 100 lines
        ot.result(handle="abc123", offset=101, limit=50)    # next page
        ot.result(handle="abc123", search="error")          # only error lines
        ot.result(handle="abc123", search="fail", context=3)# matches + 3 lines around each
        ot.result(handle="abc123", tail=20)                 # last 20 lines
    """
    from ot.executor.result_store import get_result_store

    # Validate offset and limit (1-indexed)
    if offset < 1:
        raise ValueError(f"offset must be >= 1 (1-indexed), got {offset}")
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")

    with log(
        span="ot.result",
        handle=handle,
        offset=offset,
        limit=limit,
        search=search if search else None,
        tail=tail if tail > 0 else None,
        context=context if context > 0 else None,
    ) as s:
        try:
            query_result = get_result_store().query(
                handle,
                offset=offset,
                limit=limit,
                search=search,
                fuzzy=fuzzy,
                tail=tail,
                context=context,
            )
            result = query_result.to_dict() if hasattr(query_result, "to_dict") else dict(query_result)
            s.add("returned", result["returned"])
            s.add("totalLines", result["total_lines"])
            return result
        except ValueError as e:
            s.add("error", str(e))
            raise
