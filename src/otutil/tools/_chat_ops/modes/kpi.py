"""kpi report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, group_expr, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {"limit": req.limit, "min_samples": req.min_samples}
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
    if req.group_by:
        group_sql = group_expr(group_by=req.group_by, ts_col="turn_started_at")
        sql = f"""
            SELECT
                {group_sql} AS group_key,
                COUNT(*) AS turns,
                ROUND(AVG(one_shot_success) * 100.0, 2) AS one_shot_rate_pct,
                ROUND(AVG(CASE WHEN retry_count > 0 THEN 1.0 ELSE 0.0 END) * 100.0, 2) AS retry_rate_pct,
                ROUND(AVG(commands_count * 1.0), 2) AS avg_commands_per_turn,
                ROUND(AVG(tool_calls_count * 1.0), 2) AS avg_tool_calls_per_turn,
                ROUND(AVG(total_tokens * 1.0), 2) AS avg_total_tokens
            FROM mv_turn_metrics
            {where_sql}
            GROUP BY group_key
            HAVING turns >= :min_samples
            ORDER BY turns DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)

    sql = f"""
        SELECT
            COUNT(*) AS turns,
            ROUND(AVG(one_shot_success) * 100.0, 2) AS one_shot_rate_pct,
            ROUND(AVG(CASE WHEN retry_count > 0 THEN 1.0 ELSE 0.0 END) * 100.0, 2) AS retry_rate_pct,
            ROUND(AVG(commands_count * 1.0), 2) AS avg_commands_per_turn,
            ROUND(AVG(tool_calls_count * 1.0), 2) AS avg_tool_calls_per_turn,
            ROUND(AVG(total_tokens * 1.0), 2) AS avg_total_tokens
        FROM mv_turn_metrics
        {where_sql}
    """
    return query_rows(conn, sql=sql, params=params)
