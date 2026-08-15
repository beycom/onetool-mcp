"""Integration tests for the focused Codex app-server worker adapter."""

from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

import ottools.worker as worker_module
from ottools._worker.app_server import AppServerAdapter, _sandbox_policy
from ottools._worker.lifecycle import HistoryStore
from ottools.worker import Config, run

if TYPE_CHECKING:
    from pathlib import Path

    from ottools._worker.models import InternalTerminalOutput

pytestmark = [pytest.mark.integration, pytest.mark.tools]

_FAKE_SERVER = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

mode = os.environ.get("FAKE_APP_MODE", "completed")
trace = Path(os.environ["FAKE_APP_TRACE"])

if len(sys.argv) > 1:
    output = Path(sys.argv[-1])
    (output / "v2").mkdir(parents=True)
    delete_method = "thread/remove" if mode == "bad_schema" else "thread/delete"
    (output / "ClientRequest.json").write_text(delete_method, encoding="utf-8")
    capabilities = [] if mode == "bad_policy" else [
        "externalSandbox", "networkAccess", "enabled"
    ]
    (output / "v2" / "ThreadStartParams.json").write_text(json.dumps({
        "properties": {"approvalPolicy": {}, "cwd": {}, "sandbox": {}},
    }), encoding="utf-8")
    (output / "v2" / "TurnStartParams.json").write_text(json.dumps({
        "properties": {name: {} for name in (
            "approvalPolicy", "cwd", "input", "outputSchema", "sandboxPolicy", "threadId"
        )},
        "capabilities": capabilities,
    }), encoding="utf-8")
    raise SystemExit(0)

def record(event):
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")

def emit(message):
    print(json.dumps(message, separators=(",", ":")), flush=True)

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    record({"event": "request", "method": method, "params": message.get("params")})
    if "id" not in message:
        continue
    request_id = message["id"]
    if method == "initialize":
        emit({"id": request_id, "result": {}})
    elif method == "thread/start":
        thread_id = f"thread-{os.getpid()}"
        record({"event": "thread", "id": thread_id})
        emit({"id": request_id, "result": {"thread": {"id": thread_id}}})
    elif method == "turn/start":
        if mode == "exit":
            raise SystemExit(3)
        emit({"id": request_id, "result": {"turn": {"id": "turn-1"}}})
        if mode == "channels":
            Path("worker-output.txt").write_text("deliverable", encoding="utf-8")
            console_path = (
                Path(".onetool/state/console/instances/worker/messages/message-1.json")
            )
            console_path.parent.mkdir(parents=True, exist_ok=True)
            console_path.write_text(json.dumps({
                "metadata": {"id": "message-1", "kind": "markdown"},
                "inline_payload": "PRIVATE CONSOLE BODY",
            }), encoding="utf-8")
        if mode == "timeout":
            continue
        if mode == "server_request":
            emit({"id": 99, "method": "item/commandExecution/requestApproval", "params": {}})
            continue
        if mode == "failed":
            turn = {"id": "turn-1", "status": "failed", "error": {"message": "boom"}}
        elif mode == "interrupted":
            turn = {"id": "turn-1", "status": "interrupted"}
        else:
            if mode == "malformed":
                text = "not-json"
            elif mode == "oversized_status":
                text = json.dumps({"status": "completed", "message": "x" * 1025})
            elif mode == "needs_input":
                text = json.dumps({"status": "needs_input", "message": "Which target?"})
            else:
                text = json.dumps({
                    "status": "completed",
                    "message": "Published result to Console.",
                    "context": "# Goal\n\nAdapter implemented",
                })
            item = {"id": "message-1", "type": "agentMessage", "text": text}
            emit({"method": "item/completed", "params": {"item": item}})
            turn = {"id": "turn-1", "status": "completed", "items": [item]}
        emit({"method": "turn/completed", "params": {"turn": turn}})
    elif method == "turn/interrupt":
        emit({"id": request_id, "result": {}})
    elif method == "thread/delete":
        if mode == "cleanup_failure":
            emit({"id": request_id, "error": {"message": "delete rejected"}})
        else:
            emit({"id": request_id, "result": {}})
