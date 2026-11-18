"""Read-only measured sandbox diagnostics and owned recovery categories."""

from pathlib import Path

from mcp import types as mt
from test_gateway import connected, execute, stdio


async def test_status_imports_and_failures_are_lazy_and_cached(tmp_path: Path) -> None:
    events = tmp_path / "upstream.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events, enabled=False)}}) as (
        client,
        _,
        _,
    ):

        async def status(check: str):
            result = await client.session.send_request(
                mt.CallToolRequest(
                    params=mt.CallToolRequestParams(
                        name="onetool_status",
                        arguments={"check": check},
                    )
                ),
                mt.CallToolResult,
            )
            return result.structured_content

        first = await status("json")
        missing = await status("uuid")
        again = await status("json")
        assert first["sandbox"]["imports"] == again["sandbox"]["imports"] == {"json": True}
        assert missing["sandbox"]["imports"] == {"uuid": False}
        assert not events.exists()
        assert first["config"]["sources"] and first["sandbox"]["limits"]["max_tool_calls"] == 50
        unavailable = await execute(
            client, 'return await call_tool("alpha_add", {})', raise_on_error=False
        )
        assert unavailable.meta["onetool"]["category"] == "unavailable"
        bad_config = await execute(client, "return undefined_name", raise_on_error=False)
        assert bad_config.meta["onetool"]["category"] == "config"
        assert all(result.meta["onetool"]["next_action"] for result in [unavailable, bad_config])
        assert not events.exists()


async def test_sandbox_limit_has_distinct_recovery(tmp_path: Path) -> None:
    async with connected(
        tmp_path,
        {
            "servers": {"alpha": stdio()},
            "execution": {"max_tool_calls": 1},
        },
    ) as (client, _, _):
        result = await execute(
            client,
            "await alpha.add(a=1,b=2)\nreturn await alpha.add(a=2,b=3)",
            raise_on_error=False,
        )
        assert result.is_error and result.meta["onetool"]["category"] == "sandbox_limit"
        assert "Reduce" in result.meta["onetool"]["next_action"]
