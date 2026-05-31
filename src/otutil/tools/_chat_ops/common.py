"""Shared report query helpers for chat_ops report modes."""

from __future__ import annotations

from typing import Any, Protocol


class ReportRequest(Protocol):
    """Minimal request shape used by report mode executors."""

    group_by: str | None
    project: str | None
    session_id: str | None
    model: str | None
    start: str | None
    end: str | None
    min_samples: int
    limit: int


def query_rows(
    conn: Any,
    *,
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run query and materialize rows as dictionaries."""
    cur = conn.execute(sql, dict(params))
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({key: row[idx] for idx, key in enumerate(cols)})
    return out


def add_common_filters(
    where: list[str],
    params: dict[str, Any],
    *,
    project_col: str | None,
    session_col: str | None,
    model_col: str | None,
    ts_col: str | None,
    req: ReportRequest,
) -> None:
    """Append common WHERE clauses for standard report filters."""
    if req.project and project_col:
        where.append(f"{project_col} = :project")
        params["project"] = req.project
    if req.session_id and session_col:
        where.append(f"{session_col} = :session_id")
        params["session_id"] = req.session_id
    if req.model and model_col:
        where.append(f"{model_col} = :model")
        params["model"] = req.model
    if req.start and ts_col:
        where.append(f"{ts_col} >= :start")
        params["start"] = req.start
    if req.end and ts_col:
        where.append(f"{ts_col} <= :end")
        params["end"] = req.end


def group_expr(*, group_by: str, ts_col: str = "turn_started_at") -> str:
    """Resolve timestamp bucketing aliases used by report group_by."""
    if group_by == "day":
        return f"substr({ts_col}, 1, 10)"
    if group_by == "week":
        return f"strftime('%Y-%W', {ts_col})"
    if group_by == "month":
        return f"substr({ts_col}, 1, 7)"
    return group_by
