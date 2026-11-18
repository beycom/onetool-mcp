"""Iter-1 result recovery and curated discovery through real MCP fixtures."""

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError
from mcp import types as mt
from test_gateway import connected, execute, stdio

from onetool.results import ResultFiles


async def test_result_handles_recover_once_and_share_python_store(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events)}, "execution": {"max_output_bytes": 2048}}
    ) as (client, _, _):
        result = await execute(
            client,
            "value = await alpha.append_once()\n"
            'return await results.write(value, source="fixture")',
        )
        handle = result.data["handle"]
        for action, options in [
            ("read", {}),
            ("grep", {"pattern": "appended"}),
            ("slice", {"select": "1:3"}),
            ("toc", {}),
            ("query", {"expression": "appended"}),
        ]:
            recovered = await client.call_tool(
                "onetool_results", {"action": action, "handle": handle, **options}
            )
            assert not recovered.is_error, recovered
        assert recovered.data["value"] is True
        again = await execute(client, f'return await results.query("{handle}", "appended")')
        assert again.data["value"] is True
        error = await execute(
            client, "return await alpha.append_result(size=3000,error=True)", raise_on_error=False
        )
        assert error.is_error and error.structured_content["handle"]
        inspected = (
            await client.call_tool(
                "onetool_results",
                {"action": "inspect", "handle": error.structured_content["handle"]},
            )
        ).data
        assert inspected["is_error"]
        await client.call_tool("onetool_results", {"action": "delete", "handle": handle})
        deleted = await client.call_tool(
            "onetool_results", {"action": "read", "handle": handle}, raise_on_error=False
        )
        assert deleted.is_error and "deleted handle" in str(deleted.content)
        crafted = await client.call_tool(
            "onetool_results",
            {"action": "read", "handle": "../../private-file"},
            raise_on_error=False,
        )
        assert crafted.is_error and "unknown handle" in str(crafted.content)
    assert (
        sum(json.loads(line)["event"] == "append" for line in events.read_text().splitlines()) == 2
    )


async def test_result_paging_sections_and_typed_queries(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}, "execution": {"max_output_bytes": 2048}}) as (
        client,
        _,
        _,
    ):
        value = "# First\nαβ\n## Child\nneedle\n# Second\n" + "😀" * 700
        handle = (
            await client.call_tool("onetool_results", {"action": "write", "value": value})
        ).data["handle"]
        toc = (await client.call_tool("onetool_results", {"action": "toc", "handle": handle})).data[
            "sections"
        ]
        assert [x["title"] for x in toc] == ["First", "Child", "Second"]
        page = (
            await client.call_tool(
                "onetool_results", {"action": "read", "handle": handle, "offset": 1, "limit": 1}
            )
        ).data
        assert page["text"] == "αβ"
        tail = (
            await client.call_tool(
                "onetool_results", {"action": "read", "handle": handle, "tail": True, "limit": 1}
            )
        ).data
        assert "[+200 chars]" in tail.get("text", tail.get("preview", "")) or tail.get("truncated")
        section = (
            await client.call_tool(
                "onetool_results", {"action": "slice", "handle": handle, "select": "#2"}
            )
        ).data
        assert "needle" in section["text"] and "# Second" not in section["text"]
        grep = (
            await client.call_tool(
                "onetool_results",
                {"action": "grep", "handle": handle, "pattern": "NEEDLE", "context": 1},
            )
        ).data
        assert grep["matches"] == [4]
        for value in [{"items": [1, 2]}, "items: [1, 2]\n"]:
            stored = (
                await client.call_tool("onetool_results", {"action": "write", "value": value})
            ).data
            queried = (
                await client.call_tool(
                    "onetool_results",
                    {"action": "query", "handle": stored["handle"], "expression": "items[1]"},
                )
            ).data
            assert queried["value"] == 2
        failed = await client.call_tool(
            "onetool_results",
            {"action": "query", "handle": handle, "expression": "["},
            raise_on_error=False,
        )
        assert failed.is_error
        appended = await execute(client, f'return await results.append("{handle}", "last line")')
        assert appended.data["handle"] == handle
        last = (
            await client.call_tool(
                "onetool_results", {"action": "read", "handle": handle, "tail": True, "limit": 1}
            )
        ).data
        assert last["text"] == "last line"


