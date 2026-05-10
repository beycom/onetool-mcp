"""sessions report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, group_expr, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params = {"limit": req.limit}
    add_common_filters(
        where,
        params,
        project_col="project",
        session_col="session_id",
        model_col=None,
        ts_col="updated_at",
        req=req,
    )
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if req.group_by:
        grp = group_expr(group_by=req.group_by, ts_col="updated_at")
        sql = f"""
            SELECT {grp} AS group_key, COUNT(*) AS sessions
            FROM mv_session_metrics
            {where_sql}
            GROUP BY group_key
            ORDER BY sessions DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)

    sql = f"""
        SELECT session_id,
               provider,
               project,
               session_name,
               first_user_message,
               started_at,
               updated_at
        FROM mv_session_metrics
        {where_sql}
        ORDER BY updated_at DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
