"""One compact help surface over observed/native catalog metadata."""

from __future__ import annotations

import asyncio
import builtins
import difflib
import keyword
from typing import TYPE_CHECKING, Any, Literal

from fastmcp.tools import Tool

if TYPE_CHECKING:
    from onetool.gateway import Gateway


class Discovery:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway

    def factory(self, get_catalog: Any) -> Tool:
        return Tool.from_function(self.help, name="help")

    async def help(
        self,
        query: str | None = None,
        detail: Literal["names", "default", "signatures", "full"] = "default",
    ) -> dict[str, Any]:
        """Overview, exact tool/server detail, or grouped discovery matches; never dispatch."""
        gateway = self.gateway
        for backend in gateway.backends.values():
            if backend.enabled and backend.state == "ready":
                try:
                    backend.observe_tools(await backend.provider.list_tools())
                except Exception:
                    pass  # Middleware retains the safe availability error.
        tools = {
            tool.name: tool
            for backend in gateway.backends.values()
            if backend.enabled
            for tool in backend.observed_tools
            if backend.state == "ready"
        }
        servers = gateway.status_snapshot()["servers"]
        if not query:
            data = {
                "servers": servers,
                "usage": ("await server.tool(**kwargs) or await call_tool(exact_name, arguments)"),
                "admin": ["onetool_status", "onetool_servers", "onetool_reload", "onetool_results"],
                "hint": "Enable a lazy server for discovery; inspect get_schema before calling.",
            }
        elif query in tools:
            tool = tools[query]
            data = self.tool_detail(tool, detail)
        elif query in servers:
            backend = gateway.backends[query]
            data = {
                "server": query,
                **servers[query],
                "configured_instructions": backend.config.instructions,
                "tools": [
                    self.tool_detail(tool, detail)
                    for tool in backend.observed_tools
                    if backend.state == "ready"
                ],
            }
            if backend.state == "ready":
                try:
                    resources, prompts = await asyncio.gather(
                        backend.provider.list_resources()
                        if backend.capabilities.get("resources")
                        else self.empty(),
                        backend.provider.list_prompts()
                        if backend.capabilities.get("prompts")
                        else self.empty(),
                    )
                    data["resources"] = [str(resource.uri) for resource in resources]
                    data["prompts"] = [prompt.name for prompt in prompts]
                except Exception:
                    data["capability_warning"] = "Resource/prompt metadata unavailable"
            else:
                data["next_action"] = f'Use onetool_servers(action="enable", name="{query}")'
        else:
            lowered = query.casefold()
            close = set(difflib.get_close_matches(query, list(tools) + list(servers), n=5))
            server_matches = [
                name
                for name, info in servers.items()
                if name in close
                or lowered in name.casefold()
                or lowered in (info.get("description") or "").casefold()
            ]
            tool_matches = [
                tool
                for name, tool in tools.items()
                if name in close
                or lowered in name.casefold()
                or lowered in (tool.description or "").casefold()
            ]
            data = {
                "servers": {name: servers[name] for name in sorted(server_matches)},
                "tools": [
                    self.tool_detail(tool, detail)
                    for tool in sorted(tool_matches, key=lambda t: t.name)
                ],
            }
        return gateway.results.fit(data)

    @staticmethod
    async def empty() -> list[Any]:
        return []

    def tool_detail(self, tool: Tool, detail: str) -> dict[str, Any]:
        if detail == "names":
            return {"name": tool.name}
        server = max(
            (name for name in self.gateway.backends if tool.name.startswith(name + "_")), key=len
        )
        member = tool.name[len(server) + 1 :]
        properties = tool.parameters.get("properties", {})
        required = set(tool.parameters.get("required", []))
        params = [
            name if name in required else name + "=" + repr(schema.get("default", None))
            for name, schema in properties.items()
        ]
        dotted = (
            member.isidentifier()
            and not keyword.iskeyword(member)
            and not keyword.iskeyword(server)
            and not hasattr(builtins, server)
        )
        signature = (
            f"{server}.{member}(" + ", ".join(params) + ")"
            if dotted
            else f"call_tool({tool.name!r}, arguments)"
        )
        data: dict[str, Any] = {
            "name": tool.name,
            "signature": signature,
            "description": tool.description,
        }
        if detail == "signatures":
            return {"signature": signature + "  # " + (tool.description or "").split("\n")[0]}
        if detail == "full":
            data["parameters"] = tool.parameters
            data["call_tool"] = f'await call_tool("{tool.name}", arguments)'
        return data
