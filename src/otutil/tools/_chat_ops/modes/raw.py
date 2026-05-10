"""raw report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, group_expr, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params = {"limit": req.limit}
    add_common_filters(
        where,
        params,
        project_col="sm.project",
        session_col="e.session_id",
        model_col="mt.model",
        ts_col="e.event_ts",
        req=req,
    )
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if req.group_by:
        grp = group_expr(group_by=req.group_by, ts_col="e.event_ts")
        sql = f"""
            SELECT {grp} AS group_key, COUNT(*) AS events
            FROM events e
            LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
            LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
            {where_sql}
            GROUP BY group_key
            ORDER BY events DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)
    sql = f"""
        SELECT e.event_id,
               e.event_ts,
               e.session_id,
               e.turn_id,
               e.event_type,
               e.source_file,
               e.line_no,
               e.payload_json
        FROM events e
        LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
        LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
        {where_sql}
        ORDER BY e.rowid DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
