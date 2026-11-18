"""V17–V24: owned lifecycle, result recovery, deadlines and auth boundaries."""

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

import pytest
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
        await client.call_tool("onetool_servers", {"action": "restart", "name": "alpha"})
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


async def test_client_cancellation_has_no_result_and_next_request_works(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(
        tmp_path, {"servers": {"alpha": stdio(events)}, "logging": {"level": "DEBUG"}}
    ) as (client, _, stderr):
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
        call.cancel()
        try:
            await call
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("client cancellation became a result")
        assert (await execute(client, "return 42")).content[0].text == "42"
    recorded = [json.loads(line)["event"] for line in events.read_text().splitlines()]
    assert recorded.count("delay-cancelled") == 1 and "delay-complete" not in recorded
    assert "execution_cancelled" in stderr.read_text()


async def test_status_retains_redacted_error_text(tmp_path: Path) -> None:
    secret = "owned-missing-command-secret"
    async with connected(
        tmp_path,
        {
            "servers": {
                "down": {
                    "transport": "stdio",
                    "command": f"/missing/{secret}",
                    "env": {"TOKEN": secret},
                }
            }
        },
    ) as (client, _, _):
        await client.call_tool("search", {"query": "add"})
        status = (await client.call_tool("onetool_status", {})).data
        error = status["servers"]["down"]["last_error"]
        assert "down:" in error and "No such file" in error
        assert secret not in error and "redacted" in error and len(error) <= 300


async def test_cancelled_admin_drain_reopens_execution(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events)}}) as (client, _, _):
        work = asyncio.create_task(
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
            raise AssertionError("fixture did not start")
        for tool, arguments in [
            ("onetool_reload", {}),
            ("onetool_servers", {"action": "restart", "name": "alpha"}),
        ]:
            admin = asyncio.create_task(client.call_tool(tool, arguments))
            await asyncio.sleep(0.1)
            admin.cancel()
            try:
                await admin
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("admin cancellation returned a result")
            assert (await execute(client, "return 42")).content[0].text == "42"
        work.cancel()
        await asyncio.gather(work, return_exceptions=True)


async def test_session_controls_and_disk_restart(tmp_path: Path) -> None:
    events = tmp_path / "alpha-events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events), "beta": stdio()}}) as (
        client,
        config,
        _,
    ):
        first = (await execute(client, "return await alpha.counter()")).data
        beta = (await execute(client, "return await beta.counter()")).data
        original = config.read_text()
        disabled = await client.call_tool("onetool_servers", {"action": "disable", "name": "alpha"})
        assert disabled.data["state"] == "disabled" and not disabled.data["session_enabled"]
        assert config.read_text() == original
        with pytest.raises(ProcessLookupError):
            os.kill(first["pid"], 0)
        assert "alpha_add" not in str((await client.call_tool("search", {"query": "add"})).content)
        assert (await execute(client, "return await beta.counter()")).data["pid"] == beta["pid"]
        await client.call_tool("onetool_servers", {"action": "disable", "name": "alpha"})
        enabled = await client.call_tool("onetool_servers", {"action": "enable", "name": "alpha"})
        assert enabled.data["state"] == "ready" and enabled.data["tool_count"] > 0
        assert (await execute(client, "return await alpha.counter()")).data["count"] == 1
        data = yaml.safe_load(original)
        data["servers"]["alpha"]["env"] = {"NEW_CONFIG": "non-sensitive"}
        data["servers"]["beta"]["timeout_seconds"] = 12
        data["execution"] = {"max_tool_calls": 100}
        config.write_text(yaml.safe_dump(data))
        changed = await client.call_tool("onetool_servers", {"action": "restart", "name": "alpha"})
        assert changed.data["pending_servers"] == ["beta"] and changed.data["restart_required"] == [
            "execution"
        ]
        assert (await execute(client, "return await beta.counter()")).data["pid"] == beta["pid"]
        assert (await execute(client, "return await alpha.counter()")).data["pid"] != first["pid"]
        config.write_text("version: 3\nservers: {}\n")
        failure = await client.call_tool(
            "onetool_servers", {"action": "restart", "name": "alpha"}, raise_on_error=False
        )
        assert failure.is_error
        await client.call_tool("onetool_servers", {"action": "disable", "name": "alpha"})
        config.write_text(original)
        await client.call_tool("onetool_reload", {})
        assert (
            await client.call_tool("onetool_servers", {"action": "status", "name": "alpha"})
        ).data["session_enabled"]
        unknown = await client.call_tool(
            "onetool_servers", {"action": "enable", "name": "missing"}, raise_on_error=False
        )
        assert unknown.is_error and "alpha" in str(unknown.content)


async def test_disable_drains_only_target_and_preserves_unknown_outcome(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events), "beta": stdio()}}) as (
        client,
        _,
        _,
    ):
        call = asyncio.create_task(
            execute(client, "return await alpha.append_wait(seconds=30)", raise_on_error=False)
        )
        for _ in range(100):
            if events.exists() and "append-wait" in events.read_text():
                break
            await asyncio.sleep(0.02)
        disable = asyncio.create_task(
            client.call_tool("onetool_servers", {"action": "disable", "name": "alpha"})
        )
        await asyncio.sleep(0.05)
        assert (await execute(client, "return await beta.add(a=1,b=2)")).data == {"value": 3}
        await asyncio.wait_for(disable, 7)
        result = await asyncio.wait_for(call, 2)
        assert result.is_error and "unknown" in str(result.content).lower()
    assert (
        sum(json.loads(line)["event"] == "append-wait" for line in events.read_text().splitlines())
        == 1
    )


async def test_concurrent_controls_leave_consistent_state_and_no_processes(tmp_path: Path) -> None:
    events = tmp_path / "controls-events.jsonl"
    async with connected(tmp_path, {"servers": {"alpha": stdio(events, enabled=False)}}) as (
        client,
        _,
        _,
    ):
        await asyncio.gather(
            *(
                client.call_tool("onetool_servers", {"action": action, "name": "alpha"})
                for action in ["enable", "disable", "enable"]
            )
        )
        await client.call_tool("onetool_servers", {"action": "disable", "name": "alpha"})
        status = (
            await client.call_tool("onetool_servers", {"action": "status", "name": "alpha"})
        ).data
        assert status["state"] == "disabled" and not status["session_enabled"]
        assert "alpha_" not in str((await client.call_tool("search", {"query": "add"})).content)
    for pid in {json.loads(line)["pid"] for line in events.read_text().splitlines()}:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
