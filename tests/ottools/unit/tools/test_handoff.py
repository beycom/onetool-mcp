"""Unit tests for the handoff tool pack."""

from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ot.handoff.codex_runner import CodexAppServerRunner, RunnerCompletion
from ot.handoff.models import Config, TaskRecord, default_worker_prompt
from ot.handoff.runtime import HandoffRuntime
from ottools import handoff


class FakeRunner:
    def __init__(self) -> None:
        self.started = 0
        self.submitted: list[str] = []
        self.completions: list[RunnerCompletion] = []
        self.cancel_result = "cancel_unknown"
        self.cleared = False

    def ensure_started(
        self,
        *,
        worker_env: dict[str, str] | None = None,
        mcp_config: dict[str, object] | None = None,
    ) -> None:
        del worker_env, mcp_config
        self.started += 1

    def submit(
        self,
        record: TaskRecord,
        *,
        worker_env: dict[str, str],
        mcp_config: dict[str, object],
    ) -> str:
        assert worker_env == {}
        if mcp_config:
            assert mcp_config["mcpServers"]["onetool"]["args"] == [  # type: ignore[index]
                "child",
                "--url",
                "http://127.0.0.1:8765",
            ]
        self.submitted.append(record.id)
        return f"runner-{record.id}"

    def poll_completed(self) -> list[RunnerCompletion]:
        items = self.completions
        self.completions = []
        return items

    def cancel(self, runner_id: str) -> str:
        assert runner_id.startswith("runner-")
        return self.cancel_result

    def clear(self) -> None:
        self.cleared = True


class FakeAppServerStdout:
    def __init__(self) -> None:
        self.lines: queue.Queue[str | None] = queue.Queue()

    def __iter__(self) -> FakeAppServerStdout:
        return self

    def __next__(self) -> str:
        line = self.lines.get()
        if line is None:
            raise StopIteration
        return line

    def send(self, message: dict[str, Any]) -> None:
        self.lines.put(json.dumps(message) + "\n")


class FakeAppServerStdin:
    def __init__(self, process: FakeAppServerProcess) -> None:
        self.process = process
        self.writes: list[dict[str, Any]] = []

    def write(self, text: str) -> int:
        message = json.loads(text)
        self.writes.append(message)
        self.process.handle(message)
        return len(text)

    def flush(self) -> None:
        return None


class FakeAppServerProcess:
    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.stdout = FakeAppServerStdout()
        self.stdin = FakeAppServerStdin(self)
        self.stderr = None
        self.returncode: int | None = None
        self.thread_id = "thread-1"
        self.turn_id = "turn-1"
        self.fail_method: str | None = None
        self.launch_args: list[str] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def handle(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None:
            return
        if method == self.fail_method:
            self.stdout.send(
                {
                    "id": request_id,
                    "error": {"message": f"{method} failed"},
                }
            )
            return
        if method == "initialize":
            self.stdout.send({"id": request_id, "result": {"userAgent": "fake"}})
        elif method == "thread/start":
            self.stdout.send(
                {
                    "id": request_id,
                    "result": {"thread": {"id": self.thread_id}},
                }
            )
        elif method == "turn/start":
            self.stdout.send(
                {
                    "id": request_id,
                    "result": {
                        "turn": {
                            "id": self.turn_id,
                            "status": "inProgress",
                            "items": [],
                            "error": None,
                        }
                    },
                }
            )
        elif method == "turn/interrupt":
            self.stdout.send({"id": request_id, "result": {}})

    def complete(
        self,
        *,
        status: str = "completed",
        text: str = "worker answer",
        items_loaded: bool = True,
    ) -> None:
        self.stdout.send(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": self.thread_id,
                    "turnId": self.turn_id,
                    "itemId": "item-1",
                    "delta": text,
                },
            }
        )
        self.stdout.send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": self.thread_id,
                    "turnId": self.turn_id,
                    "item": {
                        "type": "agentMessage",
                        "id": "item-1",
                        "text": text,
                        "phase": "final_answer",
                        "memoryCitation": None,
                    },
                },
            }
        )
        items = (
            [
                {
                    "type": "agentMessage",
                    "id": "item-1",
                    "text": text,
                    "phase": None,
                    "memoryCitation": None,
                }
            ]
            if items_loaded
            else []
        )
        self.stdout.send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": self.thread_id,
                    "turn": {
                        "id": self.turn_id,
                        "status": status,
                        "items": items,
                        "itemsView": "loaded" if items_loaded else "notLoaded",
                        "error": None
                        if status == "completed"
                        else {"message": "worker failed"},
                    },
                },
            }
        )


