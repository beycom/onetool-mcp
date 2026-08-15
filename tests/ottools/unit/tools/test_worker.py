"""Tests for the named-Context worker tool surface."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import ottools.worker as worker_module
from ottools._worker.app_server import AdapterOutcome
from ottools._worker.lifecycle import (
    HistoryError,
    HistoryStore,
    ObservationError,
    project_fingerprint,
)
from ottools._worker.models import (
    INTERNAL_TERMINAL_OUTPUT_ADAPTER,
    NEXT_ACTION_MAX_BYTES,
    InternalCompletedOutput,
    InternalContinueOutput,
    InternalNeedsInputOutput,
    InternalTerminalOutput,
)
from ottools.worker import (
    Config,
    archive_context,
    list_contexts,
    run,
    select,
    update_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]


class _FakeAdapter:
    def __init__(
        self,
        calls: list[dict[str, Any]],
        *,
        outcome: AdapterOutcome,
        terminal: InternalTerminalOutput | None = None,
    ) -> None:
        self._calls = calls
        self._outcome = outcome
        self._terminal = terminal

    def run_episode(self, **kwargs: Any) -> AdapterOutcome:
        self._calls.append(
            {
                key: value
                for key, value in kwargs.items()
                if key not in {"on_terminal", "before_close"}
            }
        )
        if self._terminal is not None:
            kwargs["on_terminal"](self._terminal)
        if kwargs.get("before_close") is not None:
            kwargs["before_close"]()
        return self._outcome


class _LifecycleAdapter:
    """Exercise the complete runtime-owned terminal lifecycle."""

    def run_episode(self, **kwargs: Any) -> AdapterOutcome:
        project_root = Path(kwargs["cwd"])
        (project_root / "created-by-worker.txt").write_text(
            "deliverable",
            encoding="utf-8",
        )
        message_path = (
            project_root
            / ".onetool"
            / "state"
            / "console"
            / "instances"
            / "child"
            / "messages"
            / "message-1.json"
        )
        message_path.parent.mkdir(parents=True, exist_ok=True)
        message_path.write_text(
            '{"metadata":{"id":"message-1","kind":"markdown"},'
            '"inline_payload":"PRIVATE CONSOLE BODY"}',
            encoding="utf-8",
        )
        kwargs["on_terminal"](
            InternalCompletedOutput(
                status="completed",
                message="Published result to Console.",
                context="# Current state",
            )
        )
        kwargs["before_close"]()
        return AdapterOutcome(
            "completed",
            "Published result to Console.",
            started=True,
            turn_count=1,
        )


def _configure(adapter: _FakeAdapter, config: Config | None = None):
    return (
        patch.object(worker_module, "_get_config", return_value=config or Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=adapter),
    )


def test_default_context_and_complete_body_continue_in_fresh_episode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapters = [
        _FakeAdapter(
            calls,
            outcome=AdapterOutcome("completed", "Published result to Console."),
            terminal=InternalCompletedOutput(
                status="completed",
                message="Published result to Console.",
                context="# Goal\n\nFinish the worker",
            ),
        ),
        _FakeAdapter(
            calls,
            outcome=AdapterOutcome("needs_input", "Which target?"),
            terminal=InternalNeedsInputOutput(
                status="needs_input",
                message="Which target?",
            ),
        ),
    ]
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", side_effect=adapters),
    ):
        first = run(prompt="Implement it.", model="gpt-5.6-sol", effort="high")
        second = run(prompt="Use package A.")

    assert first == {
        "context": "default",
        "status": "completed",
        "message": "Published result to Console.",
    }
    assert second == {
        "context": "default",
        "status": "needs_input",
        "message": "Which target?",
    }
    assert calls[0]["context"] == ""
    assert calls[0]["model"] == "gpt-5.6-sol"
    assert calls[0]["effort"] == "high"
    assert calls[1]["context"] == "# Goal\n\nFinish the worker"
    assert calls[0]["cwd"] == calls[1]["cwd"] == str(tmp_path)


def test_explicit_context_is_one_episode_choice_without_global_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(
        calls,
        outcome=AdapterOutcome("completed", "Done."),
    )
    config_patch, adapter_patch = _configure(adapter)
    with config_patch, adapter_patch:
        run(prompt="Implement.", context="feature-x")
        run(prompt="Review.", context="review-feature-x")
        run(prompt="Direct default call.")

    assert [call["context"] for call in calls] == ["", "", ""]
    result = list_contexts()
    assert [item["name"] for item in result["contexts"]] == [
        "default",
        "feature-x",
        "review-feature-x",
    ]


def test_fresh_review_context_does_not_receive_implementation_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    project_file = tmp_path / "implementation.py"
    project_file.write_text("IMPLEMENTED = True\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []
    adapters = [
        _FakeAdapter(
            calls,
            outcome=AdapterOutcome("completed", "Done."),
            terminal=InternalCompletedOutput(
                status="completed",
                message="Done.",
                context="PRIVATE IMPLEMENTATION CONTEXT",
            ),
        ),
        _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Reviewed.")),
        _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Continued.")),
    ]
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", side_effect=adapters),
    ):
        run(prompt="Implement.", context="feature-x")
        run(prompt="Review project files.", context="review-feature-x")
        run(prompt="Continue.", context="feature-x")

    assert project_file.is_file()
    assert calls[1]["cwd"] == str(tmp_path)
    assert calls[1]["context"] == ""
    assert calls[2]["context"] == "PRIVATE IMPLEMENTATION CONTEXT"


def test_configured_routing_and_per_call_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Done."))
    config = Config(
        model="configured-model",
        effort="medium",
        max_turns=4,
        episode_timeout_seconds=120,
    )
    config_patch, adapter_patch = _configure(adapter, config)
    with (
        config_patch,
        adapter_patch,
        patch.object(worker_module.time, "monotonic", return_value=1_000.0),
    ):
        run(prompt="First.")
        run(prompt="Second.", model="call-model", effort="high")

    assert [(call["model"], call["effort"]) for call in calls] == [
        ("configured-model", "medium"),
        ("call-model", "high"),
    ]
    assert [call["max_turns"] for call in calls] == [4, 4]
    assert [call["deadline"] for call in calls] == [1_120.0, 1_120.0]


def test_continuation_config_defaults_and_valid_limits() -> None:
    defaults = Config()
    configured = Config(max_turns=10, episode_timeout_seconds=3600)

    assert defaults.max_turns == 3
    assert defaults.episode_timeout_seconds == 900
    assert configured.max_turns == 10
    assert configured.episode_timeout_seconds == 3600


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_turns", True),
        ("max_turns", 1.0),
        ("max_turns", "3"),
        ("max_turns", 0),
        ("max_turns", 11),
        ("episode_timeout_seconds", False),
        ("episode_timeout_seconds", 1.0),
        ("episode_timeout_seconds", "900"),
        ("episode_timeout_seconds", 0),
        ("episode_timeout_seconds", 3601),
    ],
)
def test_continuation_config_rejects_non_strict_or_out_of_range_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        Config.model_validate({field: value})


def test_worker_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Config.model_validate({"unknown": 1})


def test_internal_terminal_output_is_a_strict_discriminated_union() -> None:
    continuation = INTERNAL_TERMINAL_OUTPUT_ADAPTER.validate_python(
        {"status": "continue", "next_action": "Run the focused tests."}
    )
    assert continuation == InternalContinueOutput(
        status="continue",
        next_action="Run the focused tests.",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "continue", "next_action": "Finish.", "context": "state"},
        {"status": "continue", "next_action": "Finish.", "message": "Working"},
        {"status": "continue", "next_action": "Which target?"},
        {"status": "continue", "next_action": "Finish.", "permissions": "more"},
        {"status": "continue", "next_action": "Finish.", "unknown": 1},
        {"status": "continue", "next_action": "   "},
        {"status": "continue", "next_action": "x" * (NEXT_ACTION_MAX_BYTES + 1)},
    ],
)
def test_internal_continuation_rejects_terminal_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        INTERNAL_TERMINAL_OUTPUT_ADAPTER.validate_python(payload)


def test_context_operations_are_body_free_and_preserve_explicit_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))

    selected = select(context="feature-x")
    updated = update_context(
        context="feature-x",
        description="Implement feature X",
        tags=["feature", "active"],
    )
    cleared = update_context(context="feature-x", tags=[])
    listed = list_contexts(status="active")
    archived = archive_context(context="feature-x")

    assert selected == {"ok": True, "context": "feature-x", "created": True}
    assert updated == {
        "ok": True,
        "context": "feature-x",
        "created": False,
        "description": "Implement feature X",
        "tags": ["feature", "active"],
        "status": "active",
        "revision": 2,
    }
    assert cleared["description"] == "Implement feature X"
    assert cleared["tags"] == []
    assert set(listed) == {"ok", "contexts"}
    assert "body" not in repr(listed)
    assert archived == {"ok": True, "context": "feature-x", "status": "archived"}
    assert select(context="feature-x")["status"] == "context_select_failed"


def test_update_can_create_and_empty_values_clear_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    created = update_context(context="topic", description="", tags=[])
    missing_fields = update_context(context="other")

    assert created["created"] is True
    assert created["description"] == ""
    assert created["tags"] == []
    assert missing_fields["status"] == "context_update_failed"


def test_invalid_context_fails_before_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Done."))
    config_patch, adapter_patch = _configure(adapter)
    with config_patch, adapter_patch:
        result = run(prompt="Start.", context="../escape")
        blank = run(prompt="Start.", context="")

    assert result["status"] == blank["status"] == "failed"
    assert calls == []
    assert not (tmp_path / ".onetool").exists()


def test_recursive_concurrent_and_failed_calls_are_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("failed", "Protocol failed."))
    config_patch, adapter_patch = _configure(adapter)
    with config_patch, adapter_patch:
        monkeypatch.setenv("OT_EPISODIC_WORKER", "1")
        recursive = run(prompt="Delegate.")
        recursive_select = select(context="topic")
        monkeypatch.delenv("OT_EPISODIC_WORKER")
        assert worker_module._ACTIVE_LOCK.acquire(blocking=False)
        try:
            concurrent = run(prompt="Delegate.")
        finally:
            worker_module._ACTIVE_LOCK.release()
        failed = run(prompt="Delegate.")

    assert recursive["status"] == "failed"
    assert "cannot be called" in recursive["message"]
    assert recursive_select["status"] == "recursive_worker_operation"
    assert concurrent["status"] == "failed"
    assert "already active" in concurrent["message"]
    assert failed["status"] == "failed"
    assert len(calls) == 1


def test_status_is_bounded_after_runtime_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(
        calls,
        outcome=AdapterOutcome(
            "failed",
            "é" * 2_000,
            warnings=("thread_cleanup_failed",),
        ),
    )
    config_patch, adapter_patch = _configure(adapter)
    with config_patch, adapter_patch:
        result = run(prompt="Start.")

    assert set(result) == {"context", "status", "message"}
    assert len(result["message"].encode("utf-8")) <= 1024


def test_completed_episode_records_console_context_and_local_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(
            worker_module, "AppServerAdapter", return_value=_LifecycleAdapter()
        ),
    ):
        result = run(prompt="Produce the deliverable.", context="feature-x")

    records = HistoryStore(state_root=tmp_path / ".onetool" / "state" / "worker").read()
    assert result == {
        "context": "feature-x",
        "status": "completed",
        "message": "Published result to Console.",
    }
    assert len(records) == 1
    record = records[0]
    assert record.context == "feature-x"
    assert record.context_revision_before == 1
    assert record.context_revision_after == 2
    assert [item.model_dump(mode="python") for item in record.console] == [
        {"id": "message-1", "kind": "markdown"}
    ]
    assert [item.model_dump(mode="python") for item in record.local_changes] == [
        {"path": "created-by-worker.txt", "classification": "created"}
    ]
    history_text = (
        tmp_path / ".onetool" / "state" / "worker" / "history.jsonl"
    ).read_text(encoding="utf-8")
    assert "PRIVATE CONSOLE BODY" not in history_text
    assert "# Current state" not in history_text
    assert "Produce the deliverable" not in history_text


def test_final_scan_and_history_failures_warn_without_changing_known_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    baseline = project_fingerprint(tmp_path)
    scans = iter([baseline, ObservationError("final scan failed")])

    def fingerprint(_root: Path):
        value = next(scans)
        if isinstance(value, BaseException):
            raise value
        return value

    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(
            worker_module,
            "AppServerAdapter",
            return_value=_FakeAdapter(
                [],
                outcome=AdapterOutcome(
                    "completed",
                    "Done.",
                    started=True,
                    turn_count=1,
                ),
            ),
        ),
        patch.object(worker_module, "project_fingerprint", side_effect=fingerprint),
        patch.object(
            worker_module.HistoryStore,
            "append",
            side_effect=HistoryError("append failed"),
        ),
    ):
        result = run(prompt="Finish.")

    assert result["status"] == "completed"
    assert "local_changes_observation_failed" in result["message"]
    assert "history_append_failed" in result["message"]


def test_public_surface_has_no_session_or_execution_compatibility() -> None:
    assert worker_module.__all__ == [
        "archive_context",
        "list_contexts",
        "run",
        "select",
        "update_context",
    ]
    parameters = inspect.signature(run).parameters
    assert set(parameters) == {"prompt", "context", "model", "effort"}
