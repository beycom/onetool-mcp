"""Local composition, source paths and transactional runtime reload via real MCP."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from test_gateway import connected, execute, stdio

from onetool.config import ConfigError, HttpServer, load_config


def write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data))
    return path


def test_includes_merge_and_winning_source_paths(tmp_path: Path) -> None:
    nested = write(
        tmp_path / "shared space/nested/base.yaml",
        {
            "env": {"A": "base", "B": "base"},
            "servers": {
                "alpha": stdio(env={"LEAK": "must-not-leak"}),
                "beta": {"transport": "stdio", "command": "./bin/python", "cwd": "./work"},
            },
            "logging": {"file": "logs/gateway.log"},
        },
    )
    first = write(
        tmp_path / "shared space/first.yaml",
        {"include": ["nested/base.yaml"], "env": {"B": "first"}},
    )
    second = write(
        tmp_path / "second.yaml",
        {"env": {"B": "second", "C": "second"}, "execution": {"max_tool_calls": 10}},
    )
    root = write(
        tmp_path / "root.yaml",
        {
            "version": 4,
            "include": ["shared space/first.yaml", "second.yaml"],
            "servers": {"alpha": {"transport": "http", "url": "http://127.0.0.1:8765/mcp"}},
            "env": {"C": "root"},
            "logging": {"level": "DEBUG"},
        },
    )
    loaded = load_config(root)
    assert loaded.model.env == {"A": "base", "B": "second", "C": "root"}
    assert isinstance(loaded.model.servers["alpha"], HttpServer)
    assert not hasattr(loaded.model.servers["alpha"], "env")
    beta = loaded.model.servers["beta"]
    assert beta.command == str(nested.parent / "bin/python") and beta.cwd == str(
        nested.parent / "work"
    )
    assert loaded.model.logging.file == str(nested.parent / "logs/gateway.log")
    assert loaded.model.logging.level == "DEBUG" and loaded.model.execution.max_tool_calls == 10
    assert loaded.sources == (nested, first, second, root)
    assert loaded.server_sources == {"alpha": root, "beta": nested}
    result = subprocess.run(
        [sys.executable, "-m", "onetool", "check-config", "--config", str(root)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and result.stdout == ""
    assert all(str(path) in result.stderr for path in loaded.sources)
    assert f"Server beta: {nested}" in result.stderr and not (nested.parent / "logs").exists()


@pytest.mark.parametrize(
    "problem",
    ["cycle", "duplicate", "version", "unsafe", "missing", "depth", "count", "combined", "schema"],
)
def test_include_failures_are_source_aware_and_safe(tmp_path: Path, problem: str) -> None:
    root = write(tmp_path / "root.yaml", {"version": 4, "include": ["child.yaml"], "servers": {}})
    child = tmp_path / "child.yaml"
    if problem == "cycle":
        write(child, {"include": ["root.yaml"]})
    elif problem == "duplicate":
        child.write_text("env: {}\nenv: {}\n")
    elif problem == "version":
        write(child, {"version": 3})
    elif problem == "unsafe":
        child.write_text("env: !!python/object:owned_secret {}\n")
    elif problem == "depth":
        for i in range(8):
            write(tmp_path / f"{i}.yaml", {"include": [f"{i + 1}.yaml"]})
        write(child, {"include": ["0.yaml"]})
    elif problem == "count":
        for i in range(32):
            write(tmp_path / f"{i}.yaml", {})
        write(root, {"version": 4, "include": [f"{i}.yaml" for i in range(32)], "servers": {}})
    elif problem == "combined":
        child.write_text("#" + "x" * 600000 + "\n")
        # A comment-only file is not a mapping, so make both bounded documents mappings.
        child.write_text(child.read_text() + "env: {}\n")
        other = tmp_path / "other.yaml"
        other.write_bytes(child.read_bytes())
        write(root, {"version": 4, "include": ["child.yaml", "other.yaml"], "servers": {}})
    elif problem == "schema":
        child.write_text(
            "servers:\n  beta:\n    transport: stdio\n    command: python\n"
            "    timeout_seconds: owned_secret\n"
        )
    with pytest.raises(ConfigError) as failure:
        load_config(root)
    message = str(failure.value)
    assert str(tmp_path) in message and "owned_secret" not in message
    if problem == "schema":
        assert f"{child}:5" in message and "timeout_seconds" in message


async def test_included_changes_validate_before_reload_or_restart(tmp_path: Path) -> None:
    child = write(tmp_path / "servers.yaml", {"servers": {"alpha": stdio(), "beta": stdio()}})
    async with connected(tmp_path, {"include": ["servers.yaml"]}) as (client, root, _):
        first = (await execute(client, "return await alpha.counter()")).data
        peer = (await execute(client, "return await beta.counter()")).data
        child.write_text("servers: {alpha: {transport: owned-invalid}}\n")
        failed = await client.call_tool("onetool_reload", {}, raise_on_error=False)
        assert failed.is_error and str(child) in str(failed.content)
        assert (await execute(client, "return await alpha.counter()")).data["pid"] == first["pid"]
        write(child, {"servers": {"alpha": stdio(env={"NEW": "value"}), "beta": stdio()}})
        await client.call_tool("onetool_servers", {"action": "restart", "name": "alpha"})
        assert (await execute(client, "return await alpha.counter()")).data["count"] == 1
        assert (await execute(client, "return await beta.counter()")).data["pid"] == peer["pid"]
        await client.call_tool("onetool_reload", {})
        status = (await client.call_tool("onetool_status", {})).data
        assert status["config"]["server_sources"]["alpha"] == str(child)
        assert status["config"]["sources"] == [str(child), str(root)]


@pytest.mark.parametrize("kind", ["deep", "null"])
def test_loader_resource_errors_remain_safe_config_errors(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "config.yaml"
    if kind == "deep":
        path.write_text(
            "version: 4\nservers: {}\nenv: {X: " + "[" * 1500 + "0" + "]" * 1500 + "}\n"
        )
    else:
        path.write_text('version: 4\nservers: {}\ninclude: ["\\0"]\n')
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert str(path) in str(error.value)
