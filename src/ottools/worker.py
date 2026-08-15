"""Run one fresh Codex worker episode with small validated continuation state."""

from __future__ import annotations

pack = "worker"

__all__ = ["run"]

import os
import threading
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from ot.config import get_tool_config
from ot.logging import LogSpan
from ot.paths import get_effective_cwd
from ottools._worker.app_server import AppServerAdapter
from ottools._worker.context import ContextError, ContextStore
from ottools._worker.models import (
    ExecutionPolicy,
    InternalTerminalOutput,
    ModelId,
    NonBlank,
    PublicWorkerResult,
)

_WORKER_ENV = "OT_EPISODIC_WORKER"
_ACTIVE_LOCK = threading.Lock()


class Config(BaseModel):
    """Strict worker model, effort, and context-size configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: ModelId | None = None
    effort: NonBlank | None = None
    context_max_kb: Annotated[StrictInt, Field(gt=0)] = 16


def _get_config() -> Config:
    return get_tool_config("worker", Config)


def _selection(explicit: str | None, configured: str | None, *, name: str) -> str | None:
    value = explicit if explicit is not None else configured
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    if any(ord(character) < 0x20 for character in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _public_result(
    *,
    session_id: str,
    status: str,
    message: str,
) -> dict[str, str]:
    result = PublicWorkerResult.model_validate(
        {"session_id": session_id, "status": status, "message": message}
    )
    return {key: str(value) for key, value in result.model_dump().items()}


def _prepare_session(store: ContextStore, session_id: str | None) -> str:
    if session_id is None:
        return store.create_session()
    store.require_session(session_id)
    return session_id


def _validate_execution(value: dict[str, Any]) -> ExecutionPolicy:
    execution = ExecutionPolicy.model_validate(value)
    cwd = Path(execution.cwd)
    if not cwd.is_absolute():
        raise ValueError("execution.cwd must be absolute")
    if not cwd.is_dir():
        raise ValueError(f"execution.cwd is not an existing directory: {execution.cwd}")
    effective = get_effective_cwd().resolve()
    if cwd.resolve() != effective:
        raise ValueError(
            f"execution.cwd must equal the current project directory: {effective}"
        )
    return execution.model_copy(update={"cwd": str(effective)})


def run(
    *,
    prompt: str,
    execution: dict[str, Any],
    session_id: str | None = None,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, str]:
    """Run one fresh non-interactive Codex worker episode.

    Args:
        prompt: Current user request or answer for the worker.
        execution: Exact object containing absolute current-project ``cwd``,
            ``approval_policy='never'``, and ``sandbox`` set to ``read-only`` or
            ``workspace-write``. Network access is always disabled.
        session_id: Omit for the first episode; reuse the returned ID for follow-ups.
        model: Optional direct Codex model override.
        effort: Optional installed Codex reasoning-effort override.

    Returns:
        Exactly ``session_id``, ``status``, and ``message``. Status is
        ``completed``, ``needs_input``, ``failed``, or ``interrupted``.

    Example:
        worker.run(
            prompt="Implement the approved change.",
            execution={
                "cwd": "/project",
                "approval_policy": "never",
                "sandbox": "workspace-write",
            },
        )
    """
    with LogSpan(span="worker.run", hasSession=session_id is not None) as span:
        try:
            config = _get_config()
        except ValueError as exc:
            fallback = ContextStore(context_max_kb=16)
            try:
                resolved_session = _prepare_session(fallback, session_id)
            except ContextError:
                resolved_session = session_id or fallback.create_session()
            return _public_result(
                session_id=resolved_session,
                status="failed",
                message=str(exc),
            )

        store = ContextStore(context_max_kb=config.context_max_kb)
        try:
            resolved_session = _prepare_session(store, session_id)
        except ContextError as exc:
            return _public_result(
                session_id=session_id or "unavailable",
                status="failed",
                message=str(exc),
            )

        if os.getenv(_WORKER_ENV) == "1":
            return _public_result(
                session_id=resolved_session,
                status="failed",
                message="worker.run cannot be called from an episodic worker",
            )
        if not _ACTIVE_LOCK.acquire(blocking=False):
            return _public_result(
                session_id=resolved_session,
                status="failed",
                message="another worker.run call is already active",
            )

        try:
            if not prompt.strip():
                raise ValueError("prompt must not be blank")
            policy = _validate_execution(execution)
            selected_model = _selection(model, config.model, name="model")
            selected_effort = _selection(effort, config.effort, name="effort")
            loaded = store.preflight(resolved_session)

            def commit_terminal(terminal: InternalTerminalOutput) -> None:
                if terminal.context is not None:
                    store.commit(
                        session_id=resolved_session,
                        loaded_revision=loaded.revision,
                        context=terminal.context,
                    )

            outcome = AppServerAdapter().run_episode(
                prompt=prompt,
                context=loaded.value,
                execution=policy,
                model=selected_model,
                effort=selected_effort,
                on_terminal=commit_terminal,
            )
            span.add(status=outcome.status)
            return _public_result(
                session_id=resolved_session,
                status=outcome.status,
                message=outcome.message,
            )
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(status="failed", errorType=type(exc).__name__)
            return _public_result(
                session_id=resolved_session,
                status="failed",
                message=str(exc),
            )
        finally:
            _ACTIVE_LOCK.release()
