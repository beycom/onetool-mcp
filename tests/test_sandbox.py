"""OneTool-owned sandbox behavior through the real gateway/fixture protocol."""

import asyncio
import json
from pathlib import Path

import pytest
import yaml
from fastmcp.exceptions import ToolError
from test_gateway import connected, execute, stdio

from onetool.sandbox import prepare, safe_value


def test_prepare_retains_lines_and_inner_fences() -> None:
    assert prepare('```python\n    x = "```"\n    return x\n```') == '\nx = "```"\nreturn x\n'
    with pytest.raises(ToolError, match="empty"):
        prepare("```py\n\n```")
    assert safe_value({"nan": float("nan"), "set": {1}, "surrogate": "\ud800"}) == {
        "nan": "nan",
        "set": "{1}",
        "surrogate": "?",
    }


async def test_dot_calls_preparation_names_and_print_hygiene(tmp_path: Path) -> None:
    log = tmp_path / "gateway.log"
    events = {name: tmp_path / f"{name}.jsonl" for name in ("alpha", "beta")}
    async with connected(
        tmp_path,
        {
            "servers": {name: stdio(path) for name, path in events.items()},
            "logging": {"file": str(log)},
        },
    ) as (client, _, stderr):
        chain = 'a = await alpha.add(a=2,b=3)\nreturn await beta.add(a=a["value"],b=4)'
        dot = await execute(client, chain)
        native = await execute(
            client,
            'a = await call_tool("alpha_add", {"a":2,"b":3})\n'
            'return await call_tool("beta_add", {"a":a["value"],"b":4})',
        )
        assert dot.data == native.data == {"value": 9}
        # Each chain has exactly one add on each fixture, without fuzzy dispatch.
        for path in events.values():
            assert [json.loads(line)["event"] for line in path.read_text().splitlines()].count(
                "add"
            ) == 2
        assert (await execute(client, "```py\n    return await alpha.add(a=1,b=2)\n```")).data == {
            "value": 3
        }
        assert (
            await execute(client, 'return await call_tool("alpha_odd-tool", {"value":"exact"})')
        ).data == {"value": "exact"}
        for code in [
            'await alpha.odd_tool(value="no alias")',
            "await alhpa.add(a=1,b=2)",
            "await alpha.ad(a=1,b=2)",
            "await alpha.add(aa=1,b=2)",
        ]:
            failure = await execute(client, code, raise_on_error=False)
            assert failure.is_error and (
                "alpha" in str(failure.content) or "parameter" in str(failure.content)
            )
        outputs = {}

        async def capture(token: str) -> None:
            value = await execute(
                client, f'print("{token}")\nawait alpha.delay(seconds=0.05)\nreturn {{"value":1}}'
            )
            text = "".join(c.text for c in value.content)
            assert token in text
            outputs[token] = text

        await asyncio.gather(capture("unique-first-print"), capture("unique-second-print"))
        assert (
            "unique-second-print" not in outputs["unique-first-print"]
            and "unique-first-print" not in outputs["unique-second-print"]
        )
        sentinel = '{"jsonrpc":"2.0","id":"printed-sentinel","method":"bad"}'
        result = await execute(client, f"print({sentinel!r})\nreturn 42")
        assert sentinel in str(result.content)
        failed = await execute(
            client, 'print("before-error-sentinel")\nreturn 1/0', raise_on_error=False
        )
        assert failed.is_error and "before-error-sentinel" in str(failed.content)
        assert (await execute(client, "return 42")).content[0].text == "42"
    for path in [stderr, log]:
        text = path.read_text()
        assert all(
            token not in text
            for token in [
                "unique-first-print",
                "unique-second-print",
                "printed-sentinel",
                "before-error-sentinel",
            ]
        )


@pytest.mark.parametrize("format", ["json", "json-indent", "yaml", "yaml-block", "text"])
async def test_formats_preserve_native_value(tmp_path: Path, format: str) -> None:
    async with connected(tmp_path, {"servers": {}}) as (client, _, _):
        result = await execute(
            client, f'set_format("{format}")\nreturn {{"name":"café","items":[1,2]}}'
        )
        assert result.data == {"name": "café", "items": [1, 2]}
        if format != "text":
            decoder = yaml.safe_load if format.startswith("yaml") else json.loads
            assert decoder(result.content[0].text) == result.data


