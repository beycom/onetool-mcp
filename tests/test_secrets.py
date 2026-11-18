"""Owned secret-file resolution/CLI transactions, never a live keychain prompt."""

import asyncio
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import keyring
import pytest
import yaml
from fixtures.keyring_backend import MemoryKeyring
from test_gateway import execute, stdio

from onetool.secrets import IDENTITY, SERVICE, SecretManager, SecretUnavailable, decrypt, encrypt


@pytest.fixture(autouse=True)
def forbid_platform_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed if a unit test escapes the explicit in-memory read/write patches."""
    import keyring.core

    def forbidden():
        raise AssertionError("Secrets tests must not resolve a platform keyring")

    monkeypatch.setattr(keyring, "get_keyring", forbidden)
    monkeypatch.setattr(keyring.core, "get_keyring", forbidden)
    # Subprocesses fail closed too; real-client cases explicitly select the memory fixture.
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.fail.Keyring")


def test_secret_commands_roundtrip_and_rotation_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pyrage

    backend = MemoryKeyring()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.setattr(
        keyring, "get_password", lambda service, user: backend.get_password(service, user)
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, user, value: backend.set_password(service, user, value),
    )
    manager = SecretManager(tmp_path / "secrets.yaml")
    manager.run("init")
    manager.path.write_text("PLAIN: owned-encrypt-command-sentinel\n")
    manager.run("encrypt")
    assert yaml.safe_load(manager.path.read_text())["PLAIN"].startswith("age1enc:")
    secret = "owned-file-crypto-sentinel"
    manager.run("set", "TOKEN", secret)
    original = manager.path.read_bytes()
    old_identity = backend.get_password(SERVICE, IDENTITY)
    assert secret not in original.decode() and not manager.path.stat().st_mode & 0o077
    assert (
        decrypt(yaml.safe_load(original)["TOKEN"], pyrage.x25519.Identity.from_str(old_identity))
        == secret
    )
    original_set = backend.set_password
    failed = False

    def fail_once(service, user, value):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("injected keyring failure")
        original_set(service, user, value)

    monkeypatch.setattr(backend, "set_password", fail_once)
    with pytest.raises(SecretUnavailable):
        manager.run("rotate")
    assert (
        manager.path.read_bytes() == original
        and backend.get_password(SERVICE, IDENTITY) == old_identity
    )
    monkeypatch.setattr(backend, "set_password", original_set)
    manager.run("rotate")
    new_identity = backend.get_password(SERVICE, IDENTITY)
    assert new_identity != old_identity
    assert (
        decrypt(
            yaml.safe_load(manager.path.read_text())["TOKEN"],
            pyrage.x25519.Identity.from_str(new_identity),
        )
        == secret
    )
    assert manager.run("status")["keys"] == {"PLAIN": "encrypted", "TOKEN": "encrypted"}
    assert secret not in str(manager.run("audit"))
    assert not list(tmp_path.glob("*.bak*"))


async def test_secrets_precedence_lazy_decryption_and_no_exposure(tmp_path: Path) -> None:
    import pyrage

    identity = pyrage.x25519.Identity.generate()
    plain = "owned-plain-file-secret-${MUST_REMAIN_LITERAL}"
    # Referenced values remain literal across validation and runtime connection resolution.
    hidden = "owned-encrypted-file-secret"
    path = tmp_path / "secrets.yaml"
    path.write_text(
        yaml.safe_dump({"PLAIN": plain, "ENC": encrypt(hidden, identity), "WIN": "file-wins"})
    )
    path.chmod(0o600)
    marker = tmp_path / "keyring-access"
    log = tmp_path / "gateway.log"
    values = {
        "PLAIN_VALUE": "${PLAIN}",
        "ENCRYPTED_VALUE": "${ENC}",
        "WIN_VALUE": "${WIN}",
        "TOP_VALUE": "${TOP}",
        "DEFAULT_VALUE": "${ABSENT:-fallback}",
    }
    data = {
        "env": {"TOP": "shared-value", "WIN": "top-wins"},
        "servers": {"alpha": stdio(env=values)},
        "logging": {"file": str(log)},
    }
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"version": 4, **data}))
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parent / "fixtures"),
        "PYTHON_KEYRING_BACKEND": "keyring_backend.MemoryKeyring",
        "ONETOOL_TEST_IDENTITY": str(identity),
        "ONETOOL_TEST_KEYRING_MARKER": str(marker),
        "WIN": "process-loses",
    }
    checked = await asyncio.to_thread(
        subprocess.run,
        [
            sys.executable,
            "-m",
            "onetool",
            "check-config",
            "--config",
            str(config),
            "--secrets",
            str(path),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0 and not marker.exists(), checked.stderr
    # A direct transport uses the same real CLI as connected(), with the new explicit flag.
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(
        sys.executable,
        ["-m", "onetool", "serve", "--config", str(config), "--secrets", str(path)],
        env=env,
        log_file=tmp_path / "stderr.log",
    )
    try:
        async with Client(transport) as client:
            from mcp import types as mt

            status = await client.session.send_request(
                mt.CallToolRequest(
                    params=mt.CallToolRequestParams(name="onetool_status", arguments={})
                ),
                mt.CallToolResult,
            )
            assert not marker.exists()
            expected = {
                "PLAIN_VALUE": plain,
                "ENCRYPTED_VALUE": hidden,
                "WIN_VALUE": "file-wins",
                "TOP_VALUE": "shared-value",
                "DEFAULT_VALUE": "fallback",
            }
            result = await execute(
                client, f"return await alpha.env_digests(keys={list(expected)!r})"
            )
            assert result.data == {
                key: hashlib.sha256(value.encode()).hexdigest() for key, value in expected.items()
            }
            assert marker.exists()
            exposed = await execute(
                client, f'print({plain!r})\nset_format("yaml-block")\nreturn {{"value":{hidden!r}}}'
            )
            saved = await execute(client, f'return await results.write({{"secret":{hidden!r}}})')
            read = await client.call_tool(
                "onetool_results", {"action": "read", "handle": saved.data["handle"]}
            )
            for sentinel in [plain, hidden]:
                assert sentinel not in str(status) + str(exposed) + str(read)
                assert sentinel not in Path(saved.data["path"]).read_text()
    finally:
        await transport.close()
    for destination in [tmp_path / "stderr.log", log]:
        assert plain not in destination.read_text() and hidden not in destination.read_text()


@pytest.mark.parametrize("problem", ["missing-identity", "insecure", "malformed", "unresolved"])
async def test_secret_failure_is_per_server(tmp_path: Path, problem: str) -> None:
    import pyrage
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    key = pyrage.x25519.Identity.generate()
    values = {"ENC": encrypt("never-expose-this-secret", key)}
    if problem == "malformed":
        values["ENC"] = "age1enc:not-valid-ciphertext"
    path = tmp_path / "secrets.yaml"
    path.write_text(yaml.safe_dump(values))
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "version": 4,
                "servers": {
                    "alpha": stdio(),
                    "bad": stdio(
                        env={"TOKEN": "${MISSING}" if problem == "unresolved" else "${ENC}"}
                    ),
                },
            }
        )
    )
    env = {
        "PYTHONPATH": str(Path(__file__).parent / "fixtures"),
        "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"
        if problem == "insecure"
        else "keyring_backend.MemoryKeyring",
    }
    if problem not in {"missing-identity", "insecure"}:
        env["ONETOOL_TEST_IDENTITY"] = str(key)
    transport = StdioTransport(
        sys.executable,
        ["-m", "onetool", "serve", "--config", str(config), "--secrets", str(path)],
        env=env,
        log_file=tmp_path / "stderr.log",
    )
    try:
        async with Client(transport) as client:
            assert (await execute(client, "return await alpha.add(a=1,b=2)")).data == {"value": 3}
            status = (await client.call_tool("onetool_status", {})).data
            assert status["servers"]["bad"]["state"] == "error"
            expected = "config" if problem == "unresolved" else "authentication"
            assert status["servers"]["bad"]["failure"]["category"] == expected
            assert "never-expose-this-secret" not in str(status)
    finally:
        await transport.close()


def test_secret_cli_does_not_accept_or_echo_value_arguments(tmp_path: Path) -> None:
    value = "unaccepted-secret-cli-value"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "onetool",
            "secrets",
            "set",
            "TOKEN",
            value,
            "--secrets",
            str(tmp_path / "secrets.yaml"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and value not in result.stdout + result.stderr


def test_platform_keyring_resolution_is_forbidden() -> None:
    import keyring.core

    for resolve in [keyring.get_keyring, keyring.core.get_keyring]:
        with pytest.raises(AssertionError, match="must not resolve"):
            resolve()


def test_missing_identity_cli_preserves_safe_init_hint(tmp_path: Path) -> None:
    path = tmp_path / "plain secrets.yaml"
    path.write_text("TOKEN: never-print-this-cli-secret\n")
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parent / "fixtures"),
        "PYTHON_KEYRING_BACKEND": "keyring_backend.MemoryKeyring",
        "ONETOOL_TEST_IDENTITY": "",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "onetool",
            "secrets",
            "encrypt",
            "--secrets",
            str(path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2 and "run onetool secrets init" in result.stderr
    assert "never-print-this-cli-secret" not in result.stdout + result.stderr
