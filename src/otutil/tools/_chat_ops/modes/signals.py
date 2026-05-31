"""signals report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, query_rows


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
        sql = f"""
            SELECT {req.group_by} AS group_key, COUNT(*) AS signals
            FROM event_signals es
            JOIN events e ON e.event_id = es.event_id
            LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
            LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
            {where_sql}
            GROUP BY group_key
            ORDER BY signals DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)

    sql = f"""
        SELECT es.event_signal_id AS id,
               e.session_id,
               e.turn_id,
               es.signal_type,
               es.content,
               es.evidence_json
        FROM event_signals es
        JOIN events e ON e.event_id = es.event_id
        LEFT JOIN mv_turn_metrics mt ON mt.turn_id = e.turn_id
        LEFT JOIN mv_session_metrics sm ON sm.session_id = e.session_id
        {where_sql}
        ORDER BY es.event_signal_id DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