async def test_batch_partial_order_budget_and_shape(tmp_path: Path) -> None:
    async with connected(
        tmp_path, {"servers": {"alpha": stdio()}, "execution": {"max_tool_calls": 60}}
    ) as (client, _, _):
        result = await execute(
            client,
            'return await call_tools([("alpha_delay",{"seconds":0.05}),'
            '("alpha_fail",{}),("alpha_add",{"a":2,"b":3})], concurrency=2)',
        )
        data = json.loads(result.content[0].text)
        assert [x["status"] for x in data] == ["ok", "error", "ok"]
        assert [x["index"] for x in data] == [0, 1, 2] and data[2]["value"] == {"value": 5}
        many = await execute(
            client,
            'return await call_tools([("alpha_counter",{}) for x in range(60)], concurrency=4)',
        )
        assert all(x["status"] == "ok" for x in json.loads(many.content[0].text))
        invalid = await execute(
            client,
            'return await call_tools([("alpha_counter",{}),{"bad":1}])',
            raise_on_error=False,
        )
        assert invalid.is_error
        next_counter = await execute(client, "return await alpha.counter()")
        assert next_counter.data["count"] == 61
    async with connected(
        tmp_path / "limited", {"servers": {"alpha": stdio()}, "execution": {"max_tool_calls": 2}}
    ) as (client, _, _):
        result = await execute(
            client,
            'return await call_tools([("alpha_counter",{}) for x in range(4)], concurrency=4)',
        )
        assert [x["status"] for x in json.loads(result.content[0].text)] == [
            "ok",
            "ok",
            "cancelled",
            "cancelled",
        ]


async def test_shadowing_helpers_and_source_locations(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {"len": stdio(), "alpha": stdio()}}) as (
        client,
        _,
        _,
    ):
        assert (await execute(client, 'return await call_tool("len_add", {"a":1,"b":2})')).data == {
            "value": 3
        }
        failure = await execute(client, "return await len.add(a=1,b=2)", raise_on_error=False)
        assert failure.is_error
        failure = await execute(
            client, "alpha=1\nreturn await alpha.add(a=1,b=2)", raise_on_error=False
        )
        assert failure.is_error
        failure = await execute(
            client, "```python\n    value=1\n    return 1/0\n```", raise_on_error=False
        )
        assert failure.is_error and "line 3" in str(failure.content)
        for code, text in [
            ("42", "42"),
            ("return None", ""),
            ("x=1", ""),
            ("if True:\n    42", ""),
            ("def f():\n    return 42\nreturn f()", "42"),
        ]:
            result = await execute(client, code)
            assert not result.is_error
            if text:
                assert result.content[0].text == text


async def test_print_cap_and_stored_native_value(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}, "execution": {"max_output_bytes": 1024}}) as (
        client,
        _,
        _,
    ):
        result = await execute(client, 'print("x"*3000)')
        text = str(result.content)
        if result.structured_content and "path" in result.structured_content:
            saved = json.loads(Path(result.structured_content["path"]).read_text())
            text = str(saved["content"])
        assert "truncated" in text.lower()
        result = await execute(client, 'set_format("yaml-block")\nreturn {"large":"x"*3000}')
        data = json.loads(Path(result.data["path"]).read_text())
        assert data["structured_content"] == {"large": "x" * 3000}
        assert json.loads(data["content"][0]["text"]) == data["structured_content"]
        failed = await execute(
            client, 'set_format("invalid")\nprint("should-not-run")', raise_on_error=False
        )
        assert failed.is_error and "should-not-run" not in str(failed.content)


async def test_batch_deadline_keeps_order_and_unknowns(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events)}, "execution": {"timeout_seconds": 1}}
    ) as (client, _, _):
        # Warm the catalog before the one-second deadline proof.
        await client.call_tool("search", {"query": "append_wait"})
        result = await execute(
            client,
            'return await call_tools([("alpha_append_wait",{"seconds":30}) '
            "for x in range(3)], concurrency=1)",
        )
        assert not result.is_error, result
        outcomes = json.loads(result.content[0].text)
        assert [item["status"] for item in outcomes] == ["unknown", "cancelled", "cancelled"]
        assert (await execute(client, "return 42")).content[0].text == "42"
    recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
    assert recorded.count("append-wait") == 1 and recorded.count("append-wait-cancelled") == 1


async def test_batch_concurrency_bounds(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        for concurrency in [1, 4, 16]:
            before = len(events.read_text().splitlines()) if events.exists() else 0
            result = await execute(
                client,
                'return await call_tools([("alpha_delay",{"seconds":0.03}) '
                f"for x in range(16)], concurrency={concurrency})",
            )
            assert not result.is_error
            running = peak = 0
            for line in events.read_text().splitlines()[before:]:
                event = json.loads(line)["event"]
                running += 1 if event == "delay-start" else -1 if event == "delay-complete" else 0
                peak = max(peak, running)
            assert running == 0 and peak <= concurrency and peak > 0


async def test_dot_client_cancellation_and_next_request(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        task = asyncio.create_task(execute(client, "return await alpha.delay(seconds=30)"))
        for _ in range(100):
            if events.exists() and "delay-start" in events.read_text():
                break
            await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await execute(client, "return await alpha.add(a=2,b=3)")).data == {"value": 5}
    assert "delay-cancelled" in events.read_text()


async def test_freeform_schema_delegates_arguments(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {"alpha": stdio()}}) as (client, _, _):
        result = await execute(
            client, 'return await alpha.freeform(extra=1, nested={"key":"value"})'
        )
        assert result.data == {"extra": 1, "nested": {"key": "value"}}


