"""Resource and lifecycle tests for bounded in-process execution."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

import pytest

from ot.executor.admission import (
    EXECUTION_CAPACITY,
    execution_work_state,
    shutdown_execution_admission,
    start_execution_admission,
)
from ot.executor.runner import execute_command

if TYPE_CHECKING:
    from collections.abc import Callable


async def _wait_for_state(
    predicate: Callable[[dict[str, int | bool]], bool],
) -> dict[str, int | bool]:
    """Wait briefly for concurrent-future completion callbacks to update state."""
    for _ in range(200):
        state = execution_work_state()
        if predicate(state):
            return state
        await asyncio.sleep(0.01)
    raise AssertionError(f"execution state did not converge: {execution_work_state()}")


def _result_tuple(value: str = "done") -> tuple[str, Any, bool, str, bool, None]:
    return (value, None, True, "json", False, None)


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_timed_out_jobs_fill_capacity_until_threads_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eight detached threads reject overflow and completion restores capacity."""
    import ot.executor.runner as runner

    start_execution_admission()
    release = threading.Event()
    started = 0
    started_lock = threading.Lock()

    def blocked(*_args: Any, **_kwargs: Any) -> tuple[str, Any, bool, str, bool, None]:
        nonlocal started
        with started_lock:
            started += 1
        release.wait(timeout=5)
        return _result_tuple()

    monkeypatch.setattr(runner, "_TOOL_EXECUTION_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr(runner, "execute_python_code", blocked)

    try:
        timed_out = await asyncio.gather(
            *(execute_command(f"{index} + 1") for index in range(EXECUTION_CAPACITY))
        )

        assert all(result.error_type == "TimeoutError" for result in timed_out)
        assert execution_work_state() == {
            "capacity": EXECUTION_CAPACITY,
            "active": EXECUTION_CAPACITY,
            "accepting": True,
        }
        assert started == EXECUTION_CAPACITY

        overflow = await execute_command("100 + 1")
        assert overflow.error_type == "ExecutionCapacityError"
        assert "capacity is full" in overflow.result
        assert started == EXECUTION_CAPACITY

        release.set()
        await _wait_for_state(lambda state: state["active"] == 0)

        admitted = await execute_command("200 + 1")
        assert admitted.success is True
    finally:
        release.set()
        await shutdown_execution_admission()
        start_execution_admission()


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_timeout_allows_side_effect_and_releases_on_real_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A soft timeout does not terminate side effects or release early."""
    import ot.executor.runner as runner

    start_execution_admission()
    release = threading.Event()
    side_effects: list[str] = []

    def blocked(*_args: Any, **_kwargs: Any) -> tuple[str, Any, bool, str, bool, None]:
        release.wait(timeout=5)
        side_effects.append("completed")
        return _result_tuple()

    monkeypatch.setattr(runner, "_TOOL_EXECUTION_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr(runner, "execute_python_code", blocked)

    try:
        result = await execute_command("1 + 1")
        assert result.error_type == "TimeoutError"
        assert side_effects == []
        assert execution_work_state()["active"] == 1

        release.set()
        await _wait_for_state(lambda state: state["active"] == 0)
        assert side_effects == ["completed"]
    finally:
        release.set()
        await shutdown_execution_admission()
        start_execution_admission()


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_caller_cancellation_keeps_underlying_job_accounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelling the awaiting coroutine does not cancel its concurrent future."""
    import ot.executor.runner as runner

    start_execution_admission()
    started = threading.Event()
    release = threading.Event()

    def blocked(*_args: Any, **_kwargs: Any) -> tuple[str, Any, bool, str, bool, None]:
        started.set()
        release.wait(timeout=5)
        return _result_tuple()

    monkeypatch.setattr(runner, "execute_python_code", blocked)
    task = asyncio.create_task(execute_command("1 + 1"))

    try:
        await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert execution_work_state()["active"] == 1
        release.set()
        await _wait_for_state(lambda state: state["active"] == 0)
    finally:
        release.set()
        await shutdown_execution_admission()
        start_execution_admission()


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.asyncio
async def test_shutdown_closes_admission_and_waits_for_detached_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown stays pending until a timed-out underlying thread completes."""
    import ot.executor.runner as runner

    start_execution_admission()
    release = threading.Event()

    def blocked(*_args: Any, **_kwargs: Any) -> tuple[str, Any, bool, str, bool, None]:
        release.wait(timeout=5)
        return _result_tuple()

    monkeypatch.setattr(runner, "_TOOL_EXECUTION_TIMEOUT_SECS", 0.05)
    monkeypatch.setattr(runner, "execute_python_code", blocked)

    try:
        result = await execute_command("1 + 1")
        assert result.error_type == "TimeoutError"

        shutdown_task = asyncio.create_task(shutdown_execution_admission())
        await asyncio.sleep(0)
        assert shutdown_task.done() is False
        assert execution_work_state()["accepting"] is False

        rejected = await execute_command("2 + 2")
        assert rejected.error_type == "ExecutionCapacityError"
        assert "unavailable during shutdown" in rejected.result

        release.set()
        await asyncio.wait_for(shutdown_task, timeout=1)
        assert execution_work_state() == {
            "capacity": EXECUTION_CAPACITY,
            "active": 0,
            "accepting": False,
        }
    finally:
        release.set()
        await shutdown_execution_admission()
        start_execution_admission()
