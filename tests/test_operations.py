"""V17–V24: owned lifecycle, result recovery, deadlines and auth boundaries."""

import asyncio
import hashlib
import json
import time
from pathlib import Path

import yaml
from test_gateway import connected, execute, stdio


async def test_reload_restart_and_catalog_change(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {"alpha": stdio(), "beta": stdio()}}) as (
        client,
        config,
        _,
    ):
        a = (await execute(client, 'return await call_tool("alpha_counter", {})')).data
        b = (await execute(client, 'return await call_tool("beta_counter", {})')).data
        await client.call_tool("onetool_restart_server", {"name": "alpha"})
        a2 = (await execute(client, 'return await call_tool("alpha_counter", {})')).data
        b2 = (await execute(client, 'return await call_tool("beta_counter", {})')).data
        assert a2["count"] == 1 and a2["pid"] != a["pid"]
        assert b2["count"] == 2 and b2["pid"] == b["pid"]
        original = config.read_text()
        for candidate in [
            "version: 3\nservers: {}\n",
            original + "execution: {timeout_seconds: 1}\n",
        ]:
            config.write_text(candidate)
            failure = await client.call_tool("onetool_reload", {}, raise_on_error=False)
            assert failure.is_error
            assert (await execute(client, 'return await call_tool("beta_counter", {})')).data[
                "pid"
            ] == b["pid"]
        config.write_text(yaml.safe_dump({"version": 4, "servers": {"alpha": stdio()}}))
        reload = await client.call_tool("onetool_reload", {})
        assert reload.data["revision"] == 2 and "state" in reload.data["message"].lower()
        a3 = (await execute(client, 'return await call_tool("alpha_counter", {})')).data
        assert a3["count"] == 1 and a3["pid"] != a2["pid"]
        await execute(
            client,
            'return await call_tool("alpha_change_catalog", {"enabled":true})'.replace(
                "true", "True"
            ),
        )
        assert "alpha_dynamic" in str(
            (await client.call_tool("search", {"query": "dynamic"})).content
        )
        dynamic = await execute(client, 'return await call_tool("alpha_dynamic", {})')
        assert "dynamic" in str(dynamic.content)
        await execute(client, 'return await call_tool("alpha_change_catalog", {"enabled":False})')
        assert "alpha_dynamic" not in str(
            (await client.call_tool("search", {"query": "dynamic"})).content
        )
        failure = await execute(
            client, 'return await call_tool("alpha_dynamic", {})', raise_on_error=False
        )
        assert failure.is_error


async def test_namespaced_collision_is_explicit(tmp_path: Path) -> None:
    async with connected(tmp_path, {"servers": {"alpha": stdio(), "alpha_beta": stdio()}}) as (
        client,
        _,
        _,
    ):
        failure = await execute(
            client, 'return await call_tool("alpha_add", {"a":1,"b":2})', raise_on_error=False
        )
        assert failure.is_error
        text = str(failure.content)
        assert "collision" in text.lower() and "alpha/beta_add" in text and "alpha_beta/add" in text


async def test_large_result_and_error_are_retained_once(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    paths = []
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events)}, "execution": {"max_output_bytes": 1024}}
    ) as (client, _, _):
        for error in [False, True]:
            result = await execute(
                client,
                f'return await call_tool("alpha_append_result", {{"size":4000,"error":{error}}})',
                raise_on_error=False,
            )
            assert result.is_error == error
            receipt = result.structured_content
            assert receipt and "repeat" in receipt["message"]
            path = Path(receipt["path"])
            paths.append(path)
            raw = path.read_bytes()
            assert len(raw) == receipt["size"]
            assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
            assert path.stat().st_mode & 0o777 == 0o600
            assert path.parent.stat().st_mode & 0o777 == 0o700
            assert len(result.content[0].text.encode()) < 1024
            saved = json.loads(raw)
            assert saved["is_error"] == error
        recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
        assert recorded.count("append") == 2
    assert all(not path.exists() and not path.parent.exists() for path in paths)


async def test_execution_and_backend_deadlines_cancel_without_replay(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path,
        {
            "servers": {"alpha": stdio(events, timeout_seconds=1)},
            "execution": {"timeout_seconds": 0.6},
        },
    ) as (client, _, stderr):
        await client.list_tools()
        start = time.monotonic()
        failed = await execute(client, "while True:\n    pass", raise_on_error=False)
        assert failed.is_error and time.monotonic() - start < 2
        start = time.monotonic()
        failed = await execute(
            client, 'return await call_tool("alpha_delay", {"seconds":10})', raise_on_error=False
        )
        assert failed.is_error and time.monotonic() - start < 1.5
        assert "unknown" in str(failed.content).lower() and "replay" in str(failed.content).lower()
        assert (await execute(client, "return 42")).content[0].text == "42"
    recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
    assert recorded.count("delay-start") == 1 and "delay-cancelled" in recorded
    assert "delay-complete" not in recorded
    assert '"error_category": "timeout"' in stderr.read_text()


