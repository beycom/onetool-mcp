"""Gateway-owned contracts through a real MCP stdio client and owned fixtures."""

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp import types as mt

FIXTURE = Path(__file__).parent / "fixtures/fixture_server.py"


def stdio(events: Path | None = None, **overrides: Any) -> dict[str, Any]:
    args = [str(FIXTURE.resolve())]
    if events:
        args += ["--events", str(events)]
    return {"transport": "stdio", "command": sys.executable, "args": args, **overrides}


@asynccontextmanager
async def connected(
    directory: Path, data: dict[str, Any], env: dict[str, str] | None = None
) -> AsyncIterator[tuple[Client[Any], Path, Path]]:
    directory.mkdir(exist_ok=True)
    config = directory / "config with spaces.yaml"
    config.write_text(yaml.safe_dump({"version": 4, **data}))
    stderr = directory / "stderr.log"
    transport = StdioTransport(
        sys.executable,
        ["-m", "onetool", "serve", "--config", str(config)],
        env=env,
        log_file=stderr,
    )
    try:
        async with Client(transport, timeout=20) as client:
            yield client, config, stderr
    finally:
        await transport.close()


async def execute(client: Client[Any], code: str, **kwargs: Any) -> Any:
    return await client.call_tool("execute", {"code": code}, **kwargs)


async def test_status_is_lazy_and_secret_free(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path,
        {
            "servers": {
                "fixture": stdio(events, env={"TOKEN": "private-sentinel"}),
                "down": {"transport": "stdio", "command": "/does-not-exist-onetool-fixture"},
            }
        },
    ) as (client, _, stderr):
        result = await client.session.send_request(
            mt.CallToolRequest(
                params=mt.CallToolRequestParams(name="onetool_status", arguments={})
            ),
            mt.CallToolResult,
        )
        assert not events.exists()
        assert result.structured_content["servers"]["fixture"]["state"] == "lazy"
        assert result.structured_content["servers"]["down"]["state"] == "lazy"
        assert "private-sentinel" not in str(result)
        assert "TOKEN" not in result.structured_content["servers"]["fixture"]
    assert "private-sentinel" not in stderr.read_text()


async def test_native_contract_chain_projection_and_callbacks(tmp_path: Path) -> None:
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(), "beta": stdio()}, "logging": {"level": "DEBUG"}}
    ) as (client, _, stderr):
        tools = await client.list_tools()
        code_tools = [
            {"name": tool.name, "input_schema": tool.input_schema}
            for tool in tools
            if not tool.name.startswith("onetool_")
        ]
        assert code_tools == json.loads((FIXTURE.parent / "code_mode_tools.json").read_text())
        result = await execute(
            client,
            'a = await call_tool("alpha_add", {"a":2,"b":3})\n'
            'b = await call_tool("beta_add", {"a":4,"b":5})\n'
            'return await call_tool("alpha_add", {"a":a["value"],"b":b["value"]})',
        )
        assert result.data == {"value": 14}
        result = await execute(client, 'return await call_tool("alpha_echo", {"value":"007"})')
        assert result.content[0].text == "007"
        result = await execute(
            client,
            "values = []\n"
            "for x in [1,2,3]:\n"
            "    if x > 1:\n"
            "        values.append(x * 2)\n"
            'return {"values":values}',
        )
        assert result.data == {"values": [4, 6]}
        await execute(client, "saved = 123\nreturn saved")
        failure = await execute(client, "return saved", raise_on_error=False)
        assert failure.is_error and "saved" in str(failure.content)
        failure = await execute(
            client, 'return await call_tool("alpha_fail", {})', raise_on_error=False
        )
        assert failure.is_error and "fixture deliberate error" in str(failure.content)
        counters = [
            (await execute(client, 'return await call_tool("alpha_counter", {})')).data
            for _ in range(3)
        ]
        assert [value["count"] for value in counters] == [1, 2, 3]
        assert len({value["pid"] for value in counters}) == 1
        seen: dict[str, list[str | None]] = {"first": [], "second": []}

        async def invoke(token: str) -> None:
            async def progress(progress: float, total: float | None, message: str | None) -> None:
                seen[token].append(message)

            result = await execute(
                client,
                f'return await call_tool("alpha_progress", {{"token":"{token}"}})',
                progress_handler=progress,
            )
            assert result.data == {"token": token}

        await asyncio.gather(invoke("first"), invoke("second"))
        assert seen == {"first": ["first", "first"], "second": ["second", "second"]}
        assert (await client.read_resource("fixture://alpha/value"))[0].text == "fixture resource"
        assert (await client.get_prompt("alpha_greeting", {"name": "Ada"})).messages[
            0
        ].content.text == "Hello Ada"
    records = [json.loads(line) for line in stderr.read_text().splitlines()]
    assert all(len(json.dumps(record).encode()) <= 8192 for record in records)
    assert not any(
        '"a":2' in line or "saved = 123" in line for line in stderr.read_text().splitlines()
    )
    calls = [
        record
        for record in records
        if record["event"] == "tool_completed" and record["tool"] == "progress"
    ]
    assert len(calls) == 2 and len({record["request_id"] for record in calls}) == 2


async def test_availability(tmp_path: Path) -> None:
    async with connected(
        tmp_path,
        {
            "servers": {
                "alpha": stdio(),
                "down": {"transport": "stdio", "command": "/does-not-exist-onetool-fixture"},
            }
        },
    ) as (client, _, _):
        result = await execute(client, 'return await call_tool("alpha_add", {"a":2,"b":3})')
        assert result.data == {"value": 5}
        failure = await execute(
            client, 'return await call_tool("down_add", {})', raise_on_error=False
        )
        assert failure.is_error and "down" in str(failure.content)
        status = (await client.call_tool("onetool_status", {})).data
        assert status["servers"]["down"]["state"] == "error"
        assert status["servers"]["alpha"]["state"] == "ready"


async def test_loopback_http_upstream(tmp_path: Path) -> None:
    import socket
    import subprocess

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(FIXTURE),
        "--transport",
        "http",
        "--port",
        str(port),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 0.1)
                writer.close()
                await writer.wait_closed()
                break
            except (OSError, TimeoutError):
                assert process.returncode is None
                await asyncio.sleep(0.05)
        else:
            raise AssertionError("HTTP fixture did not start")
        servers = {
            "remote": {
                "transport": "http",
                "url": f"http://127.0.0.1:{port}/mcp",
                "headers": {"X-Fixture-Token": "${HTTP_TOKEN}"},
            }
        }
        async with connected(
            tmp_path, {"servers": servers}, env={"HTTP_TOKEN": "owned-header-secret"}
        ) as (client, _, stderr):
            assert (
                await execute(client, 'return await call_tool("remote_add", {"a":4,"b":5})')
            ).data == {"value": 9}
            assert (await execute(client, 'return await call_tool("remote_header", {})')).data == {
                "result": "owned-header-secret"
            }
        assert "owned-header-secret" not in stderr.read_text()
    finally:
        process.terminate()
        await asyncio.wait_for(process.wait(), 5)