async def test_bounded_handle_index_and_tombstones(tmp_path: Path) -> None:
    import logging

    store = ResultFiles(logging.getLogger("store-test"), 2048)
    store.handle_limit = 2
    store.tombstone_limit = 1
    try:
        first = await store.action("write", value={"first": 1})
        await store.action("write", value={"second": 2})
        await store.action("write", value={"third": 3})
        with pytest.raises(ToolError, match="evicted handle"):
            await store.action("read", first["handle"])
        await store.action("write", value={"fourth": 4})
        with pytest.raises(ToolError, match="unknown handle"):
            await store.action("read", first["handle"])
        assert len(store.entries) == 2 and len(store.tombstones) == 1
        assert len(list(store.directory.iterdir())) == 2
    finally:
        store.close()


async def test_regex_timeout_is_safe_and_loop_stays_responsive(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}}) as (client, _, _):
        handle = (
            await client.call_tool(
                "onetool_results", {"action": "write", "value": "a" * 10000 + "!"}
            )
        ).data["handle"]
        work = asyncio.create_task(
            client.call_tool(
                "onetool_results",
                {"action": "grep", "handle": handle, "pattern": "(a+)+$", "timeout_seconds": 0.01},
                raise_on_error=False,
            )
        )
        status = await client.call_tool("onetool_status", {})
        assert not status.is_error
        timeout = await work
        assert timeout.is_error and "timed out" in str(timeout.content)
        assert "(a+)+$" not in str(timeout.content) and "a" * 100 not in str(timeout.content)
        oversized = await client.call_tool(
            "onetool_results",
            {"action": "grep", "handle": handle, "pattern": "a" * 1025},
            raise_on_error=False,
        )
        assert oversized.is_error


async def test_curated_instructions_schemas_filters_and_native_metadata(tmp_path: Path) -> None:
    data = {
        "instructions": "Owner gateway guidance",
        "servers": {
            "alpha": {
                **stdio(),
                "description": "Arithmetic",
                "instructions": "Owner alpha guidance",
                "tools": {
                    "add": {
                        "description": "Curated addition",
                        "tags": ["approved"],
                        "arguments": {"b": {"hide": True, "default": 7}, "a": {"examples": [2]}},
                    },
                    "counter": {"enabled": False},
                    "missing": {"description": "Unused"},
                },
                "include_tags": ["approved"],
            },
            "beta": stdio(),
        },
    }
    async with connected(tmp_path, data) as (client, _, _):
        assert "Owner gateway guidance" in client.instructions and "## alpha" in client.instructions
        assert "## beta" not in client.instructions
        schema = await client.call_tool("get_schema", {"tools": ["alpha_add"]})
        assert "Curated addition" in str(schema.content)
        assert (await execute(client, "return await alpha.add(a=2)")).data == {"value": 9}
        override = await execute(client, "return await alpha.add(a=2,b=100)", raise_on_error=False)
        assert override.is_error
        disabled = await execute(client, "return await alpha.counter()", raise_on_error=False)
        assert disabled.is_error
        state = (await client.call_tool("onetool_status", {})).data["servers"]["alpha"]
        assert state["instructions"] == "Fixture native usage instructions"
        assert state["warnings"] == ["Unknown curation target: missing"]
        assert (await execute(client, 'return await beta.echo(value="007")')).content[
            0
        ].text == "007"


async def test_help_is_lazy_grouped_and_fresh(tmp_path: Path) -> None:
    disabled_events = tmp_path / "disabled.jsonl"
    lazy_events = tmp_path / "lazy.jsonl"
    async with connected(
        tmp_path,
        {
            "servers": {
                "alpha": stdio(lazy_events),
                "down": {"transport": "stdio", "command": "/missing/owned-command"},
                "disabled": stdio(disabled_events, enabled=False),
            }
        },
    ) as (client, _, _):
        first = await client.session.send_request(
            mt.CallToolRequest(params=mt.CallToolRequestParams(name="help", arguments={})),
            mt.CallToolResult,
        )
        assert not first.is_error and not lazy_events.exists() and not disabled_events.exists()
        await client.call_tool("search", {"query": "add"})
        overview = (await client.call_tool("help", {})).data
        assert overview["servers"]["down"]["state"] == "error"
        detail = (await client.call_tool("help", {"query": "alpha", "detail": "signatures"})).data
        assert any("alpha.add(" in x["signature"] for x in detail["tools"])
        grouped = (await client.call_tool("help", {"query": "arithmetci"})).data
        assert "servers" in grouped and "tools" in grouped
        await execute(client, "return await alpha.change_catalog(enabled=True)")
        fresh = (await client.call_tool("help", {"query": "alpha_dynamic", "detail": "full"})).data
        assert fresh["name"] == "alpha_dynamic"
        assert not disabled_events.exists()


