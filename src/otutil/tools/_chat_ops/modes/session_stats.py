"""session_stats report mode."""

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
        session_col="sm.session_id",
        model_col=None,
        ts_col="sm.updated_at",
        req=req,
    )
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if req.group_by:
        sql = f"""
            SELECT sm.{req.group_by} AS group_key,
                   COUNT(*) AS sessions,
                   SUM(COALESCE(sm.tool_calls_count, 0)) AS tool_calls,
                   SUM(COALESCE(sm.input_tokens, 0)) AS input_tokens,
                   SUM(COALESCE(sm.output_tokens, 0)) AS output_tokens
            FROM mv_session_metrics sm
            {where_sql}
            GROUP BY group_key
            ORDER BY sessions DESC
            LIMIT :limit
        """
        return query_rows(conn, sql=sql, params=params)

    sql = f"""
        SELECT
            sm.session_id,
            sm.provider,
            sm.project,
            sm.session_name,
            sm.updated_at,
            sm.tool_calls_count,
            sm.input_tokens,
            sm.output_tokens,
            (
                SELECT ea.annotation_value
                FROM event_annotations ea
                JOIN events e ON e.event_id = ea.event_id
                WHERE e.session_id = sm.session_id
                  AND ea.annotation_type = 'summary'
                ORDER BY ea.event_annotation_id DESC
                LIMIT 1
            ) AS summary
        FROM mv_session_metrics sm
        {where_sql}
        ORDER BY sm.updated_at DESC
        LIMIT :limit
    """
    return query_rows(conn, sql=sql, params=params)