def _patch_popen(
    monkeypatch: pytest.MonkeyPatch, process: FakeAppServerProcess
) -> None:
    def fake_popen(*args: object, **_kwargs: object) -> FakeAppServerProcess:
        if args and isinstance(args[0], list):
            process.launch_args = [str(item) for item in args[0]]
        return process

    monkeypatch.setattr("ot.handoff.codex_runner.subprocess.Popen", fake_popen)


def _launch_overrides(process: FakeAppServerProcess) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for index, arg in enumerate(process.launch_args):
        if arg != "-c":
            continue
        key, value = process.launch_args[index + 1].split("=", 1)
        overrides[key] = value
    return overrides


@pytest.fixture
def runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[HandoffRuntime, FakeRunner]:
    monkeypatch.setattr(
        "ot.handoff.runtime.resolve_ot_path",
        lambda p: tmp_path / p,
    )
    monkeypatch.setattr(
        "ot.handoff.child_proxy.current_direct_url",
        lambda: "http://127.0.0.1:8765",
    )
    cfg = Config()
    fake = FakeRunner()
    return HandoffRuntime(config=cfg, cwd=tmp_path, runner=fake), fake


def _record(tmp_path: Path) -> TaskRecord:
    return TaskRecord(
        id="hf-test",
        task="task",
        context="ctx",
        model="gpt-test",
        reasoning_effort="low",
        timeout_seconds=30,
        prompt="prompt",
        cwd=str(tmp_path),
        dedupe_key="key",
    )


@pytest.mark.unit
@pytest.mark.tools
def test_public_pack_metadata() -> None:
    assert handoff.pack == "handoff"
    assert set(handoff.__all__) == {
        "submit",
        "check",
        "read_index",
        "search_index",
        "cancel",
        "clear",
    }
    assert handoff.__ot_requires__["cli"][0][0] == "codex"


@pytest.mark.unit
@pytest.mark.tools
def test_register_services_adds_reload_hook() -> None:
    hooks: list[Any] = []

    class Registry:
        def register_reload_hook(self, hook: Any) -> None:
            hooks.append(hook)

    handoff.register_services(Registry())

    assert hooks
    assert hooks[0].__name__ == "reset_runtime"


@pytest.mark.unit
@pytest.mark.tools
def test_reset_runtime_clears_cached_handoff_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ot.handoff.runtime import get_runtime, reset_runtime

    monkeypatch.setattr("ot.handoff.runtime.resolve_ot_path", lambda p: tmp_path / p)
    cfg = Config()
    fake = FakeRunner()
    first = get_runtime(config=cfg, cwd=tmp_path)
    first._runner = fake

    reset_runtime()
    second = get_runtime(config=cfg, cwd=tmp_path)

    assert fake.cleared is True
    assert second is not first
    reset_runtime()


@pytest.mark.unit
@pytest.mark.tools
def test_codex_runner_submits_and_collects_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = FakeAppServerProcess()
    _patch_popen(monkeypatch, process)
    runner = CodexAppServerRunner(
        command="codex app-server --listen stdio://",
        startup_timeout_seconds=1,
    )

    runner_id = runner.submit(
        _record(tmp_path),
        worker_env={},
        mcp_config={
            "mcpServers": {
                "onetool": {
                    "command": "onetool",
                    "args": ["child", "--url", "http://127.0.0.1:8765"],
                    "env": {"EXISTING": "1"},
                    "allowed_tools": ["run"],
                }
            }
        },
    )
    process.complete(text="The all-check command is `just check`.")
    time.sleep(0.05)

    completed = runner.poll_completed()
    assert runner_id == "codex-1"
    assert completed[0].task_id == "hf-test"
    assert completed[0].status == "completed"
    assert completed[0].body == "The all-check command is `just check`."
    assert completed[0].raw_events

    thread_start = process.stdin.writes[2]
    assert "config" not in thread_start["params"]
    overrides = _launch_overrides(process)
    assert overrides["mcp_servers.onetool.command"] == '"onetool"'
    assert (
        overrides["mcp_servers.onetool.args"]
        == '["child","--url","http://127.0.0.1:8765"]'
    )
    assert overrides["mcp_servers.onetool.enabled_tools"] == '["run"]'
    assert "mcp_servers.onetool.disabled_packs" not in overrides
    assert "mcp_servers.onetool.env.ONETOOL_HANDOFF_ROLE" not in overrides
    assert overrides["mcp_servers.onetool.env.EXISTING"] == '"1"'