async def test_non_json_large_output_keeps_one_receipt_file(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}, "execution": {"max_output_bytes": 1024}}) as (
        client,
        _,
        _,
    ):
        result = await execute(client, 'set_format("yaml-block")\nreturn {"value":"x"*3000}')
        path = Path(result.data["path"])
        assert len(list(path.parent.iterdir())) == 1


async def test_result_response_cap_empty_invalid_and_process_expiry(tmp_path: Path) -> None:
    cap = 1024
    async with connected(tmp_path, {"servers": {}, "execution": {"max_output_bytes": cap}}) as (
        client,
        _,
        _,
    ):
        saved = await client.call_tool("onetool_results", {"action": "write", "value": "界" * 500})
        handle = saved.data["handle"]
        for action in ["read", "inspect"]:
            page = await client.call_tool("onetool_results", {"action": action, "handle": handle})
            from fastmcp.tools import ToolResult

            from onetool.results import encoded

            assert len(encoded(ToolResult(content=page.data, structured_content=page.data))) <= cap
        empty = (await client.call_tool("onetool_results", {"action": "write", "value": ""})).data
        read = await client.call_tool(
            "onetool_results", {"action": "read", "handle": empty["handle"]}
        )
        assert read.data["text"] == ""
        no_match = await client.call_tool(
            "onetool_results",
            {
                "action": "grep",
                "handle": empty["handle"],
                "pattern": "absent",
            },
        )
        assert no_match.data["matches"] == []
        structured = (
            await client.call_tool("onetool_results", {"action": "write", "value": {"v": 1}})
        ).data
        invalid = await client.call_tool(
            "onetool_results",
            {
                "action": "query",
                "handle": structured["handle"],
                "expression": "[",
            },
            raise_on_error=False,
        )
        assert invalid.is_error and "Invalid query" in str(invalid.content)
        missing = await client.call_tool(
            "onetool_results",
            {
                "action": "slice",
                "handle": handle,
                "select": "missing heading",
            },
            raise_on_error=False,
        )
        assert missing.is_error and "not found" in str(missing.content)
    async with connected(tmp_path, {"servers": {}}) as (client, _, _):
        stale = await client.call_tool(
            "onetool_results",
            {
                "action": "read",
                "handle": handle,
            },
            raise_on_error=False,
        )
        assert stale.is_error and "unknown handle" in str(stale.content)


async def test_markdown_section_number_is_not_a_heading_substring(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {}}) as (client, _, _):
        stored = (
            await client.call_tool(
                "onetool_results",
                {
                    "action": "write",
                    "value": "# Reference #2\nfirst\n# Actual second\nsecond",
                },
            )
        ).data
        selected = (
            await client.call_tool(
                "onetool_results",
                {
                    "action": "slice",
                    "handle": stored["handle"],
                    "select": "#2",
                },
            )
        ).data
        assert selected["text"] == "# Actual second\nsecond"


async def test_help_and_namespaces_share_dot_callability(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events), "len": stdio()}}) as (
        client,
        _,
        _,
    ):
        await client.call_tool("search", {"query": "hidden"})
        for name in ["alpha__hidden", "len_add"]:
            help_result = (await client.call_tool("help", {"query": name, "detail": "full"})).data
            assert help_result["signature"].startswith("call_tool(")
        failed = await execute(
            client, 'return await alpha._hidden(value="not-dispatched")', raise_on_error=False
        )
        assert failed.is_error
        assert '"event": "underscore"' not in events.read_text()
        native = await execute(client, 'return await call_tool("alpha__hidden", {"value":"works"})')
        assert native.data == {"value": "works"}
        assert (
            sum(
                json.loads(line)["event"] == "underscore"
                for line in events.read_text().splitlines()
            )
            == 1
        )
        assert (await execute(client, 'return await call_tool("len_add", {"a":1,"b":2})')).data == {
            "value": 3
        }
