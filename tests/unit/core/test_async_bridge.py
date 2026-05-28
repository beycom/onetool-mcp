"""Tests for sync/async bridge helpers."""

from __future__ import annotations

import pytest

from ot.utils.async_bridge import run_coro_sync


@pytest.mark.unit
@pytest.mark.core
def test_run_coro_sync_without_running_loop() -> None:
    """Bridge runs directly when no event loop is active."""

    async def _value() -> str:
        return "ok"

    assert run_coro_sync(_value()) == "ok"


@pytest.mark.unit
@pytest.mark.core
async def test_run_coro_sync_inside_running_loop() -> None:
    """Bridge completes from inside an already-running event loop."""

    async def _value() -> str:
        return "ok"

    assert run_coro_sync(_value()) == "ok"


@pytest.mark.unit
@pytest.mark.core
async def test_run_coro_sync_propagates_coroutine_exception() -> None:
    """Bridge raises the original coroutine exception."""

    async def _fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_coro_sync(_fail())
