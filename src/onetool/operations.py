"""Small lifecycle glue proved in P5; upstream owns connections and processes.

Replacement uses documented Provider extension points. Gap draft:
planning/features/ready/[gateway]-v4/pocs/upstream-gaps.md#collision-rejection-and-whole-composition-replacement
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import anyio
from fastmcp.exceptions import ToolError

from onetool.config import ConfigError, load_config
from onetool.diagnostics import event

if TYPE_CHECKING:
    from onetool.gateway import Gateway


class UnknownOutcome(ToolError):
    """A dispatched operation was interrupted; automatic replay is forbidden."""


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

    async def servers(self, action: str, name: str | None) -> dict[str, Any]:
        gateway = self.gateway
        if action not in {"list", "status", "enable", "disable", "restart"}:
            raise ToolError("action must be list, status, enable, disable or restart")
        if action == "list":
            return {"servers": gateway.status()["servers"]}
        if name not in gateway.backends:
            raise ToolError("Unknown server; configured names: " + ", ".join(gateway.backends))
        assert name is not None
        if action == "status":
            return {"server": name, **gateway.status()["servers"][name]}
        # Serialize controls with whole-composition reload; other-server calls continue.
        async with self.lock:
            backend = gateway.backends[name]
            candidate = None
            if action == "restart":
                from onetool.gateway import Backend

                try:
                    candidate = load_config(gateway.config.path)
                except ConfigError as exc:
                    raise ToolError(str(exc)) from None
                if name not in candidate.model.servers:
                    raise ToolError("Server absent from disk config; use reload to apply removals")
            if action == "disable":
                backend.session_enabled = False
            if action in {"disable", "restart"}:
                backend.accepting = False
                try:
                    tasks = set(backend.active)
                    if tasks:
                        _, pending = await asyncio.wait(tasks, timeout=5)
                        for task in pending:
                            if task.cancel():
                                backend.draining.add(task)
                        with anyio.CancelScope(shield=True):
                            await asyncio.gather(*pending, return_exceptions=True)
                finally:
                    with anyio.CancelScope(shield=True):
                        await backend.close()
                    backend.accepting = True
            details: dict[str, Any] = {}
            if candidate is not None:
                pending_names = [
                    n
                    for n in set(candidate.model.servers) | set(gateway.config.model.servers)
                    if n != name
                    and candidate.model.servers.get(n) != gateway.config.model.servers.get(n)
                ]
                restart_required = [
                    key
                    for key in ("execution", "logging")
                    if getattr(candidate.model, key) != getattr(gateway.config.model, key)
                ]
                configs = {**gateway.config.model.servers, name: candidate.model.servers[name]}
                secrets = tuple(
                    sorted(
                        set(gateway.config.secret_values + candidate.secret_values),
                        key=len,
                        reverse=True,
                    )
                )
                gateway.config = replace(
                    gateway.config,
                    model=gateway.config.model.model_copy(update={"servers": configs}),
                    secret_values=secrets,
                    env_names=gateway.config.env_names | candidate.env_names,
                )
                gateway.redact.values = secrets
                backend = Backend(gateway, name, candidate.model.servers[name])
                gateway.backends[name] = backend
                details = {
                    "pending_servers": sorted(pending_names),
                    "restart_required": restart_required,
                    "message": (
                        "Named server refreshed; reload applies other definitions. "
                        "Interrupted outcomes are unknown; do not replay."
                    ),
                }
            if action in {"enable", "restart"}:
                backend.session_enabled = True
                if backend.state != "ready":
                    backend.state = "connecting"
                    try:
                        await backend.provider.list_tools()
                    except Exception:
                        details["error_category"] = "unavailable"
            else:
                backend.state = "disabled"
            return {"server": name, **gateway.status()["servers"][name], **details}