@pytest.mark.unit
@pytest.mark.tools
def test_codex_runner_uses_raw_final_answer_when_turn_items_not_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = FakeAppServerProcess()
    _patch_popen(monkeypatch, process)
    runner = CodexAppServerRunner(
        command="codex app-server --listen stdio://",
        startup_timeout_seconds=1,
    )
    runner.submit(_record(tmp_path), worker_env={}, mcp_config={})

    process.complete(
        text="`dev/agents/hints.md:13` lists `just check`.",
        items_loaded=False,
    )
    time.sleep(0.05)

    completed = runner.poll_completed()
    assert completed[0].status == "completed"
    assert completed[0].body == "`dev/agents/hints.md:13` lists `just check`."
    assert completed[0].summary == "`dev/agents/hints.md:13` lists `just check`."


@pytest.mark.unit
@pytest.mark.tools
def test_codex_runner_maps_failed_turn_to_failed_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = FakeAppServerProcess()
    _patch_popen(monkeypatch, process)
    runner = CodexAppServerRunner(
        command="codex app-server --listen stdio://",
        startup_timeout_seconds=1,
    )
    runner.submit(_record(tmp_path), worker_env={}, mcp_config={})

    process.complete(status="failed")
    time.sleep(0.05)

    completed = runner.poll_completed()
    assert completed[0].status == "failed"
    assert completed[0].summary == "worker failed"
    assert completed[0].error == "worker failed"


@pytest.mark.unit
@pytest.mark.tools
def test_codex_runner_surfaces_protocol_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = FakeAppServerProcess()
    process.fail_method = "thread/start"
    _patch_popen(monkeypatch, process)
    runner = CodexAppServerRunner(
        command="codex app-server --listen stdio://",
        startup_timeout_seconds=1,
    )

    with pytest.raises(RuntimeError, match="thread/start failed"):
        runner.submit(_record(tmp_path), worker_env={}, mcp_config={})


@pytest.mark.unit
@pytest.mark.tools
def test_config_rejects_unknown_values_and_renders_prompt() -> None:
    with pytest.raises(ValidationError):
        Config(extra_key=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Config(limits={"max_queue_depth": 0})
    with pytest.raises(ValidationError):
        Config(limits={"max_concurrent_tasks": 2})

    cfg = Config(defaults={"worker_prompt": "Task={task}; Context={context}"})
    rendered = cfg.defaults.worker_prompt.format(
        task="Inspect auth", context="src/ot"
    )
    assert rendered == "Task=Inspect auth; Context=src/ot"
    with pytest.raises(ValidationError):
        Config(defaults={"subagent_prompt": "Task={task}"})

    default_prompt = default_worker_prompt()
    assert Config().defaults.worker_prompt == default_prompt
    assert "{task}" in default_prompt
    assert "{context}" in default_prompt


@pytest.mark.unit
@pytest.mark.tools
def test_handoff_config_surfaces_invalid_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        handoff,
        "_get_raw_config",
        lambda _pack: {"limits": {"max_queue_depth": 0}},
    )

    result = handoff.submit(task="Inspect auth")

    assert isinstance(result, str)
    assert result.startswith("Error: invalid handoff config:")
    assert "max_queue_depth" in result


@pytest.mark.unit
@pytest.mark.tools
def test_submit_validation_defaults_and_dedupe(
    runtime: tuple[HandoffRuntime, FakeRunner],
) -> None:
    rt, fake = runtime
    assert rt.submit(task="")["error"] == "task must not be empty"

    first = rt.submit(task="Inspect auth", context="login")
    assert first["status"] == "submitted"
    assert first["deduped"] is False
    assert first["model"] == "gpt-5.3-codex"
    assert first["reasoning_effort"] == "low"
    assert first["queue_empty"] is False
    assert fake.started == 1

    second = rt.submit(task="Inspect auth", context="login")
    assert second["id"] == first["id"]
    assert second["deduped"] is True
    assert len(fake.submitted) == 1


@pytest.mark.unit
@pytest.mark.tools
def test_queue_full(runtime: tuple[HandoffRuntime, FakeRunner]) -> None:
    rt, _fake = runtime
    rt.config.limits.max_queue_depth = 1
    assert rt.submit(task="one")["status"] == "submitted"
    result = rt.submit(task="two")
    assert result["status"] == "error"
    assert "queue is full" in result["error"]


