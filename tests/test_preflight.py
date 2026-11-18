"""Static errors stop side effects; cached check never runs submitted statements."""

import ast
import json
from pathlib import Path

import pytest
from mcp import types as mt
from test_gateway import connected, execute, stdio

from onetool.preflight import references


@pytest.mark.parametrize(
    "third",
    [
        "return await alpha.ad(a=1,b=2)",
        'return await call_tool("alpha_typo", {})',
        "return await alpha.add(wrong=1,b=2)",
        'return await call_tools([("alpha_typo",{})])',
    ],
)
async def test_static_third_call_stops_before_first_business_call(
    tmp_path: Path, third: str
) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, stderr):
        result = await execute(
            client,
            "await alpha.add(a=1,b=2)\nawait alpha.counter()\n" + third,
            raise_on_error=False,
        )
        assert result.is_error and "line 3" in str(result.content)
        assert "Preflight" in str(result.content)
        observed = [json.loads(line)["event"] for line in events.read_text().splitlines()]
        assert set(observed) <= {"start", "list-tools"}
        assert "alpha_typo" not in stderr.read_text() and "wrong=1" not in stderr.read_text()


async def test_check_is_cached_nonexecuting_and_computed_calls_run(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):

        async def check(code: str):
            result = await client.session.send_request(
                mt.CallToolRequest(
                    params=mt.CallToolRequestParams(name="check", arguments={"code": code})
                ),
                mt.CallToolResult,
            )
            assert not result.is_error
            return result.structured_content

        first = await check("while True:\n    pass\nimport subprocess\nawait alpha.add(a=1,b=2)")
        assert not events.exists()
        assert first["catalog"]["unknown_servers"] == ["alpha"]
        assert first["warnings"] and "Provisional" in first["syntax"]
        await client.call_tool("onetool_servers", {"action": "enable", "name": "alpha"})
        before = events.read_text()
        bad = await check("await alpha.add(a=1,b=2)\nreturn await alpha.typo()")
        assert not bad["valid"] and bad["errors"][0]["line"] == 2
        assert bad["catalog"]["age_seconds"]["alpha"] >= 0
        computed = 'name="alpha_add"\nargs={"a":2,"b":3}\nreturn await call_tool(name,args)'
        advisory = await check(computed)
        assert advisory["valid"] and advisory["warnings"]
        assert events.read_text() == before  # no refresh, worker or business call from check
        assert (await execute(client, computed)).data == {"value": 5}
        local = 'alpha={"x":1}\nreturn alpha.get("x")'
        assert (await check(local))["warnings"]
        assert (await execute(client, local)).content[0].text == "1"
        syntax = await check("x =")
        assert not syntax["valid"] and syntax["errors"][0]["line"] == 1


async def test_native_syntax_failure_has_no_upstream_activity(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        result = await client.session.send_request(
            mt.CallToolRequest(
                params=mt.CallToolRequestParams(
                    name="execute",
                    arguments={"code": "x ="},
                )
            ),
            mt.CallToolResult,
        )
        assert result.is_error and (
            "line 1" in str(result.content) or "submitted.py:1" in str(result.content)
        )
        assert not events.exists()


def test_static_walk_leaves_computed_and_shadowed_names_unresolved() -> None:
    calls = references(ast.parse('alpha={}\nalpha.get("a")\ncall_tool(name, args)'), {"alpha"})
    assert len(calls) == 2 and all(name is None for _, name, _ in calls)
