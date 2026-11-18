"""Installed-compatible EOF/SIGINT probe using a real MCP stdio client."""

import argparse
import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


async def run_case(python: str, fixture: Path, sigint: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="onetool signal proof ") as directory:
        root = Path(directory)
        events = root / "events.jsonl"
        config = root / "config with spaces.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "version": 4,
                    "servers": {
                        "alpha": {
                            "transport": "stdio",
                            "command": python,
                            "args": [str(fixture), "--events", str(events)],
                        }
                    },
                }
            )
        )
        stderr = root / "stderr.log"
        transport = StdioTransport(
            python,
            ["-m", "onetool", "serve", "--config", str(config)],
            cwd=str(root),
            log_file=stderr,
        )
        unrelated = await asyncio.create_subprocess_exec("/bin/sleep", "30")
        call = None
        try:
            async with Client(transport, timeout=15) as client:
                status = (await client.call_tool("onetool_status", {})).data
                gateway_pid = status["runtime"]["pid"]
                value = await client.call_tool(
                    "execute", {"code": 'return await call_tool("alpha_counter", {})'}
                )
                child_pid = value.data["pid"]
                receipt = await client.call_tool(
                    "execute", {"code": 'return await call_tool("alpha_large", {"size":70000})'}
                )
                result_path = Path(receipt.data["path"])
                assert result_path.exists()
                if sigint:
                    call = asyncio.create_task(
                        client.call_tool(
                            "execute",
                            {"code": 'return await call_tool("alpha_delay", {"seconds":30})'},
                            raise_on_error=False,
                        )
                    )
                    for _ in range(100):
                        if "delay-start" in events.read_text():
                            break
                        await asyncio.sleep(0.02)
                    else:
                        raise AssertionError("blocking call did not start")
                    start = time.monotonic()
                    os.kill(gateway_pid, signal.SIGINT)
                    await asyncio.sleep(0.1)
                else:
                    start = time.monotonic()
            await transport.close()
            elapsed = time.monotonic() - start
            if call:
                await asyncio.gather(call, return_exceptions=True)
            assert not alive(child_pid), f"child {child_pid} leaked"
            assert not alive(gateway_pid), f"gateway {gateway_pid} leaked"
            assert unrelated.returncode is None
            assert not result_path.exists() and not result_path.parent.exists()
            assert elapsed < 5, elapsed
            text = stderr.read_text()
            assert "gateway_stopped" in text, text
            if sigint:
                recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
                assert "delay-cancelled" in recorded and "delay-complete" not in recorded
            print("SIGINT" if sigint else "EOF", "PASS", "seconds", elapsed, "child", child_pid)
        finally:
            await transport.close()
            unrelated.terminate()
            await asyncio.wait_for(unrelated.wait(), 5)


async def main(python: str, fixture: Path) -> None:
    for sigint in [False, True]:
        await run_case(python, fixture.resolve(), sigint)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.python, args.fixture))
