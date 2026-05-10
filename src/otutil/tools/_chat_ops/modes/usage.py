"""usage report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import group_expr, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params = {"limit": req.limit}
    if req.project:
        where.append("sm.project = :project")
        params["project"] = req.project
    if req.session_id:
        where.append("e.session_id = :session_id")
        params["session_id"] = req.session_id
    if req.model:
        where.append("COALESCE(eu.model, mt.model) = :model")
        params["model"] = req.model
    if req.start:
        where.append("e.event_ts >= :start")
        params["start"] = req.start
    if req.end:
        where.append("e.event_ts <= :end")
        params["end"] = req.end
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if req.group_by:
        grp = group_expr(group_by=req.group_by, ts_col="e.event_ts")
        if req.group_by == "model":
            grp = "COALESCE(eu.model, mt.model)"
        elif req.group_by == "project":
            grp = "sm.project"
        sql = f"""
            SELECT
                {grp} AS group_key,
                SUM(COALESCE(eu.input_tokens, 0)) AS input_tokens,
                SUM(COALESCE(eu.output_tokens, 0)) AS output_tokens,
                SUM(COALESCE(eu.cached_input_tokens, 0)) AS cached_input_tokens,
                SUM(COALESCE(eu.reasoning_tokens, 0)) AS reasoning_tokens,
                SUM(COALESCE(eu.total_tokens, 0)) AS total_tokens
            FROM event_usage eu
            JOIN events e ON e.event_id = eu.event_id
            LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
            LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
            {where_sql}
            GROUP BY group_key
            ORDER BY total_tokens DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)

    sql = f"""
        SELECT eu.event_id,
               e.session_id,
               e.turn_id,
               COALESCE(eu.model, mt.model) AS model,
               eu.input_tokens,
               eu.output_tokens,
               eu.cached_input_tokens,
               eu.reasoning_tokens,
               eu.uncached_input_tokens,
               eu.total_tokens
        FROM event_usage eu
        JOIN events e ON e.event_id = eu.event_id
        LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
        LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
        {where_sql}
        ORDER BY eu.event_id DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
