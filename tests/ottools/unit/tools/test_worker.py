"""Tests for the sole public episodic worker tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

import ottools.worker as worker_module
from ottools._worker.app_server import AdapterOutcome
from ottools._worker.context import normalize_context, render_context
from ottools._worker.models import CommittedContext, InternalTerminalOutput
from ottools.worker import Config, run

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _context(summary: str) -> dict[str, Any]:
    return {
        "goal": {
            "status": "active",
            "objective": "Finish the worker",
            "success_criteria": ["Checks pass"],
        },
        "work": {
            "summary": summary,
            "next_actions": ["Continue"],
            "blockers": [],
        },
        "knowledge": [{"kind": "decision", "text": "Keep the surface small"}],
        "questions": [],
        "references": [],
    }


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
        self._calls.append({key: value for key, value in kwargs.items() if key != "on_terminal"})
        if self._terminal is not None:
            kwargs["on_terminal"](self._terminal)
        return self._outcome


def _execution(tmp_path: Path, *, sandbox: str = "workspace-write") -> dict[str, str]:
    return {
        "cwd": str(tmp_path),
        "approval_policy": "never",
        "sandbox": sandbox,
    }


def test_two_episodes_reuse_only_complete_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapters = [
        _FakeAdapter(
            calls,
            outcome=AdapterOutcome("completed", "First done."),
            terminal=InternalTerminalOutput(
                status="completed", message="First done.", context=_context("First episode")
            ),
        ),
        _FakeAdapter(
            calls,
            outcome=AdapterOutcome("needs_input", "Which target?"),
            terminal=InternalTerminalOutput(
                status="needs_input", message="Which target?", context=None
            ),
        ),
    ]
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", side_effect=adapters),
    ):
        first = run(
            prompt="Implement it.",
            execution=_execution(tmp_path),
            model="gpt-5.6-sol",
            effort="high",
        )
        second = run(
            prompt="Use package A.",
            execution=_execution(tmp_path),
            session_id=first["session_id"],
        )

    assert set(first) == {"session_id", "status", "message"}
    assert first["status"] == "completed"
    assert second == {
        "session_id": first["session_id"],
        "status": "needs_input",
        "message": "Which target?",
    }
    assert calls[0]["context"] == {
        "schema_version": 1,
        "revision": 0,
        "context": None,
    }
    assert calls[0]["model"] == "gpt-5.6-sol"
    assert calls[0]["effort"] == "high"
    assert calls[1]["context"]["revision"] == 1
    assert calls[1]["context"]["work"]["summary"] == "First episode"


def test_configured_routing_and_per_call_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Done."))
    with (
        patch.object(
            worker_module,
            "_get_config",
            return_value=Config(model="configured-model", effort="medium"),
        ),
        patch.object(worker_module, "AppServerAdapter", return_value=adapter),
    ):
        run(prompt="First.", execution=_execution(tmp_path))
        run(
            prompt="Second.",
            execution=_execution(tmp_path),
            model="call-model",
            effort="high",
        )
    assert [(call["model"], call["effort"]) for call in calls] == [
        ("configured-model", "medium"),
        ("call-model", "high"),
    ]


@pytest.mark.parametrize("status", ["completed", "needs_input", "failed", "interrupted"])
def test_absent_terminal_context_preserves_last_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    commit_adapter = _FakeAdapter(
        calls,
        outcome=AdapterOutcome("completed", "Saved."),
        terminal=InternalTerminalOutput(
            status="completed", message="Saved.", context=_context("Saved context")
        ),
    )
    preserve_adapter = _FakeAdapter(
        calls,
        outcome=AdapterOutcome(status, "Terminal."),
        terminal=(
            InternalTerminalOutput(status=status, message="Terminal.", context=None)
            if status in {"completed", "needs_input"}
            else None
        ),
    )
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(
            worker_module,
            "AppServerAdapter",
            side_effect=[commit_adapter, preserve_adapter],
        ),
    ):
        first = run(prompt="Save.", execution=_execution(tmp_path))
        result = run(
            prompt="Continue.",
            execution=_execution(tmp_path),
            session_id=first["session_id"],
        )
    assert result["status"] == status
    assert calls[-1]["context"]["revision"] == 1
    context_path = (
        tmp_path
        / ".onetool"
        / "state"
        / "episodic-context"
        / first["session_id"]
        / "context.yaml"
    )
    assert "revision: 1\n" in context_path.read_text(encoding="utf-8")


def test_invalid_policy_fails_before_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Done."))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=adapter),
    ):
        wrong_cwd = run(
            prompt="Start.",
            execution={**_execution(tmp_path), "cwd": str(tmp_path.parent)},
        )
    assert wrong_cwd["status"] == "failed"
    assert calls == []


@pytest.mark.parametrize(
    ("invalid_kind", "message"),
    [
        ("corrupt", "invalid YAML"),
        ("oversized", "limit is 16 KB"),
        ("missing_reference", "existing regular file"),
    ],
)
def test_every_invalid_stored_context_fails_before_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_kind: str,
    message: str,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("completed", "Done."))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=adapter),
    ):
        created = run(prompt="Create.", execution=_execution(tmp_path))
        context_path = (
            tmp_path
            / ".onetool"
            / "state"
            / "episodic-context"
            / created["session_id"]
            / "context.yaml"
        )
        if invalid_kind == "corrupt":
            content = "not: [valid"
        else:
            raw = _context("x" * 20_000 if invalid_kind == "oversized" else "Current")
            if invalid_kind == "missing_reference":
                raw["references"] = [
                    {"path": "missing.md", "purpose": "Required evidence"}
                ]
            normalized = normalize_context(raw)
            content = render_context(
                CommittedContext(
                    schema_version=1,
                    revision=1,
                    **normalized.model_dump(mode="python"),
                )
            )
        context_path.write_text(content, encoding="utf-8")
        result = run(
            prompt="Continue.",
            execution=_execution(tmp_path),
            session_id=created["session_id"],
        )
    assert result["status"] == "failed"
    assert message in result["message"]
    assert context_path.read_text(encoding="utf-8") == content
    assert len(calls) == 1


def test_recursive_concurrent_and_failed_calls_are_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    calls: list[dict[str, Any]] = []
    adapter = _FakeAdapter(calls, outcome=AdapterOutcome("failed", "Protocol failed."))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=adapter),
    ):
        monkeypatch.setenv("OT_EPISODIC_WORKER", "1")
        recursive = run(prompt="Delegate.", execution=_execution(tmp_path))
        monkeypatch.delenv("OT_EPISODIC_WORKER")
        assert worker_module._ACTIVE_LOCK.acquire(blocking=False)
        try:
            concurrent = run(prompt="Delegate.", execution=_execution(tmp_path))
        finally:
            worker_module._ACTIVE_LOCK.release()
        failed = run(prompt="Delegate.", execution=_execution(tmp_path))
    assert recursive["status"] == "failed"
    assert "cannot be called" in recursive["message"]
    assert concurrent["status"] == "failed"
    assert "already active" in concurrent["message"]
    assert failed["status"] == "failed"
    assert len(calls) == 1


def test_public_module_exposes_only_worker_run() -> None:
    assert worker_module.__all__ == ["run"]
    for deferred_name in (
        "save_context",
        "read_context",
        "search_context",
        "select_context",
        "patch_context",
        "compact_context",
        "queue",
        "schedule",
        "retry",
    ):
        assert not hasattr(worker_module, deferred_name)