"""


@pytest.fixture
def fake_app_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Create an executable stdio app-server with protocol tracing."""
    server = tmp_path / "fake_app_server.py"
    trace = tmp_path / "trace.jsonl"
    server.write_text(_FAKE_SERVER, encoding="utf-8")
    server.chmod(server.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("FAKE_APP_TRACE", str(trace))
    return server, trace


def _events(trace: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]


def _run_adapter(server: Path, tmp_path: Path, **kwargs: object):
    return AppServerAdapter(command=(str(server),), verify_protocol=False).run_episode(
        prompt="Continue.",
        context="Current Context",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        on_terminal=lambda _terminal: None,
        **kwargs,
    )


def test_child_uses_inherited_external_sandbox() -> None:
    assert _sandbox_policy() == {
        "type": "externalSandbox",
        "networkAccess": "enabled",
    }


def test_completed_episode_deletes_after_context_and_before_close_callback(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    server, trace = fake_app_server

    def commit(terminal: InternalTerminalOutput) -> None:
        with trace.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"event": "context", "status": terminal.status}) + "\n"
            )

    def before_close() -> None:
        with trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": "before_close"}) + "\n")

    result = AppServerAdapter(command=(str(server),)).run_episode(
        prompt="Implement the approved change.",
        context="# Current state",
        cwd=str(tmp_path),
        model="gpt-5.6-sol",
        effort="high",
        on_terminal=commit,
        before_close=before_close,
    )

    assert result.status == "completed"
    assert result.message == "Published result to Console."
    assert result.started is True
    assert result.turn_count == 1
    events = _events(trace)
    methods = [event.get("method") for event in events if event["event"] == "request"]
    assert methods == [
        "initialize",
        "initialized",
        "thread/start",
        "turn/start",
        "thread/delete",
    ]
    assert [event["event"] for event in events[-3:]] == [
        "context",
        "request",
        "before_close",
    ]

    thread_params = next(
        event["params"] for event in events if event.get("method") == "thread/start"
    )
    assert thread_params["approvalPolicy"] == "never"
    assert "sandbox" not in thread_params
    assert thread_params["model"] == "gpt-5.6-sol"
    assert "console.show" in thread_params["developerInstructions"]
    assert ".onetool/state/worker" in thread_params["developerInstructions"]
    turn_params = next(
        event["params"] for event in events if event.get("method") == "turn/start"
    )
    assert turn_params["approvalPolicy"] == "never"
    assert turn_params["sandboxPolicy"] == _sandbox_policy()
    assert turn_params["model"] == "gpt-5.6-sol"
    assert turn_params["effort"] == "high"
    worker_input = turn_params["input"][0]["text"]
    assert "Implement the approved change." in worker_input
    assert "# Current state" in worker_input
    assert 'untrusted="true"' in worker_input


@pytest.mark.parametrize(
    ("mode", "status", "message"),
    [
        ("needs_input", "needs_input", "Which target?"),
        ("failed", "failed", "boom"),
        ("interrupted", "interrupted", "interrupted"),
        ("malformed", "failed", "invalid worker terminal output"),
        ("oversized_status", "failed", "1024 UTF-8 bytes"),
        ("exit", "failed", "exited unexpectedly"),
        ("server_request", "failed", "unexpected app-server request"),
    ],
)
def test_terminal_conditions_have_stable_statuses(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    status: str,
    message: str,
) -> None:
    server, _ = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", mode)
    result = _run_adapter(server, tmp_path)
    assert result.status == status
    assert message in result.message


