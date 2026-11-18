"""V11–V13: boundary validation without starting any upstream machinery."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from onetool.config import ConfigError, HttpServer, StdioServer, load_config


def write(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "onetool.yaml"
    path.write_text(yaml.safe_dump(value))
    return path


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        "null",
        "version: 4\nversion: 4\nservers: {}",
        "version: 4\nservers: {}\n---\n{}",
        "version: 4\nservers: !!python/object/apply:os.system ['false']",
        "version: 4\nservers: &servers {}\nexecution: *servers",
        "version: 4\nservers: {a: {transport: stdio, command: python, env: {X: a, X: b}}}",
    ],
)
def test_unsafe_yaml_rejected(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(raw)
    with pytest.raises(ConfigError):
        load_config(path)


@pytest.mark.parametrize(
    "update",
    [
        {"version": 3},
        {"version": "4"},
        {"version": 4.0},
        {"version": True},
        {"includes": []},
        {"servers": []},
        {"execution": {"timeout_seconds": True}},
        {"execution": {"timeout_seconds": 0}},
        {"execution": {"timeout_seconds": 3601}},
        {"execution": {"timeout_seconds": float("inf")}},
        {"execution": {"timeout_seconds": float("nan")}},
        {"execution": {"max_output_bytes": True}},
        {"execution": {"max_output_bytes": 1023}},
        {"execution": {"max_output_bytes": 1048577}},
        {"logging": {"level": "TRACE"}},
        {"logging": {"unknown": "secret-value"}},
    ],
)
def test_strict_root(tmp_path: Path, update: dict) -> None:
    path = write(tmp_path, {"version": 4, "servers": {}, **update})
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "secret-value" not in str(error.value)


@pytest.mark.parametrize(
    "server",
    [
        {"transport": "sse", "url": "http://127.0.0.1/mcp"},
        {"transport": "stdio", "command": "python", "url": "http://127.0.0.1/mcp"},
        {"transport": "stdio", "command": " "},
        {"transport": "stdio", "command": "${COMMAND}"},
        {"transport": "stdio", "command": "python", "args": [2]},
        {"transport": "stdio", "command": "python", "env": {"X": 2}},
        {"transport": "stdio", "command": "python", "enabled": 1},
        {"transport": "stdio", "command": "python", "timeout_seconds": True},
        {"transport": "http", "url": "http://remote.invalid/mcp"},
        {"transport": "http", "url": "ftp://127.0.0.1/mcp"},
        {"transport": "http", "url": "https://user:secret-value@remote.invalid/mcp"},
        {"transport": "http", "url": "https://remote.invalid/mcp#fragment"},
        {"transport": "http", "url": "http://127.0.0.1:bad/mcp"},
        {"transport": "http", "url": "http://127.0.0.1/mcp", "auth": {"type": "bearer"}},
        {
            "transport": "http",
            "url": "http://127.0.0.1/mcp",
            "auth": {"type": "oauth"},
            "headers": {"aUtHoRiZaTiOn": "secret-value"},
        },
    ],
)
def test_strict_server(tmp_path: Path, server: dict) -> None:
    path = write(tmp_path, {"version": 4, "servers": {"fixture": server}})
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "secret-value" not in str(error.value)


@pytest.mark.parametrize("name", ["onetool", "UPPER", "has-dash", "1numeric", ""])
def test_names(tmp_path: Path, name: str) -> None:
    path = write(
        tmp_path, {"version": 4, "servers": {name: {"transport": "stdio", "command": "python"}}}
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_substitution_paths_and_no_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOKEN", "secret-value")
    monkeypatch.setenv("PORT", "8765")
    config = load_config(
        write(
            tmp_path,
            {
                "version": 4,
                "servers": {
                    "fixture": {
                        "transport": "stdio",
                        "command": "./bin/fixture",
                        "args": ["${TOKEN}", "$(touch NEVER)", "$HOME"],
                        "env": {"TOKEN": "${TOKEN}"},
                        "cwd": "./work",
                    },
                    "remote": {
                        "transport": "http",
                        "url": "http://127.0.0.1:${PORT}/mcp",
                        "headers": {"X-Token": "${TOKEN}"},
                    },
                },
                "logging": {"file": "gateway.log"},
            },
        )
    )
    server = config.model.servers["fixture"]
    assert isinstance(server, StdioServer)
    assert server.command == str(tmp_path / "bin/fixture")
    assert server.cwd == str(tmp_path / "work")
    assert server.args == ["secret-value", "$(touch NEVER)", "$HOME"]
    assert not (tmp_path / "NEVER").exists()
    assert server.env == {"TOKEN": "secret-value"}
    remote = config.model.servers["remote"]
    assert isinstance(remote, HttpServer)
    assert remote.url == "http://127.0.0.1:8765/mcp"
    assert config.env_names == {"TOKEN", "PORT"}
    assert config.redacted_env() == {"PORT": True, "TOKEN": True}
    assert config.model.logging.file == str(tmp_path / "gateway.log")
    assert not (tmp_path / "gateway.log").exists()


def test_missing_env_and_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONETOOL_MISSING_VAR", raising=False)
    path = write(
        tmp_path,
        {
            "version": 4,
            "servers": {
                "fixture": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["${ONETOOL_MISSING_VAR}"],
                }
            },
        },
    )
    with pytest.raises(ConfigError, match="ONETOOL_MISSING_VAR"):
        load_config(path)
    path.write_bytes(b" " * 1048577)
    with pytest.raises(ConfigError, match="1 MiB"):
        load_config(path)


def test_validation_never_imports_runtime(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        {
            "version": 4,
            "servers": {
                "remote": {
                    "transport": "http",
                    "url": "http://127.0.0.1:1/mcp",
                    "auth": {"type": "oauth"},
                }
            },
        },
    )
    code = (
        "from pathlib import Path; import sys; from onetool.config import load_config; "
        "load_config(Path(sys.argv[1])); assert not any(x in sys.modules for x in "
        "['fastmcp', 'keyring', 'onetool.gateway'])"
    )
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_literal_args_do_not_become_log_masks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONETOOL_ARG_TOKEN", "substituted-secret")
    config = load_config(
        write(
            tmp_path,
            {
                "version": 4,
                "servers": {
                    "fixture": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-y", "--stdio", "${ONETOOL_ARG_TOKEN}"],
                        "env": {"TOKEN": "literal-env-secret"},
                    },
                    "remote": {
                        "transport": "http",
                        "url": "http://127.0.0.1/mcp",
                        "headers": {"X-Token": "literal-header-secret"},
                    },
                },
            },
        )
    )
    assert set(config.secret_values) == {
        "substituted-secret",
        "literal-env-secret",
        "literal-header-secret",
    }


def test_executable_symlink_is_preserved(tmp_path: Path) -> None:
    link = tmp_path / "venv-python"
    link.symlink_to(sys.executable)
    config = load_config(
        write(
            tmp_path,
            {
                "version": 4,
                "servers": {
                    "fixture": {
                        "transport": "stdio",
                        "command": "./venv-python",
                    }
                },
            },
        )
    )
    assert config.model.servers["fixture"].command == str(link)
