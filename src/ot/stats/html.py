"""HTML report generation for OneTool statistics.

Generates self-contained HTML reports with inline CSS, no JS dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ot.support import (
    KOFI_URL,
    SUPPORT_HTML_BUTTON_TEXT,
    SUPPORT_HTML_MESSAGE,
    SUPPORT_HTML_TITLE,
)

if TYPE_CHECKING:
    from ot.stats.reader import AggregatedStats


def generate_html_report(stats: AggregatedStats) -> str:
    """Generate a self-contained HTML report from aggregated stats.

    Args:
        stats: Aggregated statistics from StatsReader

    Returns:
        Complete HTML document as string
    """
    # Format time saved in human-readable format
    time_saved_seconds = stats.time_saved_ms / 1000
    if time_saved_seconds >= 3600:
        time_saved_str = f"{time_saved_seconds / 3600:.1f} hours"
    elif time_saved_seconds >= 60:
        time_saved_str = f"{time_saved_seconds / 60:.1f} minutes"
    else:
        time_saved_str = f"{time_saved_seconds:.1f} seconds"

    # Format context saved
    if stats.context_saved >= 1_000_000:
        context_saved_str = f"{stats.context_saved / 1_000_000:.1f}M tokens"
    elif stats.context_saved >= 1_000:
        context_saved_str = f"{stats.context_saved / 1_000:.1f}K tokens"
    else:
        context_saved_str = f"{stats.context_saved} tokens"

    # Format savings estimate with coffee equivalent
    if stats.savings_usd >= 1.0:
        savings_str = f"${stats.savings_usd:.2f}"
    elif stats.savings_usd >= 0.01:
        savings_str = f"${stats.savings_usd:.3f}"
    else:
        savings_str = f"${stats.savings_usd:.4f}"

    # Coffee equivalent
    coffees = stats.coffees
    if coffees >= 1.0:
        coffees_str = f"{coffees:.1f} coffees"
    else:
        coffees_str = f"{coffees:.2f} coffees"

    savings_display = f"{savings_str} ({coffees_str})"

    # Build tool rows
    tool_rows = ""
    for tool in stats.tools:
        avg_duration = f"{tool.avg_duration_ms:.0f}ms"
        tool_rows += f"""
            <tr>
                <td>{tool.tool}</td>
                <td class="num">{tool.total_calls}</td>
                <td class="num">{tool.success_rate:.1f}%</td>
                <td class="num">{avg_duration}</td>
                <td class="num">{tool.total_chars_in:,}</td>
                <td class="num">{tool.total_chars_out:,}</td>
            </tr>"""

    # Period display
    period_display = stats.period.capitalize()
    if stats.start_time and stats.end_time:
        # Extract just the date portion
        start_date = stats.start_time[:10]
        end_date = stats.end_time[:10]
        if start_date == end_date:
            period_display = f"{period_display} ({start_date})"
        else:
            period_display = f"{period_display} ({start_date} to {end_date})"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OneTool Statistics Report</title>
    <style>
        :root {{
            --bg: #f8f9fa;
            --card-bg: #ffffff;
            --text: #212529;
            --text-muted: #6c757d;
            --border: #dee2e6;
            --primary: #0d6efd;
            --success: #198754;
            --warning: #ffc107;
            --kofi: #ff5e5b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ margin-bottom: 0.5rem; }}
        .subtitle {{ color: var(--text-muted); margin-bottom: 2rem; }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }}
        .card-label {{ color: var(--text-muted); font-size: 0.875rem; margin-bottom: 0.25rem; }}
        .card-value {{ font-size: 1.75rem; font-weight: 600; }}
        .card-value.success {{ color: var(--success); }}
        .card-value.primary {{ color: var(--primary); }}
        .card-value.warning {{ color: var(--warning); }}
        .card-sub {{ color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem; }}
        table {{
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            border-collapse: collapse;
            overflow: hidden;
        }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: var(--bg); font-weight: 600; }}
        tr:last-child td {{ border-bottom: none; }}
        .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .empty {{ color: var(--text-muted); text-align: center; padding: 2rem; }}
        .support {{
            margin-top: 2rem;
            padding: 1.5rem;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            text-align: center;
        }}
        .support h3 {{ margin-bottom: 0.5rem; font-size: 1rem; }}
        .support p {{ color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem; }}
        .kofi-btn {{
            display: inline-block;
            background: var(--kofi);
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-weight: 500;
            font-size: 0.875rem;
        }}
        .kofi-btn:hover {{ opacity: 0.9; }}
        footer {{ margin-top: 2rem; color: var(--text-muted); font-size: 0.875rem; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OneTool Statistics</h1>
        <p class="subtitle">Period: {period_display}</p>

        <div class="cards">
            <div class="card">
                <div class="card-label">Total Calls</div>
                <div class="card-value">{stats.total_calls:,}</div>
            </div>
            <div class="card">
                <div class="card-label">Success Rate</div>
                <div class="card-value success">{stats.success_rate:.1f}%</div>
            </div>
            <div class="card">
                <div class="card-label">Context Saved</div>
                <div class="card-value primary">{context_saved_str}</div>
            </div>
            <div class="card">
                <div class="card-label">Time Saved</div>
                <div class="card-value primary">{time_saved_str}</div>
            </div>
            <div class="card">
                <div class="card-label">Est. Savings</div>
                <div class="card-value success">{savings_display}</div>
            </div>
        </div>

        <h2 style="margin-bottom: 1rem;">Per-Tool Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Tool</th>
                    <th class="num">Calls</th>
                    <th class="num">Success Rate</th>
                    <th class="num">Avg Duration</th>
                    <th class="num">Chars In</th>
                    <th class="num">Chars Out</th>
                </tr>
            </thead>
            <tbody>
                {tool_rows if tool_rows else '<tr><td colspan="6" class="empty">No data available</td></tr>'}
            </tbody>
        </table>

        <div class="support">
            <h3>{SUPPORT_HTML_TITLE}</h3>
            <p>{SUPPORT_HTML_MESSAGE}</p>
            <a href="{KOFI_URL}" class="kofi-btn" target="_blank" rel="noopener">
                {SUPPORT_HTML_BUTTON_TEXT}
            </a>
        </div>

        <footer>
            Generated by OneTool &middot; {stats.end_time[:19] if stats.end_time else 'N/A'}
        </footer>
    </div>
</body>
</html>"""

    return html
