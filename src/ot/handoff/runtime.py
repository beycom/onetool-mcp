"""Synchronous handoff runtime orchestration."""

from __future__ import annotations

import json
import time
import uuid
from threading import Lock
from typing import TYPE_CHECKING, Any

from ot.handoff.child_proxy import ensure_child_proxy
from ot.handoff.cleanup import cleanup_old_artifacts
from ot.handoff.codex_runner import (
    CodexAppServerRunner,
    HandoffRunner,
    RunnerCompletion,
)
from ot.handoff.models import (
    Config,
    HandoffPaths,
    TaskRecord,
    make_dedupe_key,
)
from ot.handoff.results import (
    atomic_write_text,
    read_index_entries,
    ready_item,
    rewrite_index,
    write_raw_log,
    write_result_file,
)
from ot.meta import resolve_ot_path
from ot.utils.truncate import truncate

if TYPE_CHECKING:
    from pathlib import Path


class HandoffRuntime:
    """Bounded in-memory handoff task registry with file-backed results."""

    def __init__(
        self,
        *,
        config: Config,
        cwd: Path,
        runner: HandoffRunner | None = None,
    ) -> None:
        self.config = config
        self.cwd = cwd
        self.paths = HandoffPaths(
            state_path=resolve_ot_path(config.runtime.state_path),
            index_path=resolve_ot_path(config.runtime.index_path),
            result_dir=resolve_ot_path(config.runtime.result_dir),
            raw_log_dir=resolve_ot_path(config.runtime.raw_log_dir),
        )
        self._runner = runner
        self._runner_ready_until = 0.0
        self._records: dict[str, TaskRecord] = {}
        self._ready_returned: set[str] = set()
        self._lock = Lock()
        self.paths.result_dir.mkdir(parents=True, exist_ok=True)
        self.paths.raw_log_dir.mkdir(parents=True, exist_ok=True)
        self._load_state()
        if config.cleanup.enabled:
            cleanup_old_artifacts(
                records=self._records,
                index_path=self.paths.index_path,
                raw_log_dir=self.paths.raw_log_dir,
                max_age_days=config.cleanup.max_age_days,
            )
            self._save_state()

    @property
    def runner_started(self) -> bool:
        """Whether the runner object has been created."""
        return self._runner is not None

    def _new_runner(self) -> HandoffRunner:
        return CodexAppServerRunner(
            command=self.config.app_server.command,
            startup_timeout_seconds=self.config.app_server.startup_timeout_seconds,
        )

    def _ensure_runner(
        self,
        *,
        worker_env: dict[str, str] | None = None,
        mcp_config: dict[str, object] | None = None,
    ) -> HandoffRunner:
        if self._runner is None:
            self._runner = self._new_runner()
        now = time.monotonic()
        if now >= self._runner_ready_until:
            self._runner.ensure_started(worker_env=worker_env, mcp_config=mcp_config)
            self._runner_ready_until = (
                now + self.config.app_server.ready_check_cache_seconds
            )
        return self._runner

    def _load_state(self) -> None:
        if not self.paths.state_path.exists():
            return
        try:
            payload = json.loads(self.paths.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        tasks = payload.get("tasks", [])
        if not isinstance(tasks, list):
            return
        changed = False
        for item in tasks:
            if not isinstance(item, dict):
                continue
            record = TaskRecord.from_dict(item)
            if not record.terminal:
                record.status = "abandoned"
                record.completed_at = record.completed_at or time.time()
                record.summary = "Task abandoned after OneTool restart"
                changed = True
            self._records[record.id] = record
        if changed:
            rewrite_index(self.paths.index_path, list(self._records.values()))

    def _save_state(self) -> None:
        payload = {"tasks": [record.to_dict() for record in self._records.values()]}
        atomic_write_text(
            self.paths.state_path, json.dumps(payload, sort_keys=True, indent=2)
        )

    def _outstanding(self) -> list[TaskRecord]:
        return [record for record in self._records.values() if not record.terminal]

    def _running_count(self) -> int:
        return sum(1 for record in self._outstanding() if record.status == "running")

    def _queue_state(self) -> dict[str, Any]:
        outstanding = self._outstanding()
        cap = self.config.limits.max_remaining_ids_returned
        return {
            "remaining_count": len(outstanding),
            "remaining_ids": [record.id for record in outstanding[:cap]],
            "queue_empty": not outstanding,
        }

    def _poll_runner(self) -> None:
        if self._runner is None:
            return
        for completion in self._runner.poll_completed():
            self._finish_completion(completion)

    def _finish_completion(self, completion: RunnerCompletion) -> None:
        record = self._records.get(completion.task_id)
        if record is None or record.terminal:
            return
        record.status = "completed" if completion.status == "completed" else "failed"
        record.completed_at = time.time()
        record.summary = completion.summary or truncate(
            completion.body.replace("\n", " "), 400
        )
        record.error = completion.error
        raw_events = completion.raw_events
        if self.config.runtime.raw_log_enabled:
            max_bytes = self.config.limits.max_raw_log_bytes
            joined = "\n".join(raw_events)
            if len(joined.encode("utf-8")) > max_bytes:
                joined = joined.encode("utf-8")[-max_bytes:].decode(
                    "utf-8", errors="ignore"
                )
                raw_events = [joined]
            write_raw_log(record, events=raw_events, raw_log_dir=self.paths.raw_log_dir)
        write_result_file(
            record, body=completion.body, result_dir=self.paths.result_dir
        )
        rewrite_index(self.paths.index_path, list(self._records.values()))
        self._save_state()

    def _child_proxy_settings(self) -> tuple[dict[str, str], dict[str, object], str | None]:
        try:
            proxy = ensure_child_proxy()
        except RuntimeError as e:
            return {}, {}, f"Warning: MCP tools could not be enabled: {e}"
        return proxy.env, proxy.mcp_config, None

    def _start_record(self, record: TaskRecord) -> str | None:
        warning: str | None = None
        try:
            worker_env, mcp_config, warning = self._child_proxy_settings()
            runner = self._ensure_runner(
                worker_env=worker_env,
                mcp_config=mcp_config,
            )
            record.started_at = time.time()
            record.status = "running"
            record.runner_id = runner.submit(
                record,
                worker_env=worker_env,
                mcp_config=mcp_config,
            )
        except Exception as e:
            self._runner_ready_until = 0
            record.status = "failed"
            record.completed_at = time.time()
            record.error = str(e)
            record.summary = str(e)
            write_result_file(
                record, body=f"Error: {e}", result_dir=self.paths.result_dir
            )
        return warning

    def _start_queued_tasks(self) -> list[str]:
        available = self.config.limits.max_workers - self._running_count()
        if available <= 0:
            return []
        queued = [
            record
            for record in self._records.values()
            if record.status == "submitted" and not record.terminal
        ]
        warnings: list[str] = []
        for record in queued[:available]:
            warning = self._start_record(record)
            if warning is not None and warning not in warnings:
                warnings.append(warning)
        return warnings

    def submit(
        self,
        *,
        task: str,
        context: str = "",
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Submit one worker task and return immediate metadata."""
        with self._lock:
            if not self.config.enabled:
                return {"status": "error", "error": "handoff is disabled"}
            task = task.strip()
            if not task:
                return {"status": "error", "error": "task must not be empty"}
            self._poll_runner()
            if len(self._outstanding()) >= self.config.limits.max_queue_depth:
                return {
                    "status": "error",
                    "error": "handoff queue is full",
                    **self._queue_state(),
                }
            resolved_model = model or self.config.defaults.model
            resolved_effort = reasoning_effort or self.config.defaults.reasoning_effort
            resolved_timeout = timeout or self.config.defaults.timeout_seconds
            dedupe_key = make_dedupe_key(
                task=task,
                context=context,
                model=resolved_model,
                reasoning_effort=resolved_effort,
            )
            now = time.time()
            for record in self._outstanding():
                if (
                    record.dedupe_key == dedupe_key
                    and now - record.submitted_at
                    <= self.config.runtime.dedupe_window_seconds
                ):
                    return {
                        "id": record.id,
                        "status": "submitted",
                        "deduped": True,
                        "model": record.model,
                        "reasoning_effort": record.reasoning_effort,
                        "timeout_seconds": record.timeout_seconds,
                        **self._queue_state(),
                    }
            prompt = self.config.defaults.worker_prompt.format(
                task=task, context=context
            )
            record = TaskRecord(
                id=f"hf-{uuid.uuid4().hex[:12]}",
                task=task,
                context=context,
                model=resolved_model,
                reasoning_effort=resolved_effort,
                timeout_seconds=resolved_timeout,
                prompt=prompt,
                cwd=str(self.cwd),
                dedupe_key=dedupe_key,
            )
            self._records[record.id] = record
            warnings = self._start_queued_tasks()
            rewrite_index(self.paths.index_path, list(self._records.values()))
            self._save_state()
            return {
                "id": record.id,
                "status": "submitted" if not record.terminal else record.status,
                "deduped": False,
                "model": record.model,
                "reasoning_effort": record.reasoning_effort,
                "timeout_seconds": record.timeout_seconds,
                "index_path": str(self.paths.index_path),
                "warnings": warnings,
                **self._queue_state(),
            }

    def check(
        self,
        *,
        ids: list[str] | None = None,
        wait: bool = False,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Check ready task summaries and outstanding state."""
        start = time.time()
        requested = set(ids or [])
        effective_timeout = 0
        if wait:
            desired = (
                self.config.limits.max_check_wait_seconds
                if timeout is None
                else timeout
            )
            effective_timeout = min(desired, self.config.limits.max_check_wait_seconds)
        timed_out = False
        with self._lock:
            self._poll_runner()
            self._start_queued_tasks()
            while True:
                if wait:
                    self._poll_runner()
                    self._start_queued_tasks()
                ready = [
                    record
                    for record in self._records.values()
                    if record.terminal
                    and record.id not in self._ready_returned
                    and (not requested or record.id in requested)
                ]
                if ready or not wait:
                    break
                if time.time() - start >= effective_timeout:
                    timed_out = True
                    break
                time.sleep(0.05)
            ready_items = [ready_item(record) for record in ready]
            for record in ready:
                self._ready_returned.add(record.id)
            unknown = sorted(requested - set(self._records))
            self._save_state()
            state = self._queue_state()
            return {
                "ready": ready_items,
                "completed_count": len(ready_items),
                "remaining_count": state["remaining_count"],
                "remaining_ids": state["remaining_ids"],
                "queue_empty": state["queue_empty"],
                "timed_out": timed_out,
                "unknown_ids": unknown,
                "index_path": str(self.paths.index_path),
                "check_duration_seconds": round(time.time() - start, 3),
            }

    def cancel(self, *, ids: list[str] | None = None) -> dict[str, Any]:
        """Request best-effort cancellation."""
        with self._lock:
            targets = (
                self._outstanding()
                if ids is None
                else [
                    self._records[task_id]
                    for task_id in ids
                    if task_id in self._records and not self._records[task_id].terminal
                ]
            )
            requested: list[str] = []
            unknown: list[str] = []
            cancelled: list[str] = []
            already_finished: list[str] = []
            not_found: list[str] = []
            for task_id in ids or []:
                record = self._records.get(task_id)
                if record is None:
                    not_found.append(task_id)
                elif record.terminal:
                    already_finished.append(task_id)
            runner = self._runner
            for record in targets:
                outcome = "cancel_unknown"
                if runner is not None and record.runner_id:
                    outcome = runner.cancel(record.runner_id)
                if outcome == "cancelled":
                    record.status = "cancelled"
                    record.completed_at = time.time()
                    record.summary = "Task cancelled"
                    cancelled.append(record.id)
                    write_result_file(
                        record, body="Task cancelled.", result_dir=self.paths.result_dir
                    )
                else:
                    record.status = "cancel_requested"
                    requested.append(record.id)
                    unknown.append(record.id)
            rewrite_index(self.paths.index_path, list(self._records.values()))
            self._save_state()
            return {
                "cancel_requested": requested,
                "cancelled": cancelled,
                "cancel_unknown": unknown,
                "already_finished": already_finished,
                "not_found": not_found,
                **self._queue_state(),
            }

    def clear(self, *, include_logs: bool = False) -> dict[str, Any]:
        """Clear in-memory queue state and optionally delete runtime artifacts."""
        with self._lock:
            outstanding = len(self._outstanding())
            for record in self._outstanding():
                record.status = "cleared"
                record.completed_at = time.time()
                record.summary = "Task cleared"
            self._records.clear()
            self._ready_returned.clear()
            if self._runner is not None:
                self._runner.clear()
            deleted = {"result_files": 0, "raw_logs": 0, "index": 0, "state": 0}
            if include_logs:
                for path in self.paths.result_dir.glob("*.md"):
                    path.unlink()
                    deleted["result_files"] += 1
                for path in self.paths.raw_log_dir.glob("*.log"):
                    path.unlink()
                    deleted["raw_logs"] += 1
                for key, path in (
                    ("index", self.paths.index_path),
                    ("state", self.paths.state_path),
                ):
                    if path.exists():
                        path.unlink()
                        deleted[key] += 1
            else:
                self._save_state()
            return {
                "cleared_outstanding": outstanding,
                "deleted": deleted,
                "queue_empty": True,
            }

    def read_index(
        self, *, status: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        """Read recent index entries without starting the runner."""
        cap = min(max(limit, 0), 500)
        rows = read_index_entries(self.paths.index_path)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows = sorted(
            rows,
            key=lambda row: str(
                row.get("completed_at") or row.get("submitted_at") or ""
            ),
            reverse=True,
        )
        return {"index_path": str(self.paths.index_path), "entries": rows[:cap]}

    def search_index(
        self,
        *,
        query: str,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search index rows locally without starting the runner."""
        q = query.lower()
        rows = self.read_index(status=status, limit=500)["entries"]
        matches = []
        for row in rows:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("id", "status", "task", "summary", "result_path")
            ).lower()
            if q in haystack:
                matches.append(row)
        cap = min(max(limit, 0), 200)
        return {"index_path": str(self.paths.index_path), "matches": matches[:cap]}


_runtime: HandoffRuntime | None = None


def get_runtime(*, config: Config, cwd: Path) -> HandoffRuntime:
    """Return the process-global handoff runtime."""
    global _runtime
    if _runtime is None:
        _runtime = HandoffRuntime(config=config, cwd=cwd)
    return _runtime


def reset_runtime() -> None:
    """Reset the process-global runtime and runner-side transient state."""
    global _runtime
    if _runtime is not None and _runtime._runner is not None:
        _runtime._runner.clear()
    _runtime = None
