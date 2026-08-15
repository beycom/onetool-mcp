"""Run fresh workers with strict named project-local Contexts."""

from __future__ import annotations

pack = "worker"

__all__ = ["archive_context", "list_contexts", "run", "select", "update_context"]

import os
import threading
from datetime import UTC, datetime
from secrets import token_hex
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from ot.config import get_tool_config
from ot.logging import LogSpan
from ot.paths import get_effective_cwd
from ottools._worker.app_server import AdapterOutcome, AppServerAdapter
from ottools._worker.context import ContextError, ContextStore
from ottools._worker.lifecycle import (
    ConsoleObserver,
    HistoryError,
    HistoryStore,
    ObservationError,
    classify_changes,
    project_fingerprint,
)
from ottools._worker.models import (
    STATUS_MAX_BYTES,
    HistoryRecord,
    InternalTerminalOutput,
    ModelId,
    NonBlank,
    PublicWorkerResult,
)

_WORKER_ENV = "OT_EPISODIC_WORKER"
_ACTIVE_LOCK = threading.Lock()


class Config(BaseModel):
    """Strict worker model, effort, and Context-size configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: ModelId | None = None
    effort: NonBlank | None = None
    context_max_kb: Annotated[StrictInt, Field(gt=0)] = 16


def _get_config() -> Config:
    return get_tool_config("worker", Config)


def _selection(
    explicit: str | None, configured: str | None, *, name: str
) -> str | None:
    value = explicit if explicit is not None else configured
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    if any(ord(character) < 0x20 for character in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _safe_context_name(value: str | None) -> str:
    if value is None:
        return "default"
    return value if value.strip() else "unavailable"


def _clip_utf8(value: str, maximum: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum:
        return value
    suffix = "…".encode()
    clipped = encoded[: maximum - len(suffix)]
    while clipped:
        try:
            return clipped.decode("utf-8") + "…"
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return "…"


def _status_message(message: str, *, warnings: tuple[str, ...] = ()) -> str:
    value = message.strip() or "Worker returned no Status message."
    if warnings:
        value = f"{value} [warnings: {', '.join(warnings)}]"
    return _clip_utf8(value, STATUS_MAX_BYTES)


def _public_result(
    *,
    context: str,
    status: str,
    message: str,
    warnings: tuple[str, ...] = (),
) -> dict[str, str]:
    result = PublicWorkerResult.model_validate(
        {
            "context": _safe_context_name(context),
            "status": status,
            "message": _status_message(message, warnings=warnings),
        }
    )
    return {key: str(value) for key, value in result.model_dump().items()}


def _operation_error(*, status: str, error: str) -> dict[str, object]:
    return {
        "ok": False,
        "status": status,
        "error": _clip_utf8(error, STATUS_MAX_BYTES),
    }


def _store() -> ContextStore:
    return ContextStore(context_max_kb=_get_config().context_max_kb)


def _recursive_error() -> dict[str, object] | None:
    if os.getenv(_WORKER_ENV) != "1":
        return None
    return _operation_error(
        status="recursive_worker_operation",
        error="worker operations cannot be called from an episodic worker",
    )


def select(*, context: str) -> dict[str, object]:
    """Create or validate a named active Context for caller-owned selection.

    Args:
        context: Lowercase Context slug to create or select.

    Returns:
        A bounded receipt containing the Context name and creation indicator.
    """
    with LogSpan(span="worker.select", context=context) as span:
        if error := _recursive_error():
            return error
        try:
            loaded, created = _store().load(context, create=True)
            span.add(created=created)
            return {"ok": True, "context": loaded.name, "created": created}
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="context_select_failed", error=str(exc))


def list_contexts(
    *, status: Literal["active", "archived"] | None = None
) -> dict[str, object]:
    """List validated Context frontmatter without semantic bodies.

    Args:
        status: Optional active or archived filter.

    Returns:
        Stable body-free Context metadata.
    """
    with LogSpan(span="worker.list_contexts", status=status) as span:
        if error := _recursive_error():
            return error
        try:
            items = [
                item.model_dump(mode="json")
                for item in _store().list_contexts(status=status)
            ]
            span.add(resultCount=len(items))
            return {"ok": True, "contexts": items}
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="context_list_failed", error=str(exc))


def update_context(
    *,
    context: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    """Create a Context or replace only its supplied discoverable metadata.

    Args:
        context: Lowercase Context slug to update.
        description: Complete replacement description; empty clears it.
        tags: Complete replacement ordered tag list; empty clears it.

    Returns:
        Updated body-free metadata and creation indicator.
    """
    with LogSpan(span="worker.update_context", context=context) as span:
        if error := _recursive_error():
            return error
        try:
            loaded, created = _store().update_metadata(
                context,
                description=description,
                tags=tags,
            )
            span.add(created=created, revision=loaded.metadata.revision)
            return {
                "ok": True,
                "context": loaded.name,
                "created": created,
                "description": loaded.metadata.description,
                "tags": loaded.metadata.tags,
                "status": loaded.metadata.status,
                "revision": loaded.metadata.revision,
            }
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="context_update_failed", error=str(exc))


def archive_context(*, context: str) -> dict[str, object]:
    """Archive one active non-default Context without deleting or moving it.

    Args:
        context: Existing active Context slug.

    Returns:
        A bounded receipt containing the Context name and archived status.
    """
    with LogSpan(span="worker.archive_context", context=context) as span:
        if error := _recursive_error():
            return error
        try:
            loaded = _store().archive(context)
            span.add(revision=loaded.metadata.revision)
            return {"ok": True, "context": loaded.name, "status": "archived"}
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="context_archive_failed", error=str(exc))


def run(
    *,
    prompt: str,
    context: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, str]:
    """Run one fresh non-interactive worker episode with a named Context.

    Args:
        prompt: Current user request or required-input answer.
        context: Named Context for this episode; defaults to ``default``.
        model: Optional direct Codex model override.
        effort: Optional installed Codex reasoning-effort override.

    Returns:
        Exactly ``context``, ``status``, and bounded ``message``. Status is
        ``completed``, ``needs_input``, ``failed``, or ``interrupted``.

    Example:
        worker.run(prompt="Implement the approved change.", context="feature-x")
    """
    effective_context = "default" if context is None else context
    with LogSpan(span="worker.run", context=effective_context) as span:
        if os.getenv(_WORKER_ENV) == "1":
            return _public_result(
                context=effective_context,
                status="failed",
                message="worker operations cannot be called from an episodic worker",
            )
        if not _ACTIVE_LOCK.acquire(blocking=False):
            return _public_result(
                context=effective_context,
                status="failed",
                message="another worker.run call is already active",
            )

        try:
            if not prompt.strip():
                raise ValueError("prompt must not be blank")
            config = _get_config()
            selected_model = _selection(model, config.model, name="model")
            selected_effort = _selection(effort, config.effort, name="effort")
            project_root = get_effective_cwd().resolve()
            if not project_root.is_dir():
                raise ValueError(
                    f"current project directory does not exist: {project_root}"
                )
            store = ContextStore(context_max_kb=config.context_max_kb)
            loaded, _created = store.load(effective_context, create=True)
            revision_before = loaded.metadata.revision
            baseline = project_fingerprint(project_root)
            console_observer = ConsoleObserver(project_root=project_root)
            console_observer.capture_before()
            episode_id = f"episode-{token_hex(16)}"
            started_at = datetime.now(UTC)

            def commit_terminal(terminal: InternalTerminalOutput) -> None:
                nonlocal loaded
                if terminal.context is not None:
                    loaded = store.commit_body(loaded=loaded, body=terminal.context)

            outcome: AdapterOutcome = AppServerAdapter().run_episode(
                prompt=prompt,
                context=loaded.body,
                cwd=str(project_root),
                model=selected_model,
                effort=selected_effort,
                on_terminal=commit_terminal,
                before_close=console_observer.capture_current,
            )
            warnings = list(outcome.warnings)
            console_observer.capture_current()
            if console_observer.warning is not None:
                warnings.append(console_observer.warning)

            local_changes = []
            try:
                local_changes = classify_changes(
                    baseline,
                    project_fingerprint(project_root),
                )
            except ObservationError:
                warnings.append("local_changes_observation_failed")

            try:
                current, _ = store.load(
                    loaded.name,
                    create=False,
                    require_active=False,
                )
                revision_after = current.metadata.revision
            except ContextError:
                revision_after = loaded.metadata.revision
                warnings.append("context_revision_observation_failed")

            if outcome.started:
                history = HistoryRecord(
                    episode_id=episode_id,
                    context=loaded.name,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    status=outcome.status,
                    turn_count=outcome.turn_count,
                    context_revision_before=revision_before,
                    context_revision_after=revision_after,
                    console=console_observer.created(),
                    local_changes=local_changes,
                    failure="episode_failed" if outcome.status == "failed" else None,
                    warnings=warnings,
                )
                try:
                    HistoryStore(state_root=store.state_root).append(history)
                except HistoryError:
                    warnings.append("history_append_failed")

            span.add(status=outcome.status)
            return _public_result(
                context=loaded.name,
                status=outcome.status,
                message=outcome.message,
                warnings=tuple(warnings),
            )
        except (
            ContextError,
            ObservationError,
            ValidationError,
            ValueError,
            OSError,
        ) as exc:
            span.add(status="failed", errorType=type(exc).__name__)
            return _public_result(
                context=effective_context,
                status="failed",
                message=str(exc),
            )
        finally:
            _ACTIVE_LOCK.release()
