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
from ottools._worker.models import InternalContinueOutput
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
sequence = os.environ.get("FAKE_APP_SEQUENCE", "").split(",")
sequence = [item for item in sequence if item]
trace = Path(os.environ["FAKE_APP_TRACE"])
turn_number = 0

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
        turn_number += 1
        turn_id = f"turn-{turn_number}"
        turn_mode = sequence[min(turn_number - 1, len(sequence) - 1)] if sequence else mode
        if turn_mode == "exit":
            raise SystemExit(3)
        emit({"id": request_id, "result": {"turn": {"id": turn_id}}})
        if turn_mode in {"channels", "continue_effect"}:
            Path("worker-output.txt").write_text("deliverable", encoding="utf-8")
            console_path = (
                Path(".onetool/state/console/instances/worker/messages/message-1.json")
            )
            console_path.parent.mkdir(parents=True, exist_ok=True)
            console_path.write_text(json.dumps({
                "metadata": {"id": "message-1", "kind": "markdown"},
                "inline_payload": "PRIVATE CONSOLE BODY",
            }), encoding="utf-8")
        if turn_mode == "timeout":
            continue
        if turn_mode == "server_request":
            emit({"id": 99, "method": "item/commandExecution/requestApproval", "params": {}})
            continue
        if turn_mode == "failed":
            turn = {"id": turn_id, "status": "failed", "error": {"message": "boom"}}
        elif turn_mode == "interrupted":
            turn = {"id": turn_id, "status": "interrupted"}
        else:
            if turn_mode == "malformed":
                text = "not-json"
            elif turn_mode == "oversized_status":
                text = json.dumps({"status": "completed", "message": "x" * 1025})
            elif turn_mode == "needs_input":
                text = json.dumps({"status": "needs_input", "message": "Which target?"})
            elif turn_mode == "needs_input_context":
                text = json.dumps({
                    "status": "needs_input",
                    "message": "Which target?",
                    "context": "# Waiting\n\nTarget required",
                })
            elif turn_mode in {"continue", "continue_effect"}:
                text = json.dumps({
                    "status": "continue",
                    "next_action": "Run the focused verification.",
                })
            elif turn_mode == "invalid_continue":
                text = json.dumps({
                    "status": "continue",
                    "next_action": "Run the focused verification.",
                    "context": "must not commit",
                })
            else:
                text = json.dumps({
                    "status": "completed",
                    "message": "Published result to Console.",
                    "context": "# Goal\n\nAdapter implemented",
                })
            item = {"id": "message-1", "type": "agentMessage", "text": text}
            emit({"method": "item/completed", "params": {"item": item}})
            turn = {"id": turn_id, "status": "completed", "items": [item]}
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
    assert "Use normal tool calls" in thread_params["developerInstructions"]
    assert "only when" in thread_params["developerInstructions"]
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