@pytest.mark.unit
@pytest.mark.tools
def test_worker_limit_queues_tasks(runtime: tuple[HandoffRuntime, FakeRunner]) -> None:
    rt, fake = runtime
    rt.config.limits.max_workers = 1
    assert rt.submit(task="one")["status"] == "submitted"
    result = rt.submit(task="two")
    assert result["status"] == "submitted"
    assert len(fake.submitted) == 1

    fake.completions.append(
        RunnerCompletion(
            task_id=fake.submitted[0],
            status="completed",
            body="Done with first task.",
            summary="First task ready",
        )
    )
    rt.check(wait=True, timeout=1)
    assert len(fake.submitted) == 2


@pytest.mark.unit
@pytest.mark.tools
def test_check_wait_completion_and_remaining_cap(
    runtime: tuple[HandoffRuntime, FakeRunner],
) -> None:
    rt, fake = runtime
    rt.config.limits.max_workers = 2
    one = rt.submit(task="one")
    two = rt.submit(task="two")
    rt.config.limits.max_remaining_ids_returned = 1
    fake.completions.append(
        RunnerCompletion(
            task_id=one["id"],
            status="completed",
            body="Done with auth findings.",
            summary="Auth findings ready",
            raw_events=["event one"],
        )
    )

    result = rt.check(wait=True, timeout=3)
    assert result["completed_count"] == 1
    assert result["ready"][0]["id"] == one["id"]
    assert result["ready"][0]["summary"] == "Auth findings ready"
    assert Path(result["ready"][0]["result_path"]).exists()
    assert Path(result["ready"][0]["raw_log_path"]).exists()
    assert result["remaining_count"] == 1
    assert result["remaining_ids"] == [two["id"]]
    assert result["timed_out"] is False


@pytest.mark.unit
@pytest.mark.tools
def test_check_timeout_and_unknown_ids(
    runtime: tuple[HandoffRuntime, FakeRunner],
) -> None:
    rt, _fake = runtime
    rt.submit(task="pending")
    result = rt.check(ids=["missing"], wait=True, timeout=0)
    assert result["timed_out"] is True
    assert result["unknown_ids"] == ["missing"]


@pytest.mark.unit
@pytest.mark.tools
def test_cancel_return_shapes(runtime: tuple[HandoffRuntime, FakeRunner]) -> None:
    rt, fake = runtime
    one = rt.submit(task="cancel me")
    fake.cancel_result = "cancel_unknown"
    result = rt.cancel(ids=[one["id"], "missing"])
    assert result["cancel_requested"] == [one["id"]]
    assert result["cancel_unknown"] == [one["id"]]
    assert result["not_found"] == ["missing"]

    fake.completions.append(
        RunnerCompletion(
            task_id=one["id"], status="completed", body="late", summary="late"
        )
    )
    # already cancel_requested is still outstanding/non-terminal, so submit another and finish it.
    two = rt.submit(task="finish me")
    fake.completions.append(
        RunnerCompletion(
            task_id=two["id"], status="completed", body="done", summary="done"
        )
    )
    rt.check(wait=True, timeout=1)
    assert rt.cancel(ids=[two["id"]])["already_finished"] == [two["id"]]


@pytest.mark.unit
@pytest.mark.tools
def test_clear_keeps_and_deletes_artifacts(
    runtime: tuple[HandoffRuntime, FakeRunner],
) -> None:
    rt, fake = runtime
    submitted = rt.submit(task="artifact")
    fake.completions.append(
        RunnerCompletion(
            task_id=submitted["id"], status="completed", body="body", summary="sum"
        )
    )
    rt.check(wait=True, timeout=1)
    assert rt.paths.index_path.exists()
    assert list(rt.paths.result_dir.glob("*.md"))

    kept = rt.clear()
    assert kept["queue_empty"] is True
    assert rt.paths.index_path.exists()
    assert fake.cleared is True

    deleted = rt.clear(include_logs=True)
    assert deleted["deleted"]["index"] == 1
    assert not rt.paths.index_path.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_read_and_search_index(runtime: tuple[HandoffRuntime, FakeRunner]) -> None:
    rt, fake = runtime
    rt.config.limits.max_workers = 2
    one = rt.submit(task="Auth audit")
    two = rt.submit(task="Docs audit")
    fake.completions.extend(
        [
            RunnerCompletion(
                task_id=one["id"],
                status="completed",
                body="auth body",
                summary="Auth OK",
            ),
            RunnerCompletion(
                task_id=two["id"],
                status="failed",
                body="docs body",
                summary="Docs blocked",
            ),
        ]
    )
    rt.check(wait=True, timeout=1)

    completed = rt.read_index(status="completed", limit=10)
    assert [row["id"] for row in completed["entries"]] == [one["id"]]
    matches = rt.search_index(query="docs", limit=10)
    assert [row["id"] for row in matches["matches"]] == [two["id"]]


