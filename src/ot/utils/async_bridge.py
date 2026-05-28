"""Helpers for running async work from synchronous APIs."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Coroutine

T = TypeVar("T")


def run_coro_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion from synchronous code.

    Uses ``asyncio.run`` when no event loop is running in the current thread.
    When called from inside a running event loop, runs the coroutine in a
    dedicated worker thread with its own event loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    sentinel = object()
    result: T | object = sentinel
    error: BaseException | None = None

    def _runner() -> None:
        nonlocal error, result
        try:
            result = asyncio.run(coro)
        except BaseException as exc:
            error = exc

    thread = threading.Thread(target=_runner, name="ot-async-bridge", daemon=True)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    if result is sentinel:
        raise RuntimeError("coroutine completed without a result or exception")
    return cast("T", result)
