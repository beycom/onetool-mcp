"""categories report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params = {"limit": req.limit}
    add_common_filters(
        where,
        params,
        project_col="project",
        session_col="session_id",
        model_col="model",
        ts_col="turn_started_at",
        req=req,
    )
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT
            task_category,
            COUNT(*) AS turns,
            ROUND(AVG(one_shot_success) * 100.0, 2) AS one_shot_rate_pct,
            ROUND(AVG(CASE WHEN retry_count > 0 THEN 1.0 ELSE 0.0 END) * 100.0, 2) AS retry_rate_pct,
            ROUND(AVG(tool_calls_count * 1.0), 2) AS avg_tool_calls_per_turn
        FROM mv_turn_metrics
        {where_sql}
        GROUP BY task_category
        ORDER BY turns DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