@pytest.mark.unit
@pytest.mark.tools
def test_missing_index_is_empty(runtime: tuple[HandoffRuntime, FakeRunner]) -> None:
    rt, fake = runtime
    assert rt.read_index() == {"index_path": str(rt.paths.index_path), "entries": []}
    assert fake.started == 0


@pytest.mark.unit
@pytest.mark.tools
def test_restart_abandons_non_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ot.handoff.runtime.resolve_ot_path", lambda p: tmp_path / p)
    monkeypatch.setattr(
        "ot.handoff.child_proxy.current_direct_url",
        lambda: "http://127.0.0.1:8765",
    )
    first = HandoffRuntime(config=Config(), cwd=tmp_path, runner=FakeRunner())
    submitted = first.submit(task="pending")

    second = HandoffRuntime(config=Config(), cwd=tmp_path, runner=FakeRunner())
    rows = second.read_index()["entries"]
    assert rows[0]["id"] == submitted["id"]
    assert rows[0]["status"] == "abandoned"


@pytest.mark.unit
@pytest.mark.tools
def test_cleanup_preserves_active_and_retained_raw_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ot.handoff.runtime.resolve_ot_path", lambda p: tmp_path / p)
    cfg = Config(cleanup={"enabled": False})
    rt = HandoffRuntime(config=cfg, cwd=tmp_path, runner=FakeRunner())
    old = TaskRecord(
        id="old",
        task="old",
        context="",
        model="m",
        reasoning_effort="low",
        timeout_seconds=1,
        prompt="p",
        cwd=str(tmp_path),
        dedupe_key="old",
        status="completed",
        completed_at=time.time() - 10 * 86400,
        result_path=str(rt.paths.result_dir / "old.md"),
        raw_log_path=str(rt.paths.raw_log_dir / "old.log"),
    )
    active = TaskRecord(
        id="active",
        task="active",
        context="",
        model="m",
        reasoning_effort="low",
        timeout_seconds=1,
        prompt="p",
        cwd=str(tmp_path),
        dedupe_key="active",
        status="running",
    )
    rt._records = {"old": old, "active": active}
    Path(old.result_path).write_text("old", encoding="utf-8")
    Path(old.raw_log_path).write_text("old", encoding="utf-8")
    rt._save_state()

    cleaned = HandoffRuntime(
        config=Config(cleanup={"enabled": True, "max_age_days": 1}),
        cwd=tmp_path,
        runner=FakeRunner(),
    )
    assert "active" in cleaned._records
    assert "old" not in cleaned._records
    assert not Path(old.result_path).exists()
    assert not Path(old.raw_log_path).exists()


@pytest.mark.unit
@pytest.mark.tools
def test_child_unavailable_warns_and_starts_without_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ot.handoff.runtime.resolve_ot_path", lambda p: tmp_path / p)
    monkeypatch.setattr("ot.handoff.child_proxy.current_direct_url", lambda: None)
    fake = FakeRunner()
    rt = HandoffRuntime(config=Config(), cwd=tmp_path, runner=fake)
    result = rt.submit(task="needs tools")
    assert result["status"] == "submitted"
    assert result["warnings"]
    assert "MCP tools could not be enabled" in result["warnings"][0]
    assert fake.started == 1


@pytest.mark.unit
@pytest.mark.tools
def test_public_tools_return_native_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ottools.handoff._get_raw_config", lambda _pack: {})
    monkeypatch.setattr("ottools.handoff.get_effective_cwd", lambda: tmp_path)
    monkeypatch.setattr("ot.handoff.runtime.resolve_ot_path", lambda p: tmp_path / p)
    monkeypatch.setattr("ot.handoff.child_proxy.current_direct_url", lambda: None)
    from ot.handoff.runtime import reset_runtime

    reset_runtime()
    result = handoff.read_index()
    assert isinstance(result, dict)
    assert "index_path" in result
    submit_result = handoff.submit(task="x")
    assert isinstance(submit_result, dict)
    assert submit_result["status"] == "submitted"
    assert submit_result["warnings"]
