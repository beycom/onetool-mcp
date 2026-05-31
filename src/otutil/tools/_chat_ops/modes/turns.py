"""turns report mode."""

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
    if req.group_by:
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"""
            SELECT {req.group_by} AS group_key, COUNT(*) AS turns
            FROM mv_turn_metrics
            {where_sql}
            GROUP BY group_key
            ORDER BY turns DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT turn_id,
               session_id,
               turn_started_at,
               model,
               project,
               task_category,
               commands_count,
               failed_commands_count,
               tool_calls_count,
               total_tokens
        FROM mv_turn_metrics
        {where_sql}
        ORDER BY turn_started_at DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