async def test_empty_batch_is_lazy_and_errors_do_not_dispatch_suggestions(tmp_path: Path) -> None:
    from mcp import types as mt

    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        result = await client.session.send_request(
            mt.CallToolRequest(
                params=mt.CallToolRequestParams(
                    name="execute", arguments={"code": "return await call_tools([])"}
                )
            ),
            mt.CallToolResult,
        )
        assert not result.is_error and result.content[0].text == "[]"
        assert not events.exists()
        failure = await execute(client, "return await alpha.ad(a=1,b=2)", raise_on_error=False)
        assert failure.is_error and "alpha_add" in str(failure.content)
        assert '"event": "add"' not in events.read_text()


async def test_batch_secret_error_and_transport_unknown(tmp_path: Path) -> None:
    secret = "batch-owned-error-secret"
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events, env={"ONETOOL_FIXTURE_SECRET": secret})}}
    ) as (client, _, stderr):
        result = await execute(
            client,
            'return await call_tools([("alpha_fail_secret",{}),'
            '("alpha_interrupt",{})], concurrency=1)',
        )
        assert not result.is_error, result
        outcomes = json.loads(result.content[0].text)
        assert [x["status"] for x in outcomes] == ["error", "unknown"]
        assert secret not in str(result.content)
    assert secret not in stderr.read_text()
    assert (
        sum(
            json.loads(line)["event"] == "append-interrupt"
            for line in events.read_text().splitlines()
        )
        == 1
    )


@pytest.mark.parametrize(
    "code",
    [
        "return await alpha.add(a=1,b=2)",
        'return await call_tool("alpha_add", {"a":1,"b":2})',
        'return await call_tools([("alpha_add",{"a":1,"b":2})])',
    ],
)
async def test_all_dispatch_paths_check_catalog_collisions(tmp_path: Path, code: str) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events), "alpha_beta": stdio()}}
    ) as (client, _, _):
        result = await execute(client, code, raise_on_error=False)
        assert "collision" in str(result.content).lower()
        assert '"event": "add"' not in events.read_text()


async def test_formatted_expansion_uses_native_result_file(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}, "execution": {"max_output_bytes": 1024}}) as (
        client,
        _,
        _,
    ):
        result = await execute(
            client, 'set_format("json-indent")\nreturn {"items":[{"value":x} for x in range(20)]}'
        )
        assert "path" in result.data, result
        saved = json.loads(Path(result.data["path"]).read_text())
        assert saved["structured_content"] == {"items": [{"value": x} for x in range(20)]}


async def test_final_unsupported_values_render_without_tags(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}}) as (client, _, _):
        result = await execute(
            client,
            'set_format("yaml-block")\nreturn {"set":{1,2},"nan":float("nan"),"inf":float("inf")}',
        )
        assert not result.is_error
        assert result.data["nan"] == "nan" and result.data["inf"] == "inf"
        assert yaml.safe_load(result.content[0].text) == result.data
        assert "!!python" not in result.content[0].text


async def test_dot_cpu_deadline_stops_and_recovers(tmp_path: Path) -> None:
    async with connected(
        tmp_path, {"servers": {"alpha": stdio()}, "execution": {"timeout_seconds": 0.4}}
    ) as (client, _, _):
        await client.call_tool("search", {"query": "add"})
        failed = await execute(
            client, "await alpha.add(a=1,b=2)\nwhile True: pass", raise_on_error=False
        )
        assert failed.is_error
        assert (await execute(client, "return 42")).content[0].text == "42"


async def test_cancellation_joins_pending_catalog_callback(tmp_path: Path) -> None:
    events = tmp_path / "pending-catalog.jsonl"
    alpha = stdio(events)
    alpha["args"] += ["--catalog-delay", "0.4"]
    async with connected(tmp_path, {"servers": {"alpha": alpha}}) as (client, _, _):
        task = asyncio.create_task(
            execute(client, 'return await call_tool("alpha_append_once", {})')
        )
        for _ in range(100):
            if events.exists() and "list-tools" in events.read_text():
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("fixture catalog did not start")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.5)
        assert (await execute(client, "return 42")).content[0].text == "42"
        assert '"event": "append"' not in events.read_text()


async def test_batch_bound_across_servers(tmp_path: Path) -> None:
    paths = {name: tmp_path / f"{name}.jsonl" for name in ("alpha", "beta")}
    async with connected(
        tmp_path, {"servers": {name: stdio(path) for name, path in paths.items()}}
    ) as (client, _, _):
        result = await execute(
            client,
            'return await call_tools([(server+"_delay",{"seconds":0.03}) '
            'for server in ["alpha","beta"]*8], concurrency=4)',
        )
        assert not result.is_error
    records = sorted(
        (json.loads(line) for path in paths.values() for line in path.read_text().splitlines()),
        key=lambda row: row["time"],
    )
    running = peak = 0
    for row in records:
        running += (
            1 if row["event"] == "delay-start" else -1 if row["event"] == "delay-complete" else 0
        )
        peak = max(peak, running)
    assert running == 0 and 0 < peak <= 4