def test_continuation_reuses_thread_authority_with_ephemeral_input(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue,completed")
    terminals: list[InternalTerminalOutput] = []

    result = AppServerAdapter(
        command=(str(server),),
        verify_protocol=False,
    ).run_episode(
        prompt="Implement the approved change.",
        context="# Private committed Context",
        cwd=str(tmp_path),
        model="gpt-5.6-sol",
        effort="high",
        max_turns=3,
        on_terminal=terminals.append,
    )

    assert result.status == "completed"
    assert result.turn_count == 2
    assert len(terminals) == 1
    assert terminals[0].status == "completed"
    events = _events(trace)
    threads = [event for event in events if event["event"] == "thread"]
    turns = [event["params"] for event in events if event.get("method") == "turn/start"]
    assert len(threads) == 1
    assert len(turns) == 2
    assert turns[0]["threadId"] == turns[1]["threadId"] == threads[0]["id"]
    for field in ("cwd", "approvalPolicy", "sandboxPolicy", "model", "effort"):
        assert turns[0][field] == turns[1][field]
    second_input = turns[1]["input"][0]["text"]
    assert "Continue the current task autonomously" in second_input
    assert "Run the focused verification." in second_input
    assert "Implement the approved change." not in second_input
    assert "# Private committed Context" not in second_input
    assert "Status" not in second_input


def test_invalid_continuation_fails_terminal_validation(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _ = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", "invalid_continue")
    terminals: list[InternalTerminalOutput] = []

    result = AppServerAdapter(
        command=(str(server),),
        verify_protocol=False,
    ).run_episode(
        prompt="Continue.",
        context="",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        max_turns=3,
        on_terminal=terminals.append,
    )

    assert result.status == "failed"
    assert result.turn_count == 1
    assert "invalid worker terminal output" in result.message
    assert terminals == []


def test_continuation_at_turn_limit_fails_without_another_turn(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_MODE", "continue")

    result = _run_adapter(server, tmp_path, max_turns=2)

    assert result.status == "failed"
    assert result.turn_count == 2
    assert result.message.startswith("turn_limit:")
    turns = [event for event in _events(trace) if event.get("method") == "turn/start"]
    assert len(turns) == 2


def test_one_deadline_covers_later_continuation_turn(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue,timeout")

    result = AppServerAdapter(
        command=(str(server),),
        verify_protocol=False,
        timeout_seconds=0.5,
    ).run_episode(
        prompt="Continue.",
        context="",
        cwd=str(tmp_path),
        model=None,
        effort=None,
        max_turns=3,
        on_terminal=lambda _terminal: None,
    )

    assert result.status == "failed"
    assert result.turn_count == 2
    assert result.message.startswith("episode_timeout:")
    methods = [event.get("method") for event in _events(trace)]
    assert methods[-2:] == ["turn/interrupt", "thread/delete"]


def test_later_turn_protocol_failure_is_not_retried(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue,malformed")

    result = _run_adapter(server, tmp_path, max_turns=3)

    assert result.status == "failed"
    assert result.turn_count == 2
    assert "invalid worker terminal output" in result.message
    assert len([event for event in _events(trace) if event["event"] == "thread"]) == 1


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
    assert result.message.startswith("episode_timeout:")
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


def test_caller_interruption_after_continuation_records_started_turns(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    waits = 0

    def continue_then_interrupt(*_args: object, **_kwargs: object):
        nonlocal waits
        waits += 1
        if waits == 1:
            return InternalContinueOutput(
                status="continue",
                next_action="Run the focused verification.",
            )
        raise KeyboardInterrupt

    monkeypatch.setattr(
        AppServerAdapter,
        "_wait_for_terminal",
        continue_then_interrupt,
    )
    result = _run_adapter(server, tmp_path, max_turns=3)

    assert result.status == "interrupted"
    assert result.turn_count == 2
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


def test_public_continuation_commits_only_final_context_and_records_turns(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue_effect,completed")
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        result = run(prompt="Implement and verify.", context="feature-x")

    assert result == {
        "context": "feature-x",
        "status": "completed",
        "message": "Published result to Console.",
    }
    assert (tmp_path / "worker-output.txt").read_text(encoding="utf-8") == "deliverable"
    context_path = (
        tmp_path / ".onetool" / "state" / "worker" / "contexts" / "feature-x.md"
    )
    assert "revision: 2\n" in context_path.read_text(encoding="utf-8")
    history = HistoryStore(state_root=context_path.parents[1]).read()
    assert len(history) == 1
    assert history[0].turn_count == 2
    assert history[0].context_revision_before == 1
    assert history[0].context_revision_after == 2
    history_text = (context_path.parents[1] / "history.jsonl").read_text(
        encoding="utf-8"
    )
    assert "next_action" not in history_text
    assert "Run the focused verification" not in history_text
    assert "Continue the current task" not in history_text
    events = _events(trace)
    assert len([event for event in events if event["event"] == "thread"]) == 1
    assert len([event for event in events if event.get("method") == "turn/start"]) == 2


def test_public_turn_limit_preserves_pre_episode_context(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _ = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setenv("FAKE_APP_MODE", "continue")
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(
            worker_module,
            "_get_config",
            return_value=Config(max_turns=2),
        ),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        result = run(prompt="Keep working.", context="feature-x")

    assert result["status"] == "failed"
    assert result["message"].startswith("turn_limit:")
    context_path = (
        tmp_path / ".onetool" / "state" / "worker" / "contexts" / "feature-x.md"
    )
    assert "revision: 1\n" in context_path.read_text(encoding="utf-8")
    history = HistoryStore(state_root=context_path.parents[1]).read()
    assert history[0].turn_count == 2
    assert history[0].context_revision_before == history[0].context_revision_after == 1
    assert history[0].failure == "turn_limit"


def test_later_failure_preserves_effects_without_context_commit_or_replay(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue_effect,malformed")
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        result = run(prompt="Implement and verify.", context="feature-x")

    assert result["status"] == "failed"
    assert (tmp_path / "worker-output.txt").read_text(encoding="utf-8") == "deliverable"
    context_path = (
        tmp_path / ".onetool" / "state" / "worker" / "contexts" / "feature-x.md"
    )
    assert "revision: 1\n" in context_path.read_text(encoding="utf-8")
    history = HistoryStore(state_root=context_path.parents[1]).read()
    assert history[0].turn_count == 2
    assert history[0].context_revision_after == 1
    assert any(item.path == "worker-output.txt" for item in history[0].local_changes)
    assert len([event for event in _events(trace) if event["event"] == "thread"]) == 1


def test_continued_needs_input_is_deleted_and_answer_uses_fresh_thread(
    fake_app_server: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, trace = fake_app_server
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setenv("FAKE_APP_SEQUENCE", "continue,needs_input_context")
    real_adapter = AppServerAdapter(command=(str(server),))
    with (
        patch.object(worker_module, "_get_config", return_value=Config()),
        patch.object(worker_module, "AppServerAdapter", return_value=real_adapter),
    ):
        first = run(prompt="Implement.", context="feature-x")
        monkeypatch.setenv("FAKE_APP_SEQUENCE", "completed")
        second = run(prompt="Use target A.", context="feature-x")

    assert first["status"] == "needs_input"
    assert second["status"] == "completed"
    events = _events(trace)
    thread_ids = [event["id"] for event in events if event["event"] == "thread"]
    assert len(thread_ids) == len(set(thread_ids)) == 2
    methods = [event.get("method") for event in events]
    first_delete = methods.index("thread/delete")
    second_start = methods.index("thread/start", methods.index("thread/start") + 1)
    assert first_delete < second_start
    turns = [event["params"] for event in events if event.get("method") == "turn/start"]
    assert len(turns) == 3
    assert turns[0]["threadId"] == turns[1]["threadId"]
    assert turns[2]["threadId"] != turns[1]["threadId"]
    answer_input = turns[2]["input"][0]["text"]
    assert "Use target A." in answer_input
    assert "# Waiting\n\nTarget required" in answer_input
    history_path = tmp_path / ".onetool" / "state" / "worker"
    history = HistoryStore(state_root=history_path).read()
    assert [record.turn_count for record in history] == [2, 1]
    assert [record.status for record in history] == ["needs_input", "completed"]


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
