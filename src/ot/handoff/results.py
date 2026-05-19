"""Result spool and index helpers for handoff."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ot.utils.truncate import truncate

if TYPE_CHECKING:
    from ot.handoff.models import TaskRecord


def iso_ts(value: float | None) -> str | None:
    """Format a unix timestamp as UTC ISO text."""
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def duration(start: float | None, end: float | None) -> float | None:
    """Return rounded duration seconds when both endpoints exist."""
    if start is None or end is None:
        return None
    return round(max(0.0, end - start), 3)


def atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically beside the destination path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        Path(tmp_name).replace(path)
    finally:
        tmp = Path(tmp_name)
        if tmp.exists():
            tmp.unlink()


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def index_entry(record: TaskRecord) -> dict[str, Any]:
    """Return the compact JSONL/index representation for a task."""
    return {
        "id": record.id,
        "status": record.status,
        "task": record.task,
        "summary": record.summary,
        "result_path": record.result_path,
        "raw_log_path": record.raw_log_path,
        "model": record.model,
        "submitted_at": iso_ts(record.submitted_at),
        "started_at": iso_ts(record.started_at),
        "completed_at": iso_ts(record.completed_at),
        "submit_to_start_seconds": duration(record.submitted_at, record.started_at),
        "run_seconds": duration(record.started_at, record.completed_at),
    }


def ready_item(record: TaskRecord) -> dict[str, Any]:
    """Return a path-and-summary ready item for check()."""
    now = time.time()
    record.checked_at = now
    item = index_entry(record)
    item["checked_at"] = iso_ts(now)
    item["completed_to_checked_seconds"] = duration(record.completed_at, now)
    return item


def write_result_file(record: TaskRecord, *, body: str, result_dir: Path) -> Path:
    """Write one Markdown result file with YAML frontmatter."""
    result_path = result_dir / f"{record.id}.md"
    summary = record.summary or truncate(body.strip().replace("\n", " "), 400)
    record.summary = summary
    fields = {
        "id": record.id,
        "status": record.status,
        "task": record.task,
        "summary": summary,
        "model": record.model,
        "submitted_at": iso_ts(record.submitted_at),
        "started_at": iso_ts(record.started_at),
        "completed_at": iso_ts(record.completed_at),
        "submit_to_start_seconds": duration(record.submitted_at, record.started_at),
        "run_seconds": duration(record.started_at, record.completed_at),
        "raw_log_path": record.raw_log_path,
    }
    frontmatter = "\n".join(
        f"{key}: {_yaml_scalar(value)}" for key, value in fields.items()
    )
    atomic_write_text(result_path, f"---\n{frontmatter}\n---\n\n{body.strip()}\n")
    record.result_path = str(result_path)
    return result_path


def write_raw_log(
    record: TaskRecord, *, events: list[str], raw_log_dir: Path
) -> Path | None:
    """Flush buffered raw events for a task."""
    if not events:
        return None
    path = raw_log_dir / f"{record.id}.log"
    atomic_write_text(path, "\n".join(events) + "\n")
    record.raw_log_path = str(path)
    return path


def read_index_entries(index_path: Path) -> list[dict[str, Any]]:
    """Read index rows, treating a missing index as empty."""
    if not index_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def rewrite_index(index_path: Path, records: list[TaskRecord]) -> None:
    """Atomically rewrite JSONL index rows."""
    rows = [json.dumps(index_entry(record), sort_keys=True) for record in records]
    atomic_write_text(index_path, "\n".join(rows) + ("\n" if rows else ""))
