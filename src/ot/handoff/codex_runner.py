"""Narrow Codex app-server runner abstraction for handoff."""

from __future__ import annotations

import itertools
import json
import os
import queue
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ot.handoff.models import TaskRecord


@dataclass
class RunnerCompletion:
    """Completed worker result returned by a runner."""

    task_id: str
    status: str
    body: str
    summary: str = ""
    raw_events: list[str] = field(default_factory=list)
    error: str | None = None


class HandoffRunner(Protocol):
    """Minimal synchronous runner surface used by the handoff runtime."""

    def ensure_started(
        self,
        *,
        worker_env: dict[str, str] | None = None,
        mcp_config: dict[str, object] | None = None,
    ) -> None: ...
    def submit(
        self,
        record: TaskRecord,
        *,
        worker_env: dict[str, str],
        mcp_config: dict[str, object],
    ) -> str: ...
    def poll_completed(self) -> list[RunnerCompletion]: ...
    def cancel(self, runner_id: str) -> str: ...
    def clear(self) -> None: ...


class CodexAppServerRunner:
    """Lazily owns one `codex app-server --listen stdio://` process.

    The live app-server protocol is intentionally isolated here so the handoff
    runtime only sees submitted runner ids and terminal completions.
    """

    def __init__(self, *, command: str, startup_timeout_seconds: int) -> None:
        self.command = command
        self.startup_timeout_seconds = startup_timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._ids = itertools.count(1)
        self._request_ids = itertools.count(1)
        self._lock = threading.RLock()
        self._responses: dict[int, dict[str, Any]] = {}
        self._raw_events: dict[str, list[str]] = {}
        self._turn_to_task: dict[str, str] = {}
        self._task_to_turn: dict[str, str] = {}
        self._runner_to_turn: dict[str, tuple[str, str]] = {}
        self._deadlines: dict[str, float] = {}
        self._completed: queue.SimpleQueue[RunnerCompletion] = queue.SimpleQueue()
        self._reader: threading.Thread | None = None
        self._initialized = False
        self._startup_config_key: str | None = None

    def ensure_started(
        self,
        *,
        worker_env: dict[str, str] | None = None,
        mcp_config: dict[str, object] | None = None,
    ) -> None:
        """Start the Codex app-server process if needed."""
        startup_config = self._worker_config(
            worker_env=worker_env or {}, mcp_config=mcp_config or {}
        )
        startup_config_key = json.dumps(startup_config, sort_keys=True)
        if self.process is not None and self.process.poll() is None:
            if startup_config_key != self._startup_config_key:
                self.clear()
            else:
                if not self._initialized:
                    self._initialize()
                return
        if self.process is not None and self.process.poll() is None:
            if not self._initialized:
                self._initialize()
            return
        args = self._app_server_args(startup_config)
        if "stdio://" not in args:
            raise RuntimeError(
                "handoff runner requires codex app-server stdio transport"
            )
        try:
            self.process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**os.environ},
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "codex CLI not found; install Codex CLI and authenticate before using handoff"
            ) from e
        time.sleep(min(0.05, self.startup_timeout_seconds))
        if self.process.poll() is not None:
            raise RuntimeError(
                "codex app-server exited during startup; check Codex authentication"
            )
        self._reader = threading.Thread(
            target=self._read_stdout,
            name="onetool-handoff-codex-reader",
            daemon=True,
        )
        self._reader.start()
        self._initialize()
        self._startup_config_key = startup_config_key

    def _app_server_args(self, config: dict[str, Any]) -> list[str]:
        args = shlex.split(self.command)
        for key, value in self._flatten_config(config):
            args.extend(["-c", f"{key}={self._toml_literal(value)}"])
        return args

    def _flatten_config(self, config: dict[str, Any]) -> list[tuple[str, Any]]:
        items: list[tuple[str, Any]] = []
        for key in sorted(config):
            value = config[key]
            if isinstance(value, dict):
                for child_key, child_value in self._flatten_config(value):
                    items.append((f"{key}.{child_key}", child_value))
            else:
                items.append((key, value))
        return items

    def _toml_literal(self, value: Any) -> str:
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        if isinstance(value, list):
            return "[" + ",".join(self._toml_literal(item) for item in value) + "]"
        if value is None:
            raise TypeError("Codex app-server config overrides do not support null")
        raise TypeError(f"unsupported Codex app-server config value: {type(value)}")

    def _initialize(self) -> None:
        response = self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "onetool-handoff",
                    "title": "OneTool Handoff",
                    "version": "0",
                },
                "capabilities": {"experimentalApi": True},
            },
            timeout=self.startup_timeout_seconds,
        )
        if "result" not in response:
            raise RuntimeError("codex app-server initialize failed")
        self._notify("initialized")
        self._initialized = True

    def _read_stdout(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            text = line.rstrip("\n")
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            request_id = message.get("id")
            if request_id is not None:
                with self._lock:
                    if isinstance(request_id, int):
                        self._responses[request_id] = message
                continue
            self._handle_notification(message, raw=text)

    def _handle_notification(self, message: dict[str, Any], *, raw: str) -> None:
        method = message.get("method")
        params = message.get("params")
        if isinstance(params, dict):
            turn_id = self._extract_turn_id(params)
            if turn_id:
                with self._lock:
                    task_id = self._turn_to_task.get(turn_id)
                    if task_id:
                        self._raw_events.setdefault(task_id, []).append(raw)
            if method == "turn/completed":
                self._handle_turn_completed(params)

    def _extract_turn_id(self, params: dict[str, Any]) -> str | None:
        turn_id = params.get("turnId")
        if isinstance(turn_id, str):
            return turn_id
        turn = params.get("turn")
        if isinstance(turn, dict):
            nested_turn_id = turn.get("id")
            if isinstance(nested_turn_id, str):
                return nested_turn_id
        return None

    def _handle_turn_completed(self, params: dict[str, Any]) -> None:
        turn = params.get("turn")
        if not isinstance(turn, dict):
            return
        turn_id = turn.get("id")
        if not isinstance(turn_id, str):
            return
        with self._lock:
            task_id = self._turn_to_task.pop(turn_id, None)
            if task_id is None:
                return
            self._task_to_turn.pop(task_id, None)
            self._deadlines.pop(task_id, None)
            for runner_id, (_thread_id, mapped_turn_id) in list(
                self._runner_to_turn.items()
            ):
                if mapped_turn_id == turn_id:
                    self._runner_to_turn.pop(runner_id, None)
            raw_events = self._raw_events.pop(task_id, [])
        status = turn.get("status")
        body = self._completion_body(turn, raw_events=raw_events)
        error = self._turn_error(turn)
        if status == "completed":
            completion_status = "completed"
            summary = self._summary(body)
        else:
            completion_status = "failed"
            summary = error or f"Codex worker turn {status or 'failed'}"
        self._completed.put(
            RunnerCompletion(
                task_id=task_id,
                status=completion_status,
                body=body or summary,
                summary=summary,
                raw_events=raw_events,
                error=None if completion_status == "completed" else summary,
            )
        )

    def _completion_body(self, turn: dict[str, Any], *, raw_events: list[str]) -> str:
        parts: list[str] = []
        items = turn.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("type") == "agentMessage":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
        if parts:
            return "\n\n".join(parts)
        error = self._turn_error(turn)
        if error:
            return error
        raw_body = self._completion_body_from_raw_events(raw_events)
        if raw_body:
            return raw_body
        return json.dumps(turn, sort_keys=True)

    def _completion_body_from_raw_events(self, raw_events: list[str]) -> str:
        completed_fallback: str | None = None
        for raw in reversed(raw_events):
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("method") != "item/completed":
                continue
            params = message.get("params")
            if not isinstance(params, dict):
                continue
            item = params.get("item")
            if not isinstance(item, dict) or item.get("type") != "agentMessage":
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            if item.get("phase") == "final_answer":
                return text.strip()
            completed_fallback = completed_fallback or text.strip()
        if completed_fallback:
            return completed_fallback

        by_item: dict[str, list[str]] = {}
        order: list[str] = []
        for raw in raw_events:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("method") != "item/agentMessage/delta":
                continue
            params = message.get("params")
            if not isinstance(params, dict):
                continue
            item_id = params.get("itemId")
            delta = params.get("delta")
            if not isinstance(item_id, str) or not isinstance(delta, str):
                continue
            if item_id not in by_item:
                by_item[item_id] = []
                order.append(item_id)
            by_item[item_id].append(delta)
        for item_id in reversed(order):
            text = "".join(by_item[item_id]).strip()
            if text:
                return text
        return ""

    def _turn_error(self, turn: dict[str, Any]) -> str | None:
        error = turn.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
            return json.dumps(error, sort_keys=True)
        if isinstance(error, str):
            return error
        return None

    def _summary(self, body: str) -> str:
        return body.strip().replace("\n", " ")[:400]

    def _request(
        self, method: str, params: dict[str, Any] | None, *, timeout: int | float
    ) -> dict[str, Any]:
        process = self.process
        if process is None or process.stdin is None:
            raise RuntimeError("codex app-server is not running")
        request_id = next(self._request_ids)
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._write_message(message)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("codex app-server exited unexpectedly")
            with self._lock:
                response = self._responses.pop(request_id, None)
            if response is not None:
                error = response.get("error")
                if error is not None:
                    raise RuntimeError(
                        f"codex app-server {method} failed: {self._format_error(error)}"
                    )
                return response
            time.sleep(0.01)
        raise RuntimeError(f"codex app-server {method} timed out")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self._write_message(message)

    def _write_message(self, message: dict[str, Any]) -> None:
        process = self.process
        if process is None or process.stdin is None:
            raise RuntimeError("codex app-server is not running")
        try:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except BrokenPipeError as e:
            raise RuntimeError("codex app-server stdin closed") from e

    def _format_error(self, error: Any) -> str:
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
            return json.dumps(error, sort_keys=True)
        return str(error)

    def submit(
        self,
        record: TaskRecord,
        *,
        worker_env: dict[str, str],
        mcp_config: dict[str, object],
    ) -> str:
        """Submit a task to Codex app-server."""
        self.ensure_started(worker_env=worker_env, mcp_config=mcp_config)
        runner_id = f"codex-{next(self._ids)}"
        thread_response = self._request(
            "thread/start",
            {
                "model": record.model,
                "cwd": record.cwd,
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
            },
            timeout=self.startup_timeout_seconds,
        )
        thread_id = self._thread_id(thread_response)
        turn_response = self._request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [
                    {
                        "type": "text",
                        "text": record.prompt,
                        "text_elements": [],
                    }
                ],
                "cwd": record.cwd,
                "approvalPolicy": "never",
                "model": record.model,
                "effort": record.reasoning_effort,
            },
            timeout=self.startup_timeout_seconds,
        )
        turn_id = self._turn_id(turn_response)
        with self._lock:
            self._turn_to_task[turn_id] = record.id
            self._task_to_turn[record.id] = turn_id
            self._runner_to_turn[runner_id] = (thread_id, turn_id)
            self._raw_events[record.id] = []
            self._deadlines[record.id] = time.monotonic() + record.timeout_seconds
        return runner_id

    def _worker_config(
        self, *, worker_env: dict[str, str], mcp_config: dict[str, object]
    ) -> dict[str, Any]:
        server = mcp_config.get("mcpServers")
        config: dict[str, Any] = {}
        if isinstance(server, dict):
            config["mcp_servers"] = self._mcp_servers_config(server, worker_env)
        return config

    def _mcp_servers_config(
        self, mcp_servers: dict[str, object], worker_env: dict[str, str]
    ) -> dict[str, Any]:
        converted: dict[str, Any] = {}
        for name, value in mcp_servers.items():
            if not isinstance(value, dict):
                continue
            item = dict(value)
            env = item.get("env")
            merged_env = dict(worker_env)
            if isinstance(env, dict):
                merged_env.update(
                    {str(env_key): str(env_value) for env_key, env_value in env.items()}
                )
            if merged_env:
                item["env"] = merged_env
            else:
                item.pop("env", None)
            if "allowed_tools" in item:
                item["enabled_tools"] = item.pop("allowed_tools")
            converted[name] = item
        return converted

    def _thread_id(self, response: dict[str, Any]) -> str:
        result = response.get("result")
        if isinstance(result, dict):
            thread = result.get("thread")
            if isinstance(thread, dict):
                thread_id = thread.get("id")
                if isinstance(thread_id, str):
                    return thread_id
        raise RuntimeError("codex app-server thread/start response missing thread id")

    def _turn_id(self, response: dict[str, Any]) -> str:
        result = response.get("result")
        if isinstance(result, dict):
            turn = result.get("turn")
            if isinstance(turn, dict):
                turn_id = turn.get("id")
                if isinstance(turn_id, str):
                    return turn_id
        raise RuntimeError("codex app-server turn/start response missing turn id")

    def poll_completed(self) -> list[RunnerCompletion]:
        """Return completed runner results."""
        self._fail_timed_out_tasks()
        completed: list[RunnerCompletion] = []
        while True:
            try:
                completed.append(self._completed.get_nowait())
            except queue.Empty:
                break
        return completed

    def _fail_timed_out_tasks(self) -> None:
        now = time.monotonic()
        expired: list[tuple[str, str]] = []
        with self._lock:
            for task_id, deadline in list(self._deadlines.items()):
                if now >= deadline:
                    turn_id = self._task_to_turn.pop(task_id, None)
                    self._deadlines.pop(task_id, None)
                    if turn_id:
                        self._turn_to_task.pop(turn_id, None)
                        expired.append((task_id, turn_id))
        for task_id, turn_id in expired:
            self._interrupt_turn(turn_id)
            self._completed.put(
                RunnerCompletion(
                    task_id=task_id,
                    status="failed",
                    body="Codex worker timed out",
                    summary="Codex worker timed out",
                    raw_events=[],
                    error="timeout",
                )
            )

    def cancel(self, runner_id: str) -> str:
        """Request best-effort cancellation for a runner task."""
        with self._lock:
            turn = self._runner_to_turn.get(runner_id)
        if turn is None:
            return "cancel_unknown"
        thread_id, turn_id = turn
        try:
            self._request(
                "turn/interrupt",
                {"threadId": thread_id, "turnId": turn_id},
                timeout=1,
            )
        except RuntimeError:
            return "cancel_unknown"
        return "cancel_unknown"

    def _interrupt_turn(self, turn_id: str) -> None:
        with self._lock:
            match = next(
                (
                    item
                    for item in self._runner_to_turn.values()
                    if item[1] == turn_id
                ),
                None,
            )
        if match is None:
            return
        thread_id, matched_turn_id = match
        try:
            self._request(
                "turn/interrupt",
                {"threadId": thread_id, "turnId": matched_turn_id},
                timeout=1,
            )
        except RuntimeError:
            return

    def clear(self) -> None:
        """Clear runner-side transient state."""
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
        with self._lock:
            self._responses.clear()
            self._raw_events.clear()
            self._turn_to_task.clear()
            self._task_to_turn.clear()
            self._runner_to_turn.clear()
            self._deadlines.clear()
        self.process = None
        self._reader = None
        self._initialized = False
        self._startup_config_key = None
