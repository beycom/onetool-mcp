"""Small lifecycle glue proved in P5; upstream owns connections and processes.

Replacement uses documented Provider extension points. Gap draft:
planning/features/backlog/[gateway]-v4/pocs/upstream-gaps.md#collision-rejection-and-whole-composition-replacement
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from onetool.config import ConfigError, load_config
from onetool.diagnostics import event

if TYPE_CHECKING:
    from onetool.gateway import Gateway


class Operations:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway
        self.accepting = True
        self.active: set[asyncio.Task[object]] = set()
        self.draining: set[asyncio.Task[object]] = set()
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def execution(self) -> AsyncIterator[None]:
        if not self.accepting:
            raise ToolError("Gateway changing; call was not dispatched")
        task = asyncio.current_task()
        assert task is not None
        self.active.add(task)
        try:
            yield
        finally:
            self.active.discard(task)

    async def drain(self) -> None:
        self.accepting = False
        tasks = self.active - {asyncio.current_task()}
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=5)
            for task in pending:
                if task.cancel("Dispatched call outcome unknown; do not replay"):
                    self.draining.add(task)
            try:
                await asyncio.gather(*pending, return_exceptions=True)
            finally:
                self.draining.difference_update(pending)

    async def reload(self) -> dict[str, object]:
        async with self.lock:
            gateway = self.gateway
            try:
                candidate = load_config(gateway.config.path)
            except ConfigError as exc:
                raise ToolError(str(exc)) from None
            if (
                candidate.model.execution != gateway.config.model.execution
                or candidate.model.logging != gateway.config.model.logging
            ):
                raise ToolError("execution or logging changes require a gateway process restart")
            try:
                await self.drain()
                await gateway.close_backends()
                gateway.config = candidate
                gateway.redact.values = candidate.secret_values
                gateway.backends = gateway.build_backends(candidate)
                gateway.revision += 1
            finally:
                self.accepting = True
            event(gateway.logger, "config_reloaded", outcome="success")
            return {
                "revision": gateway.revision,
                "message": (
                    "All upstream state was reset. Connections are lazy. "
                    "Interrupted calls have unknown outcomes; do not replay."
                ),
            }

    async def restart(self, name: str) -> dict[str, str]:
        async with self.lock:
            backend = self.gateway.backends.get(name)
            if backend is None:
                raise ToolError("Unknown server name")
            if not backend.config.enabled:
                raise ToolError(f"{name}: server is disabled in the loaded config")
            try:
                await self.drain()
                await backend.close()
            finally:
                self.accepting = True
            event(self.gateway.logger, "server_restarted", server=name, outcome="success")
            return {
                "server": name,
                "message": (
                    "State reset; next operation reconnects. "
                    "Interrupted calls have unknown outcomes; do not replay."
                ),
            }
