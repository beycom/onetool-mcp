"""sessions_summary report mode."""

from __future__ import annotations

from typing import Any

from otutil.tools._chat_ops.common import add_common_filters, query_rows


def run(conn: Any, *, req: Any) -> list[dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {"limit": req.limit}
    add_common_filters(
        where,
        params,
        project_col="sm.project",
        session_col="sm.session_id",
        model_col=None,
        ts_col="sm.updated_at",
        req=req,
    )
    if req.model:
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM mv_turn_metrics tm_model
                WHERE tm_model.session_id = sm.session_id
                  AND tm_model.model = :model
            )
            """
        )
        params["model"] = req.model
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT
            sm.session_id,
            sm.provider,
            sm.project,
            sm.session_name,
            sm.started_at,
            sm.updated_at,
            sm.turns_count AS turns,
            ROUND(AVG(CASE WHEN tm.one_shot_success = 1 THEN 1.0 ELSE 0.0 END) * 100.0, 2) AS one_shot_rate_pct,
            ROUND(AVG(CASE WHEN tm.retry_count > 0 THEN 1.0 ELSE 0.0 END) * 100.0, 2) AS retry_rate_pct,
            COALESCE(SUM(tm.commands_count), 0) AS commands_count,
            COALESCE(SUM(tm.tool_calls_count), 0) AS tool_calls_count,
            COALESCE(SUM(tm.input_tokens), 0) AS input_tokens,
            COALESCE(SUM(tm.output_tokens), 0) AS output_tokens,
            COALESCE(SUM(tm.total_tokens), 0) AS total_tokens,
            (
                SELECT ea.annotation_value
                FROM event_annotations ea
                JOIN events e ON e.event_id = ea.event_id
                WHERE e.session_id = sm.session_id
                  AND ea.annotation_type = 'summary'
                  AND ea.source = 'tool_call'
                ORDER BY ea.event_annotation_id DESC
                LIMIT 1
            ) AS latest_manual_summary_annotation
        FROM mv_session_metrics sm
        LEFT JOIN mv_turn_metrics tm ON tm.session_id = sm.session_id
        {where_sql}
        GROUP BY
            sm.session_id,
            sm.provider,
            sm.project,
            sm.session_name,
            sm.started_at,
            sm.updated_at,
            sm.turns_count
        ORDER BY sm.updated_at DESC
        LIMIT :limit
    """
    sessions = query_rows(conn, sql=sql, params=params)

    for session in sessions:
        session_id = str(session["session_id"])
        turn_count = int(session.get("turns") or 0)

        session["top_categories"] = query_rows(
            conn,
            sql="""
                SELECT
                    task_category AS category,
                    COUNT(*) AS turns,
                    ROUND(COUNT(*) * 100.0 / NULLIF(:turn_count, 0), 2) AS rate_pct
                FROM mv_turn_metrics
                WHERE session_id = :session_id
                GROUP BY task_category
                ORDER BY turns DESC, category ASC
                LIMIT 10
            """,
            params={"session_id": session_id, "turn_count": turn_count},
        )
        session["top_signals"] = query_rows(
            conn,
            sql="""
                SELECT
                    es.signal_type,
                    COUNT(*) AS signals
                FROM event_signals es
                JOIN events e ON e.event_id = es.event_id
                WHERE e.session_id = :session_id
                GROUP BY es.signal_type
                ORDER BY signals DESC, es.signal_type ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )
        session["top_files_read"] = query_rows(
            conn,
            sql="""
                SELECT
                    ef.file_path,
                    COUNT(*) AS reads
                FROM event_file_ops ef
                JOIN events e ON e.event_id = ef.event_id
                WHERE e.session_id = :session_id
                  AND ef.op = 'read'
                GROUP BY ef.file_path
                ORDER BY reads DESC, ef.file_path ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )
        session["top_files_written"] = query_rows(
            conn,
            sql="""
                SELECT
                    ef.file_path,
                    COUNT(*) AS writes
                FROM event_file_ops ef
                JOIN events e ON e.event_id = ef.event_id
                WHERE e.session_id = :session_id
                  AND ef.op = 'write'
                GROUP BY ef.file_path
                ORDER BY writes DESC, ef.file_path ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )
        session["write_churn_hotspots"] = query_rows(
            conn,
            sql="""
                SELECT
                    ef.file_path,
                    SUM(ef.churn) AS total_churn,
                    COUNT(*) AS write_events
                FROM event_file_ops ef
                JOIN events e ON e.event_id = ef.event_id
                WHERE e.session_id = :session_id
                  AND ef.op = 'write'
                GROUP BY ef.file_path
                ORDER BY total_churn DESC, write_events DESC, ef.file_path ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )
        session["tool_token_attribution"] = query_rows(
            conn,
            sql="""
                SELECT
                    usage.tool_name,
                    COUNT(*) AS turns_with_tool,
                    COALESCE(SUM(tm.input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(tm.output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(tm.total_tokens), 0) AS total_tokens
                FROM (
                    SELECT DISTINCT
                        e.session_id,
                        e.turn_id,
                        etc.tool_name
                    FROM event_tool_calls etc
                    JOIN events e ON e.event_id = etc.event_id
                    WHERE e.session_id = :session_id
                ) usage
                JOIN mv_turn_metrics tm
                  ON tm.session_id = usage.session_id
                 AND tm.turn_id = usage.turn_id
                GROUP BY usage.tool_name
                ORDER BY total_tokens DESC, turns_with_tool DESC, usage.tool_name ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )
        session["skill_token_attribution"] = query_rows(
            conn,
            sql="""
                SELECT
                    usage.skill_name,
                    COUNT(*) AS turns_with_skill,
                    COALESCE(SUM(tm.input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(tm.output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(tm.total_tokens), 0) AS total_tokens
                FROM (
                    SELECT DISTINCT
                        e.session_id,
                        e.turn_id,
                        SUBSTR(ei.invocation_text, 2) AS skill_name
                    FROM event_invocations ei
                    JOIN events e ON e.event_id = ei.event_id
                    WHERE e.session_id = :session_id
                      AND ei.invocation_type = 'dollar'
                      AND ei.invocation_text LIKE '$%'
                      AND LENGTH(ei.invocation_text) > 1
                ) usage
                JOIN mv_turn_metrics tm
                  ON tm.session_id = usage.session_id
                 AND tm.turn_id = usage.turn_id
                GROUP BY usage.skill_name
                ORDER BY total_tokens DESC, turns_with_skill DESC, usage.skill_name ASC
                LIMIT 10
            """,
            params={"session_id": session_id},
        )

    return sessions
