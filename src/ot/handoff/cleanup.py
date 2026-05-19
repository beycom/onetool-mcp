"""Age-based cleanup for handoff runtime files."""

from __future__ import annotations

import time
from pathlib import Path

from ot.handoff.models import TERMINAL_STATUSES, TaskRecord
from ot.handoff.results import read_index_entries, rewrite_index


def cleanup_old_artifacts(
    *,
    records: dict[str, TaskRecord],
    index_path: Path,
    raw_log_dir: Path,
    max_age_days: int,
) -> dict[str, int]:
    """Remove old terminal artifacts while preserving active tasks."""
    cutoff = time.time() - (max_age_days * 86400)
    removed_results = 0
    removed_raw_logs = 0
    retained_raw_logs: set[str] = set()
    stale_ids: set[str] = set()

    for task_id, record in list(records.items()):
        if (
            record.status in TERMINAL_STATUSES
            and (record.completed_at or record.submitted_at) < cutoff
        ):
            stale_ids.add(task_id)
            if record.result_path:
                path = Path(record.result_path)
                if path.exists():
                    path.unlink()
                    removed_results += 1
            if record.raw_log_path:
                path = Path(record.raw_log_path)
                if path.exists():
                    path.unlink()
                    removed_raw_logs += 1
            records.pop(task_id, None)
        elif record.raw_log_path:
            retained_raw_logs.add(record.raw_log_path)

    for row in read_index_entries(index_path):
        raw_path = row.get("raw_log_path")
        result_path = row.get("result_path")
        if result_path and Path(str(result_path)).exists() and raw_path:
            retained_raw_logs.add(str(raw_path))

    for path in raw_log_dir.glob("*.log"):
        if str(path) not in retained_raw_logs and path.stat().st_mtime < cutoff:
            path.unlink()
            removed_raw_logs += 1

    rows = [
        TaskRecord.from_dict(record.to_dict())
        for task_id, record in records.items()
        if task_id not in stale_ids
    ]
    rewrite_index(index_path, rows)
    return {"result_files": removed_results, "raw_logs": removed_raw_logs}
