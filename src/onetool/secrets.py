"""Explicit secrets files and lazy age/keyring resolution. No plaintext fallback."""

from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from onetool.config import ConfigError, read_document

SERVICE = "onetool-mcp"
IDENTITY = "secrets-identity"
PREFIX = "age1enc:"
REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _age() -> Any:
    import pyrage  # type: ignore[import-untyped]  # Public extension has no stubs.

    return pyrage


class SecretUnavailable(ConfigError):
    """A safe authentication category, without ciphertext or plaintext details."""

    category = "authentication"


def secure_keyring(backend: Any) -> bool:
    secure = {
        "keyring.backends.macOS",
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
    }
    if type(backend).__module__ == "keyring.backends.chainer":
        return bool(backend.backends) and all(secure_keyring(child) for child in backend.backends)
    return type(backend).__module__ in secure and backend.priority > 0


def identity(*, optional: bool = False) -> Any:
    import keyring

    pyrage = _age()

    try:
        if not secure_keyring(keyring.get_keyring()):
            raise SecretUnavailable("A supported secure system keyring is required")
        value = keyring.get_password(SERVICE, IDENTITY)
        if value is None and optional:
            return None
        if not value:
            raise SecretUnavailable("Secret identity missing; run onetool secrets init")
        return pyrage.x25519.Identity.from_str(value)
    except SecretUnavailable:
        raise
    except Exception:
        raise SecretUnavailable("Secret identity storage unavailable") from None


def read_secrets(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = read_document(path)
    if any(
        not isinstance(k, str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
        or not isinstance(v, str)
        for k, v in data.items()
    ):
        raise ConfigError("Secrets must be a flat mapping of variable names to strings")
    return data


def decrypt(value: str, key: Any) -> str:
    pyrage = _age()

    try:
        plaintext = pyrage.decrypt(base64.b64decode(value[len(PREFIX) :], validate=True), [key])
        if not isinstance(plaintext, bytes):
            raise SecretUnavailable("Invalid decrypted value")
        return plaintext.decode("utf-8")
    except Exception:
        raise SecretUnavailable("Encrypted secret is malformed or cannot be decrypted") from None


def encrypt(value: str, key: Any) -> str:
    pyrage = _age()

    encrypted = (
        PREFIX + base64.b64encode(pyrage.encrypt(value.encode(), [key.to_public()])).decode()
    )
    if decrypt(encrypted, key) != value:
        raise SecretUnavailable("Secret encryption verification failed")
    return encrypted


class Variables:
    def __init__(self, path: Path | None, shared: dict[str, str]):
        self.path = path
        self.values = read_secrets(path)
        self.shared = shared
        self.names: set[str] = set()
        self.masks: set[str] = {v for v in self.values.values() if v}
        self.protected: set[str] = {
            v for v in self.values.values() if v and not v.startswith(PREFIX)
        }
        self.decrypted: dict[str, str] = {}

    def present(self, name: str) -> bool:
        return name in self.values or name in self.shared or name in os.environ

    def text(self, value: str, *, runtime: bool = False, stack: tuple[str, ...] = ()) -> str:
        def replace(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            self.names.add(name)
            if name in stack or len(stack) >= 32:
                raise ConfigError(f"Variable reference cycle: {name}")
            if name in self.values:
                result = self.values[name]
                if result.startswith(PREFIX):
                    if not runtime:
                        return match.group(0)
                    if name not in self.decrypted:
                        self.decrypted[name] = decrypt(result, identity())
                    result = self.decrypted[name]
                if result:
                    self.protected.add(result)
            elif name in self.shared:
                result = self.text(self.shared[name], runtime=runtime, stack=(*stack, name))
            elif name in os.environ:
                result = os.environ[name]
            elif default is not None:
                result = default
            else:
                raise ConfigError(f"environment variable is not set: {name}")
            if result:
                self.masks.add(result)
            return result

        return REFERENCE.sub(replace, value)


class SecretManager:
    def __init__(self, path: Path):
        self.path = path.absolute()

    def _values(self) -> dict[str, str]:
        return read_secrets(self.path) if self.path.exists() else {}

    def _write(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".onetool-secrets-", dir=self.path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                yaml.safe_dump(values, stream, allow_unicode=True, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def run(self, action: str, name: str | None = None, value: str | None = None) -> dict[str, Any]:
        import keyring

        pyrage = _age()

        values = self._values()
        if action == "init":
            current = identity(optional=True)
            if current is None:
                current = pyrage.x25519.Identity.generate()
                try:
                    keyring.set_password(SERVICE, IDENTITY, str(current))
                except Exception:
                    raise SecretUnavailable("Secret identity storage unavailable") from None
            return {"identity": "present", "recipient": str(current.to_public())}
        current = identity(optional=True)
        if action in {"status", "audit"}:
            return {
                "identity_present": current is not None,
                "keys": {
                    k: ("encrypted" if v.startswith(PREFIX) else "plain") for k, v in values.items()
                },
                "owner_only": not self.path.exists() or not (self.path.stat().st_mode & 0o077),
            }
        if action == "set":
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                or value is None
            ):
                raise ConfigError("set needs a variable name and a prompted value")
            values[name] = encrypt(value, current) if current is not None else value
            self._write(values)
            return {"name": name, "storage": "encrypted" if current is not None else "plain"}
        if current is None:
            raise SecretUnavailable("Secret identity missing; run onetool secrets init")
        if action not in {"encrypt", "rotate"}:
            raise ConfigError("Unknown secrets command")
        plain = {k: decrypt(v, current) if v.startswith(PREFIX) else v for k, v in values.items()}
        replacement = pyrage.x25519.Identity.generate() if action == "rotate" else current
        prepared = {k: encrypt(v, replacement) for k, v in plain.items()}
        self._write(prepared)
        try:
            written = read_secrets(self.path)
            if any(decrypt(written[k], replacement) != v for k, v in plain.items()):
                raise SecretUnavailable("Encrypted file verification failed")
            if action == "rotate":
                keyring.set_password(SERVICE, IDENTITY, str(replacement))
        except Exception:
            self._write(values)
            if action == "rotate":
                try:
                    keyring.set_password(SERVICE, IDENTITY, str(current))
                except Exception:
                    pass
            raise SecretUnavailable("Secret operation failed; original file restored") from None
        return {"keys": list(prepared), "storage": "encrypted", "rotated": action == "rotate"}
