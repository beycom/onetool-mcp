"""Bounded admission and lifecycle accounting for in-process execution."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

EXECUTION_CAPACITY = 8


class ExecutionCapacityError(RuntimeError):
    """Raised when no in-process execution slot is available."""


class _ExecutionController:
    """Own execution slots until their underlying threads actually finish."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=capacity,
            thread_name_prefix="ot-exec",
        )
        self._futures: set[concurrent.futures.Future[Any]] = set()
        self._accepting = True
        self._lock = threading.Lock()

    def start(self) -> None:
        """Open admission for a new server lifespan."""
        with self._lock:
            if self._futures:
                raise RuntimeError(
                    "cannot open execution admission while work is still active"
                )
            self._accepting = True

    def submit(
        self,
        function: Callable[..., T],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> concurrent.futures.Future[T]:
        """Submit work if a process-global slot is available."""
        with self._lock:
            if not self._accepting:
                raise ExecutionCapacityError(
                    "in-process execution is unavailable during shutdown"
                )
            if len(self._futures) >= self._capacity:
                raise ExecutionCapacityError(
                    f"in-process execution capacity is full ({self._capacity} jobs)"
                )
            future = self._executor.submit(function, *args, **kwargs)
            self._futures.add(future)

        future.add_done_callback(self._on_done)
        return future

    def _on_done(self, future: concurrent.futures.Future[Any]) -> None:
        """Observe failures and release the slot on actual thread completion."""
        try:
            future.exception()
        except concurrent.futures.CancelledError:
            pass
        finally:
            with self._lock:
                self._futures.discard(future)

    def state(self) -> dict[str, int | bool]:
        """Return a thread-safe accounting snapshot."""
        with self._lock:
            return {
                "capacity": self._capacity,
                "active": len(self._futures),
                "accepting": self._accepting,
            }

    async def shutdown(self) -> None:
        """Close admission and wait for every admitted thread to finish."""
        with self._lock:
            self._accepting = False
            futures = tuple(self._futures)

        if futures:
            await asyncio.gather(
                *(asyncio.wrap_future(future) for future in futures),
                return_exceptions=True,
            )


_CONTROLLER = _ExecutionController(EXECUTION_CAPACITY)


def start_execution_admission() -> None:
    """Open admission for a new MCP server lifespan."""
    _CONTROLLER.start()


def submit_execution(
    function: Callable[..., T],
    /,
    *args: Any,
    **kwargs: Any,
) -> concurrent.futures.Future[T]:
    """Submit one in-process job under the global capacity bound."""
    return _CONTROLLER.submit(function, *args, **kwargs)


def execution_work_state() -> dict[str, int | bool]:
    """Return current execution capacity and admitted-work accounting."""
    return _CONTROLLER.state()


async def shutdown_execution_admission() -> None:
    """Stop admission and drain all admitted in-process work."""
    await _CONTROLLER.shutdown()


__all__ = [
    "EXECUTION_CAPACITY",
    "ExecutionCapacityError",
    "execution_work_state",
    "shutdown_execution_admission",
    "start_execution_admission",
    "submit_execution",
]