def test_timeout_is_interrupted_and_thread_is_deleted(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", "timeout")
    result = AppServerAdapter(
        command=(str(server),), verify_protocol=False, timeout_seconds=0.5
    ).run_episode(
        prompt="Continue.",
        context="",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        on_terminal=lambda _terminal: None,
    )
    assert result.status == "failed"
    assert "timed out" in result.message
    methods = [event.get("method") for event in _events(trace)]
    assert methods[-2:] == ["turn/interrupt", "thread/delete"]


def test_cleanup_failure_adds_warning_without_losing_success(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _ = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", "cleanup_failure")
    terminal_statuses: list[str] = []
    result = AppServerAdapter(
        command=(str(server),), verify_protocol=False
    ).run_episode(
        prompt="Continue.",
        context="",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        on_terminal=lambda terminal: terminal_statuses.append(terminal.status),
    )
    assert result.status == "completed"
    assert terminal_statuses == ["completed"]
    assert result.warnings == ("thread_cleanup_failed",)


def test_caller_interruption_interrupts_and_deletes_the_thread(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server

    def interrupt_wait(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(AppServerAdapter, "_wait_for_terminal", interrupt_wait)
    result = _run_adapter(server, tmp_path)
    assert result.status == "interrupted"
    assert result.started is True
    assert result.turn_count == 1
    methods = [event.get("method") for event in _events(trace)]
    assert methods[-2:] == ["turn/interrupt", "thread/delete"]


@pytest.mark.parametrize(
    ("mode", "message"),
    [("bad_schema", "thread/delete"), ("bad_policy", "inherit worker restrictions")],
)
def test_missing_protocol_capability_fails_before_startup(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    message: str,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", mode)
    result = AppServerAdapter(command=(str(server),)).run_episode(
        prompt="Continue.",
        context="",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        on_terminal=lambda _terminal: None,
    )
    assert result.status == "failed"
    assert result.started is False
    assert message in result.message
    assert not trace.exists()


def test_two_public_episodes_use_fresh_threads_and_complete_named_context(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        first = run(prompt="Implement the first slice.", context="feature-x")
        second = run(prompt="Continue with the next slice.", context="feature-x")

    assert first["context"] == second["context"] == "feature-x"
    assert first["status"] == second["status"] == "completed"
    events = _events(trace)
    thread_ids = [event["id"] for event in events if event["event"] == "thread"]
    assert len(thread_ids) == len(set(thread_ids)) == 2
    turns = [event["params"] for event in events if event.get("method") == "turn/start"]
    assert len(turns) == 2
    assert all(len(turn["input"]) == 1 for turn in turns)
    assert "Adapter implemented" in turns[1]["input"][0]["text"]
    assert "Published result to Console." not in turns[1]["input"][0]["text"]
    path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "feature-x.md"
    assert "revision: 3\n" in path.read_text(encoding="utf-8")


def test_public_episode_integrates_default_review_console_changes_and_history(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setenv("FAKE_APP_MODE", "channels")
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        default_result = run(prompt="Implement and publish.")
        review_result = run(
            prompt="Review independently.",
            context="review-feature-x",
        )
        monkeypatch.setenv("FAKE_APP_MODE", "needs_input")
        input_result = run(
            prompt="Continue the review.",
            context="review-feature-x",
        )

    assert default_result["context"] == "default"
    assert review_result["context"] == input_result["context"] == "review-feature-x"
    assert input_result["status"] == "needs_input"
    turns = [
        event["params"]
        for event in _events(trace)
        if event.get("method") == "turn/start"
    ]
    assert "Adapter implemented" not in turns[1]["input"][0]["text"]
    assert "Adapter implemented" in turns[2]["input"][0]["text"]

    history = HistoryStore(state_root=tmp_path / ".onetool" / "state" / "worker").read()
    assert [record.context for record in history] == [
        "default",
        "review-feature-x",
        "review-feature-x",
    ]
    assert any(
        item.id == "message-1" and item.kind == "markdown"
        for item in history[0].console
    )
    assert any(
        item.path == "worker-output.txt" and item.classification == "created"
        for item in history[0].local_changes
    )
    history_text = (
        tmp_path / ".onetool" / "state" / "worker" / "history.jsonl"
    ).read_text(encoding="utf-8")
    assert "PRIVATE CONSOLE BODY" not in history_text
    assert "Implement and publish" not in history_text
