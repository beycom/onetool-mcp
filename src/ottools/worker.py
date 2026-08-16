"""Run fresh workers with strict named project-local Contexts."""

from __future__ import annotations

pack = "worker"

__all__ = [
    "asset_create",
    "asset_delete",
    "asset_list",
    "asset_open",
    "ctx_archive",
    "ctx_list",
    "ctx_select",
    "ctx_update",
    "run",
]

import os
import threading
import time
from datetime import UTC, datetime
from secrets import token_hex
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
)

from ot.config import get_tool_config
from ot.logging import LogSpan
from ot.paths import get_effective_cwd
from ottools._worker.app_server import AdapterOutcome, AppServerAdapter
from ottools._worker.artifacts import ArtifactError, ArtifactStore, encode_content
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
    InternalPublicTerminalOutput,
    ModelId,
    NonBlank,
    PublicWorkerResult,
)

_WORKER_ENV = "OT_EPISODIC_WORKER"
_ACTIVE_LOCK = threading.Lock()


class Config(BaseModel):
    """Strict worker routing, Context, and episode-limit configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: ModelId | None = None
    effort: NonBlank | None = None
    context_max_kb: Annotated[StrictInt, Field(gt=0)] = 16
    max_turns: Annotated[StrictInt, Field(ge=1, le=10)] = 3
    episode_timeout_seconds: Annotated[StrictInt, Field(ge=1, le=3600)] = 900
    warm_runtime_enabled: StrictBool = True
    warm_runtime_idle_seconds: Annotated[StrictInt, Field(ge=1, le=3600)] = 300


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


def _failure_classification(outcome: AdapterOutcome) -> str | None:
    if outcome.status != "failed":
        return None
    for classification in ("turn_limit", "episode_timeout"):
        if outcome.message.startswith(f"{classification}:"):
            return classification
    return "episode_failed"


def _store() -> ContextStore:
    return ContextStore(context_max_kb=_get_config().context_max_kb)


def _artifact_store() -> ArtifactStore:
    return ArtifactStore(context_store=_store())


def _recursive_error() -> dict[str, object] | None:
    if os.getenv(_WORKER_ENV) != "1":
        return None
    return _operation_error(
        status="recursive_worker_operation",
        error="worker operations cannot be called from an episodic worker",
    )


def ctx_select(*, context: str) -> dict[str, object]:
    """Create or validate a named active Context for caller-owned selection.

    Args:
        context: Lowercase Context slug to create or select.

    Returns:
        A bounded receipt containing the Context name and creation indicator.
    """
    with LogSpan(span="worker.ctx_select", context=context) as span:
        if error := _recursive_error():
            return error
        try:
            loaded, created = _store().load(context, create=True)
            span.add(created=created)
            return {"ok": True, "context": loaded.name, "created": created}
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="ctx_select_failed", error=str(exc))


def ctx_list(
    *, status: Literal["active", "archived"] | None = None
) -> dict[str, object]:
    """List validated Context frontmatter without semantic bodies.

    Args:
        status: Optional active or archived filter.

    Returns:
        Stable body-free Context metadata.
    """
    with LogSpan(span="worker.ctx_list", status=status) as span:
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
            return _operation_error(status="ctx_list_failed", error=str(exc))


def ctx_update(
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
    with LogSpan(span="worker.ctx_update", context=context) as span:
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
            return _operation_error(status="ctx_update_failed", error=str(exc))


def ctx_archive(*, context: str) -> dict[str, object]:
    """Archive one active non-default Context without deleting or moving it.

    Args:
        context: Existing active Context slug.

    Returns:
        A bounded receipt containing the Context name and archived status.
    """
    with LogSpan(span="worker.ctx_archive", context=context) as span:
        if error := _recursive_error():
            return error
        try:
            loaded = _store().archive(context)
            span.add(revision=loaded.metadata.revision)
            return {"ok": True, "context": loaded.name, "status": "archived"}
        except (ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="ctx_archive_failed", error=str(exc))


def asset_create(
    *,
    context: str,
    content: str,
    kind: Literal["text", "binary"],
    media_type: str,
    label: str,
) -> dict[str, object]:
    """Create one immutable artifact owned by an active named Context.

    Args:
        context: Existing active Context slug.
        content: UTF-8 text, or strict base64 when ``kind`` is ``binary``.
        kind: Content encoding kind: ``text`` or ``binary``.
        media_type: Lowercase media type without parameters.
        label: Bounded nonblank human-readable label.

    Returns:
        Bounded artifact metadata without the artifact body.
    """
    with LogSpan(span="worker.asset_create") as span:
        try:
            metadata, warnings = _artifact_store().create(
                context=context,
                content=content,
                kind=kind,
                media_type=media_type,
                label=label,
            )
            return {
                "ok": True,
                "context": context,
                "artifact": metadata.model_dump(mode="json"),
                "warnings": warnings,
            }
        except (ArtifactError, ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="asset_create_failed", error=str(exc))


def asset_open(*, context: str, artifact_id: str) -> dict[str, object]:
    """Open one validated artifact explicitly by Context and opaque ID.

    Args:
        context: Existing active or archived Context slug.
        artifact_id: Opaque artifact ID returned by create or list.

    Returns:
        Strict metadata and UTF-8 text or base64 binary content.
    """
    with LogSpan(span="worker.asset_open") as span:
        try:
            artifact, warnings = _artifact_store().open(
                context=context,
                artifact_id=artifact_id,
            )
            return {
                "ok": True,
                "context": context,
                "artifact": artifact.metadata.model_dump(mode="json"),
                "content": encode_content(artifact),
                "warnings": warnings,
            }
        except (ArtifactError, ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="asset_open_failed", error=str(exc))


def asset_list(
    *,
    context: str,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """List bounded artifact metadata for one active or archived Context.

    Args:
        context: Existing active or archived Context slug.
        limit: Oldest-first page size from 1 through 64.
        offset: Zero-based oldest-first page offset.

    Returns:
        Metadata-only page and bounded orphan warnings.
    """
    with LogSpan(span="worker.asset_list") as span:
        try:
            page = _artifact_store().list_artifacts(
                context=context,
                limit=limit,
                offset=offset,
            )
            return {
                "ok": True,
                "context": context,
                "artifacts": [
                    item.model_dump(mode="json") for item in page.items
                ],
                "total": page.total,
                "limit": page.limit,
                "offset": page.offset,
                "has_more": page.has_more,
                "warnings": page.warnings,
            }
        except (ArtifactError, ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="asset_list_failed", error=str(exc))


def asset_delete(*, context: str, artifact_id: str) -> dict[str, object]:
    """Delete one existing artifact explicitly from its owning Context.

    Args:
        context: Existing active or archived Context slug.
        artifact_id: Opaque artifact ID returned by create or list.

    Returns:
        Bounded deletion receipt without artifact metadata or body.
    """
    with LogSpan(span="worker.asset_delete") as span:
        try:
            warnings = _artifact_store().delete(
                context=context,
                artifact_id=artifact_id,
            )
            return {
                "ok": True,
                "context": context,
                "artifact_id": artifact_id,
                "deleted": True,
                "warnings": warnings,
            }
        except (ArtifactError, ContextError, ValidationError, ValueError, OSError) as exc:
            span.add(error=type(exc).__name__)
            return _operation_error(status="asset_delete_failed", error=str(exc))


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
            episode_deadline = time.monotonic() + config.episode_timeout_seconds
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

            def commit_terminal(terminal: InternalPublicTerminalOutput) -> None:
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
                max_turns=config.max_turns,
                deadline=episode_deadline,
                warm_runtime_enabled=config.warm_runtime_enabled,
                warm_runtime_idle_seconds=config.warm_runtime_idle_seconds,
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
                    failure=_failure_classification(outcome),
                    warnings=warnings,
                )
                try:
                    HistoryStore(state_root=store.state_root).append(history)
                except HistoryError:
                    warnings.append("history_append_failed")

            span.add(status=outcome.status)
            if outcome.startup is not None:
                span.add(
                    runtimeStartup=outcome.startup.classification,
                    initializationSeconds=round(
                        outcome.startup.initialization_seconds, 6
                    ),
                    firstEventSeconds=round(outcome.startup.first_event_seconds, 6),
                    threadStartSeconds=round(outcome.startup.thread_start_seconds, 6),
                    preTurnSeconds=round(outcome.startup.pre_turn_seconds, 6),
                )
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