async def test_interrupted_side_effect_is_not_replayed(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        failed = await execute(
            client, 'return await call_tool("alpha_interrupt", {})', raise_on_error=False
        )
        assert failed.is_error and "unknown" in str(failed.content).lower()
        assert "replay" in str(failed.content).lower()
        recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
        assert recorded.count("append-interrupt") == 1
        # Only this explicit later operation may reconnect.
        value = (await execute(client, 'return await call_tool("alpha_counter", {})')).data
        assert value["count"] == 1
        recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
        assert recorded.count("append-interrupt") == 1


async def test_environment_and_secret_errors(tmp_path: Path) -> None:
    secret = "owned-test-secret-9238"
    source = stdio(env={"ONETOOL_FIXTURE_SECRET": secret})
    source["args"] += ["--stderr-text", "unconfigured-startup-stderr-must-not-appear"]
    async with connected(
        tmp_path,
        {
            "servers": {"restricted": source, "inherited": stdio(inherit_env=True)},
            "logging": {"level": "DEBUG"},
        },
        env={"ONETOOL_TEST_PARENT_SECRET": "parent-sentinel"},
    ) as (client, _, stderr):
        for name, expected in [("restricted", False), ("inherited", True)]:
            result = await execute(client, f'return await call_tool("{name}_environment", {{}})')
            assert result.data["sentinel"] == expected
        failure = await execute(
            client, 'return await call_tool("restricted_fail_secret", {})', raise_on_error=False
        )
        assert failure.is_error and secret not in str(failure)
        assert "redacted" in str(failure.content)
        await execute(
            client, 'return await call_tool("restricted_echo", {"value":"RESULT_PAYLOAD_SENTINEL"})'
        )
    text = stderr.read_text()
    assert all(
        token not in text
        for token in [
            secret,
            "parent-sentinel",
            "RESULT_PAYLOAD_SENTINEL",
            "unconfigured-startup-stderr-must-not-appear",
            "call_tool(",
        ]
    )


async def test_auth_storage_unavailable_does_not_break_healthy_server(tmp_path: Path) -> None:
    servers = {
        "alpha": stdio(),
        "auth": {
            "transport": "http",
            "url": "http://127.0.0.1:1/mcp",
            "auth": {"type": "oauth", "scopes": ["read"]},
        },
    }
    async with connected(
        tmp_path,
        {"servers": servers},
        env={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
    ) as (client, _, _):
        assert (
            await execute(client, 'return await call_tool("alpha_add", {"a":2,"b":3})')
        ).data == {"value": 5}
        status = (await client.call_tool("onetool_status", {})).data
        assert status["servers"]["auth"]["state"] == "error"
        error = status["servers"]["auth"]["last_error"]
        assert "storage unavailable" in error and "plaintext" in error


async def test_one_execution_deadline_covers_the_chain(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path,
        {
            "servers": {"alpha": stdio(events, timeout_seconds=2)},
            "execution": {"timeout_seconds": 1},
        },
    ) as (client, _, _):
        await client.list_tools()
        start = time.monotonic()
        result = await execute(
            client,
            'await call_tool("alpha_delay", {"seconds":0.6})\n'
            'return await call_tool("alpha_delay", {"seconds":0.6})',
            raise_on_error=False,
        )
        assert result.is_error and time.monotonic() - start < 1.6
        assert "unknown" in str(result.content).lower()
    recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
    assert recorded.count("delay-start") == 2
    assert recorded.count("delay-complete") == 1
    assert recorded.count("delay-cancelled") == 1


async def test_reload_drains_then_cancels_and_blocks_new_execution(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        call = asyncio.create_task(
            execute(
                client,
                'return await call_tool("alpha_delay", {"seconds":30})',
                raise_on_error=False,
            )
        )
        for _ in range(100):
            if events.exists() and "delay-start" in events.read_text():
                break
            await asyncio.sleep(0.02)
        else:
            raise AssertionError("fixture call did not start")
        reload = asyncio.create_task(client.call_tool("onetool_reload", {}))
        await asyncio.sleep(0.1)
        blocked = await execute(client, "return 42", raise_on_error=False)
        assert blocked.is_error and "not dispatched" in str(blocked.content)
        await asyncio.wait_for(reload, 7)
        interrupted = await asyncio.wait_for(call, 2)
        assert interrupted.is_error and "unknown" in str(interrupted.content).lower()
        assert (await execute(client, "return 42")).content[0].text == "42"
    recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
    assert recorded.count("delay-start") == 1 and recorded.count("delay-cancelled") == 1
