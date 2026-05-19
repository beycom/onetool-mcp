"""Codex worker handoff.

Submit one focused Codex worker task, keep working, and later inspect compact
file-backed results.
"""

from __future__ import annotations

pack = "handoff"
__all__ = ["cancel", "check", "clear", "read_index", "search_index", "submit"]

__ot_requires__ = {
    "cli": [
        (
            "codex",
            "Install the Codex CLI and authenticate it, then ensure `codex app-server --listen stdio://` starts locally.",
        )
    ]
}

from typing import Any

from otpack import LogSpan, get_effective_cwd
from pydantic import ValidationError

from ot.config.loader import _expand_vars_recursive, _get_raw_config
from ot.handoff.models import Config
from ot.handoff.runtime import HandoffRuntime, get_runtime, reset_runtime


def _config() -> Config:
    raw_config = _get_raw_config("handoff")
    expanded_config = _expand_vars_recursive(raw_config)
    return Config.model_validate(expanded_config)


def _runtime() -> HandoffRuntime:
    return get_runtime(config=_config(), cwd=get_effective_cwd())


def _validation_error(error: ValidationError) -> str:
    return f"Error: invalid handoff config: {error}"


def register_services(registry: object) -> None:
    """Register handoff runtime hooks with the OneTool service registry."""
    registry.register_reload_hook(reset_runtime)  # type: ignore[attr-defined]


def submit(
    *,
    task: str,
    context: str = "",
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any] | str:
    """Submit one focused Codex worker task.

    Args:
        task: Single focused worker request.
        context: Optional extra context for the worker prompt.
        model: Codex model override. Defaults to handoff config.
        reasoning_effort: Reasoning effort override. Defaults to handoff config.
        timeout: Worker timeout in seconds. Defaults to handoff config.

    Returns:
        Task metadata including id, status, queue state, and index path.

    Example:
        handoff.submit(task="Inspect auth flow and report likely bug locations")
    """
    with LogSpan(span="handoff.submit", task=task[:80]) as s:
        try:
            result = _runtime().submit(
                task=task,
                context=context,
                model=model,
                reasoning_effort=reasoning_effort,
                timeout=timeout,
            )
        except ValidationError as e:
            return _validation_error(e)
        s.add("status", result.get("status"))
        s.add("id", result.get("id"))
        return result


def check(
    *,
    ids: list[str] | None = None,
    wait: bool = False,
    timeout: int | None = None,
) -> dict[str, Any] | str:
    """Check worker task results and outstanding queue state.

    Args:
        ids: Optional task ids to check. Omit for all outstanding/ready tasks.
        wait: If true, wait up to the capped timeout for completions.
        timeout: Requested wait timeout in seconds.

    Returns:
        Ready result summaries, file paths, queue state, and timing metadata.

    Example:
        handoff.check(wait=True, timeout=5)
    """
    with LogSpan(span="handoff.check", wait=wait) as s:
        try:
            result = _runtime().check(ids=ids, wait=wait, timeout=timeout)
        except ValidationError as e:
            return _validation_error(e)
        s.add("completedCount", result.get("completed_count"))
        s.add("remainingCount", result.get("remaining_count"))
        return result


def cancel(*, ids: list[str] | None = None) -> dict[str, Any] | str:
    """Request best-effort cancellation for outstanding handoff tasks.

    Args:
        ids: Optional task ids. Omit to target all outstanding tasks.

    Returns:
        Cancellation buckets including cancel_requested, cancel_unknown,
        already_finished, and not_found.

    Example:
        handoff.cancel(ids=["hf-abc123"])
    """
    with LogSpan(span="handoff.cancel") as s:
        try:
            result = _runtime().cancel(ids=ids)
        except ValidationError as e:
            return _validation_error(e)
        s.add("requested", len(result.get("cancel_requested", [])))
        return result


def clear(*, include_logs: bool = False) -> dict[str, Any] | str:
    """Clear handoff queue state and optionally delete runtime artifacts.

    Args:
        include_logs: When true, delete result files, raw logs, index, and state.

    Returns:
        Cleared counts and queue state.

    Example:
        handoff.clear(include_logs=True)
    """
    with LogSpan(span="handoff.clear", includeLogs=include_logs) as s:
        try:
            result = _runtime().clear(include_logs=include_logs)
        except ValidationError as e:
            return _validation_error(e)
        s.add("queueEmpty", result.get("queue_empty"))
        return result


def read_index(*, status: str | None = None, limit: int = 50) -> dict[str, Any] | str:
    """Read recent handoff index entries.

    Args:
        status: Optional exact status filter.
        limit: Maximum entries to return.

    Returns:
        Index path and recent entries.

    Example:
        handoff.read_index(status="completed", limit=10)
    """
    with LogSpan(span="handoff.read_index", status=status) as s:
        try:
            result = _runtime().read_index(status=status, limit=limit)
        except ValidationError as e:
            return _validation_error(e)
        s.add("entryCount", len(result.get("entries", [])))
        return result


def search_index(
    *,
    query: str,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any] | str:
    """Search handoff index entries with local substring matching.

    Args:
        query: Case-insensitive substring query.
        status: Optional exact status filter.
        limit: Maximum matches to return.

    Returns:
        Index path and matching entries.

    Example:
        handoff.search_index(query="auth", status="completed")
    """
    with LogSpan(span="handoff.search_index", query=query[:80]) as s:
        try:
            result = _runtime().search_index(query=query, status=status, limit=limit)
        except ValidationError as e:
            return _validation_error(e)
        s.add("matchCount", len(result.get("matches", [])))
        return result
