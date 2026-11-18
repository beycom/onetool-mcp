"""Disk retention boundaries owned entirely by OneTool."""

import json
import logging
from pathlib import Path

from fastmcp.tools import ToolResult

from onetool.results import ResultFiles, encoded


def test_exact_inline_boundary_and_directory_eviction(tmp_path: Path) -> None:
    result = ToolResult(content="small")
    files = ResultFiles(logging.getLogger("test.results"), len(encoded(result)))
    assert files.bound(result) is result
    assert files.directory is None
    files.cap = 1024
    files.directory_limit = 6000
    one = files.bound(ToolResult(content="a" * 3500))
    first = Path(one.structured_content["path"])
    two = files.bound(ToolResult(content="b" * 3500, is_error=True))
    second = Path(two.structured_content["path"])
    assert not first.exists() and second.exists()
    assert len(encoded(one)) <= files.cap and len(encoded(two)) <= files.cap
    assert two.is_error
    assert json.loads(second.read_text())["is_error"] is True
    files.close()
    assert not second.parent.exists()


def test_hard_limit_does_not_retain_or_invite_replay() -> None:
    files = ResultFiles(logging.getLogger("test.results"), 1024)
    result = files.bound(ToolResult(content="x" * (16 * 1024 * 1024)))
    assert result.is_error and files.directory is None
    assert "Do not replay" in result.content[0].text


def test_inline_fit_stops_rendering_before_full_fanout_and_keeps_error_flag() -> None:
    calls = 0

    class RenderProbe:
        def __str__(self):
            nonlocal calls
            calls += 1
            return "x" * 2000

    store = ResultFiles(logging.getLogger("test.results"), 1024)
    result = store.fit({"is_error": True, "value": [RenderProbe()] * 10000})
    assert result["truncated"] and result["is_error"]
    assert calls == 1  # Traversal stops at the budget; repeated references aren't all rendered.
    assert len(encoded(ToolResult(content=result, structured_content=result))) <= 1024


async def test_cancelled_query_keeps_worker_slot_until_real_completion(
    tmp_path: Path, monkeypatch
) -> None:
    import asyncio
    import threading
    import time

    import yaml
    from fastmcp import Client
    from test_gateway import execute, stdio

    from onetool.config import load_config
    from onetool.diagnostics import Redactor
    from onetool.gateway import Gateway

    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 4,
                "servers": {"alpha": stdio()},
                "execution": {"timeout_seconds": 0.15},
            }
        )
    )
    gateway = Gateway(load_config(path), logging.getLogger("test.results"), Redactor(()))
    saved = await gateway.results.action("write", value={"value": 2})
    original = gateway.results.query
    started = threading.Event()
    release = threading.Event()
    calls = []

    def delayed(handle, expression):
        calls.append(handle)
        started.set()
        assert release.wait(3)
        return original(handle, expression)

    monkeypatch.setattr(gateway.results, "query", delayed)
    try:
        async with Client(gateway.server) as client:
            begin = time.monotonic()
            first = await execute(
                client,
                f'return await results.query("{saved["handle"]}", "value")',
                raise_on_error=False,
            )
            assert started.is_set() and first.is_error
            assert time.monotonic() - begin < 0.8
            next_query = asyncio.create_task(
                client.call_tool(
                    "onetool_results",
                    {
                        "action": "query",
                        "handle": saved["handle"],
                        "expression": "value",
                    },
                )
            )
            await asyncio.sleep(0.03)
            assert len(calls) == 1 and not next_query.done()
            release.set()
            result = await asyncio.wait_for(next_query, 2)
            assert result.data["value"] == 2 and len(calls) == 2
    finally:
        release.set()
        gateway.results.close()
