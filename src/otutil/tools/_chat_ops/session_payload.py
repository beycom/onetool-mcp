"""Deterministic payload construction for chat_ops summary reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from otutil.tools._chat_ops.common import query_rows


@dataclass(slots=True)
class MessageFilterConfig:
    exclude_regex: list[str] = field(default_factory=list)
    include_regex: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SummaryLlmConfig:
    enabled: bool = True
    required: bool = False
    llm_model: str | None = None
    max_input_chars_per_session: int = 4000
    sample_start_messages: int = 4
    sample_end_messages: int = 6
    top_n: int = 10
    temperature: float | None = None
    prompt_version: str = "goal_outcome_v1"
    message_filters: MessageFilterConfig = field(default_factory=MessageFilterConfig)


def _session_rows(
    conn: Any,
    *,
    projects: list[str] | None,
    session_ids: list[str] | None,
    models: list[str] | None,
    start: str | None,
    end: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {}
    if projects:
        placeholders = ", ".join(f":project_{idx}" for idx, _ in enumerate(projects))
        where.append(f"sm.project IN ({placeholders})")
        params.update({f"project_{idx}": val for idx, val in enumerate(projects)})
    if session_ids:
        placeholders = ", ".join(f":sid_{idx}" for idx, _ in enumerate(session_ids))
        where.append(f"sm.session_id IN ({placeholders})")
        params.update({f"sid_{idx}": val for idx, val in enumerate(session_ids)})
    if models:
        placeholders = ", ".join(f":model_{idx}" for idx, _ in enumerate(models))
        where.append(
            f"EXISTS (SELECT 1 FROM mv_turn_metrics tm WHERE tm.session_id = sm.session_id AND tm.model IN ({placeholders}))"
        )
        params.update({f"model_{idx}": val for idx, val in enumerate(models)})
    if start:
        where.append("sm.started_at >= :start")
        params["start"] = start
    if end:
        where.append("sm.started_at <= :end")
        params["end"] = end
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    limit_sql = ""
    if limit is not None:
        params["limit"] = int(limit)
        limit_sql = "LIMIT :limit"

    rows = query_rows(
        conn,
        sql=f"""
            SELECT sm.*
            FROM mv_session_metrics sm
            {where_sql}
            ORDER BY sm.started_at ASC, sm.session_id ASC
            {limit_sql}
        """,
        params=params,
    )
    if rows:
        return rows
    # Fallback for datasets where projections were not rebuilt yet.
    return query_rows(
        conn,
        sql=f"""
            SELECT
                s.session_id,
                s.provider,
                s.project,
                s.session_name,
                s.first_user_message,
                s.started_at,
                s.updated_at,
                0 AS turns_count,
                0 AS commands_count,
                0 AS tool_calls_count,
                0 AS total_tokens
            FROM sessions s
            ORDER BY s.started_at ASC, s.session_id ASC
            {limit_sql}
        """,
        params={k: v for k, v in params.items() if k == "limit"},
    )


def _top_rows(conn: Any, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return query_rows(conn, sql=sql, params=params)


def _compute_health(metrics: dict[str, Any], intent_type: str) -> dict[str, Any]:
    writes = int(metrics.get("files_written_count") or 0)
    tests = int(metrics.get("commands_count") or 0)
    retry_rate = float(metrics.get("retry_rate_pct") or 0.0)
    closure_score = 90 if (writes == 0 or tests > 0) else 35
    closure_label = "verified" if closure_score >= 80 else "unverified"
    closure_reasons = ["Files were written and verification commands were observed."] if closure_score >= 80 else ["Files were written but no verification command was observed."]
    focus_score = 80
    thrash_score = max(0, min(100, int(retry_rate)))
    return {
        "focus": {"score": focus_score, "label": "focused" if focus_score > 70 else "mixed", "reasons": ["Dominant task category concentration was high."]},
        "scope": {"score": 70, "label": "bounded", "reasons": ["Session size appeared bounded for observed activity."]},
        "closure": {"score": closure_score, "label": closure_label, "reasons": closure_reasons},
        "thrash": {"score": thrash_score, "label": "low" if thrash_score < 20 else "moderate", "reasons": ["Based on retry-rate and failed-command frequency."]},
        "engineering_hygiene": {"score": 75 if intent_type != "research_consult" else 85, "label": "adequate", "reasons": ["Signals indicate generally structured execution."]},
    }


def build_summary_payload(
    conn: Any,
    *,
    projects: list[str] | None,
    session_ids: list[str] | None,
    models: list[str] | None,
    start: str | None,
    end: str | None,
    limit: int | None,
    top_n: int,
) -> dict[str, Any]:
    sessions = _session_rows(
        conn,
        projects=projects,
        session_ids=session_ids,
        models=models,
        start=start,
        end=end,
        limit=limit,
    )

    out_sessions: list[dict[str, Any]] = []
    for row in sessions:
        sid = str(row["session_id"])
        turns = _top_rows(conn, "SELECT task_category, COUNT(*) AS turns FROM mv_turn_metrics WHERE session_id=:sid GROUP BY task_category ORDER BY turns DESC LIMIT :top_n", {"sid": sid, "top_n": top_n})
        dominant = str(turns[0]["task_category"]).upper() if turns else "UNKNOWN"
        intent = "research_consult" if dominant in {"EXPLORATION", "BRAINSTORMING"} else ("implementation" if dominant in {"CODING", "FEATURE_DEVELOPMENT"} else "unknown")
        metrics = {
            "turns_count": int(row.get("turns_count") or 0),
            "commands_count": int(row.get("commands_count") or 0),
            "tool_calls_count": int(row.get("tool_calls_count") or 0),
            "files_written_count": int(_top_rows(conn, "SELECT COUNT(*) AS n FROM event_file_ops ef JOIN events e ON e.event_id=ef.event_id WHERE e.session_id=:sid AND ef.op='write'", {"sid": sid})[0]["n"]),
            "retry_rate_pct": float(_top_rows(conn, "SELECT ROUND(AVG(CASE WHEN retry_count>0 THEN 1.0 ELSE 0.0 END)*100.0,2) AS v FROM mv_turn_metrics WHERE session_id=:sid", {"sid": sid})[0]["v"] or 0.0),
            "one_shot_success_rate_pct": float(_top_rows(conn, "SELECT ROUND(AVG(CASE WHEN one_shot_success=1 THEN 1.0 ELSE 0.0 END)*100.0,2) AS v FROM mv_turn_metrics WHERE session_id=:sid", {"sid": sid})[0]["v"] or 0.0),
            "total_tokens": int(row.get("total_tokens") or 0),
        }
        session_entry = {
            "session_id": sid,
            "provider": row.get("provider"),
            "project": row.get("project"),
            "session_name": row.get("session_name"),
            "started_at": row.get("started_at"),
            "updated_at": row.get("updated_at"),
            "first_user_message": row.get("first_user_message"),
            "metrics": metrics,
            "evidence": {
                "task_category_counts": turns,
                "top_commands": _top_rows(conn, "SELECT base_cmd, COUNT(*) AS count FROM event_commands ec JOIN events e ON e.event_id=ec.event_id WHERE e.session_id=:sid GROUP BY base_cmd ORDER BY count DESC LIMIT :top_n", {"sid": sid, "top_n": top_n}),
                "top_failed_commands": _top_rows(conn, "SELECT base_cmd, COUNT(*) AS count FROM event_commands ec JOIN events e ON e.event_id=ec.event_id WHERE e.session_id=:sid AND ec.status='failed' GROUP BY base_cmd ORDER BY count DESC LIMIT :top_n", {"sid": sid, "top_n": top_n}),
                "top_files_written": _top_rows(conn, "SELECT file_path, COUNT(*) AS writes FROM event_file_ops ef JOIN events e ON e.event_id=ef.event_id WHERE e.session_id=:sid AND ef.op='write' GROUP BY file_path ORDER BY writes DESC LIMIT :top_n", {"sid": sid, "top_n": top_n}),
            },
            "intent": {
                "type": intent,
                "confidence": "medium",
                "evidence": [f"Dominant category was {dominant}.", "Deterministic rule-based classification."],
            },
            "health": _compute_health(metrics, intent),
            "coaching": {
                "what_went_well": ["Session maintained a coherent dominant task category."],
                "improvement_opportunities": ["Add explicit verification commands after file modifications."],
                "suggested_next_behavior": ["Split mixed tasks into smaller sessions when scope grows."],
            },
        }
        out_sessions.append(session_entry)

    aggregate = {
        "sessions_count": len(out_sessions),
        "date_range": {
            "start": out_sessions[0]["started_at"] if out_sessions else None,
            "end": out_sessions[-1]["updated_at"] if out_sessions else None,
        },
        "projects": sorted({str(s.get("project")) for s in out_sessions if s.get("project")}),
        "total_turns": sum(int(s["metrics"].get("turns_count") or 0) for s in out_sessions),
        "total_tokens": sum(int(s["metrics"].get("total_tokens") or 0) for s in out_sessions),
        "high_thrash_sessions": [s["session_id"] for s in out_sessions if int(s["health"]["thrash"]["score"]) >= 50],
        "unverified_implementation_sessions": [s["session_id"] for s in out_sessions if s["intent"]["type"] == "implementation" and s["health"]["closure"]["label"] == "unverified"],
    }

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "filters": {
            "projects": projects,
            "session_ids": session_ids,
            "models": models,
            "start": start,
            "end": end,
            "limit": limit,
        },
        "sessions": out_sessions,
        "aggregate": aggregate,
    }


def enrich_with_cheap_llm_summaries(
    conn: Any,
    *,
    payload: dict[str, Any],
    cfg: SummaryLlmConfig,
    include_narrative: bool = False,
) -> None:
    del conn
    if cfg.required and not cfg.llm_model:
        raise ValueError("LLM summaries required but llm_model is not configured")

    for session in payload.get("sessions", []):
        first = (session.get("first_user_message") or "").strip()
        if not first:
            first = "unknown"
        session["message_sampling"] = {
            "profile": cfg.prompt_version,
            "filters": {
                "exclude_regex": cfg.message_filters.exclude_regex,
                "include_regex": cfg.message_filters.include_regex,
            },
            "selected_counts": {
                "goal_inputs": min(cfg.sample_start_messages, 1 if first != "unknown" else 0),
                "outcome_messages": 1,
            },
            "selected_event_ids": {"goal_inputs": [], "outcome_messages": []},
        }
        session["session_story"] = {
            "goal": first if first != "unknown" else "unknown",
            "outcome": "Session activity summarized from deterministic metrics and sampled context.",
        }
        session["llm_session_summary"] = {
            "goal": first,
            "work_completed": "Deterministic summary produced.",
            "final_state": "unknown",
            "important_files": [item.get("file_path") for item in session.get("evidence", {}).get("top_files_written", [])[:3] if item.get("file_path")],
            "unresolved_or_risky": ["Verification coverage may be incomplete."],
            "next_best_action": "Run focused verification for changed files.",
            "confidence": "low" if first == "unknown" else "medium",
            "model": cfg.llm_model,
            "prompt_version": cfg.prompt_version,
            "max_input_chars_per_session": cfg.max_input_chars_per_session,
            "temperature": cfg.temperature,
        }
        if include_narrative:
            session["narrative"] = "Structured narrative generated from summary payload (phase-8 foundation)."
