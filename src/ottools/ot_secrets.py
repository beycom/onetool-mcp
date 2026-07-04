"""Secrets management tool pack for OneTool.

Provides agent-callable functions to manage age-encrypted secrets in secrets.yaml.
Values prefixed with `age1enc:` are encrypted with an age X25519 identity stored
in the OS keychain.
"""

from __future__ import annotations

import base64
import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ot.config.keyring import (
    _NO_IDENTITY_MSG as _NO_IDENTITY_MSG,
)
from ot.config.keyring import (
    _SECURE_BACKENDS as _SECURE_BACKENDS,
)
from ot.config.keyring import (
    _assert_secure_keyring_backend as _assert_secure_keyring_backend,
)
from ot.config.keyring import (
    _InsecureKeyringError as _InsecureKeyringError,
)
from otpack import LogSpan

# Pack for dot notation: ot_secrets.init(), ot_secrets.encrypt(), etc.
pack = "ot_secrets"
pack_aliases = ("sec",)

__all__ = ["audit", "encrypt", "get", "init", "rotate", "set", "status"]

__ot_requires__ = {
    "lib": [
        ("pyrage", "pip install pyrage"),
        ("keyring", "pip install keyring"),
    ]
}

_SERVICE = "onetool"
_KEY_IDENTITY = "age_identity"
_KEY_PUBKEY = "age_pubkey"
_KEY_LABEL = "age_label"
_PREFIX = "age1enc:"

# _NO_IDENTITY_MSG, _SECURE_BACKENDS, _InsecureKeyringError, and
# _assert_secure_keyring_backend() now live in ot.config.keyring (hoisted so
# core's ot.config.secrets doesn't import a leaf pack's private symbols).
# Re-imported above as module-level aliases for backwards compatibility —
# existing call sites and tests in this module keep working unchanged.


def _resolve_secrets_file(file: str | None) -> Path:
    """Resolve the secrets-file path, defaulting to the configured location.

    Explicit ``file`` wins; else the loaded ``--secrets`` path; else
    ``<config dir>/secrets.yaml``.
    """
    if file is not None:
        return Path(file).expanduser()
    from ot.config.loader import get_loaded_secrets_path

    loaded = get_loaded_secrets_path()
    if loaded is not None:
        return Path(loaded).expanduser()
    from ot.paths import get_config_dir

    return get_config_dir() / "secrets.yaml"


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` atomically at mode 0600 (temp file + rename).

    A crash mid-write leaves the original file untouched — no truncation window.
    """
    fd, temp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=".tmp_", suffix=".yaml"
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(
                data, f, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
        Path(temp_path).chmod(0o600)
        Path(temp_path).replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(temp_path).unlink()
        raise
    # Re-assert 0600 after replace (covers platforms where mkstemp perms differ).
    path.chmod(0o600)


def _require_keyring() -> Any:
    try:
        import keyring

        return keyring
    except ImportError as e:
        raise ImportError("keyring is not installed. Run: pip install keyring") from e


def _require_pyrage() -> Any:
    try:
        import pyrage  # type: ignore[import-untyped]

        return pyrage
    except ImportError as e:
        raise ImportError("pyrage is not installed. Run: pip install pyrage") from e


def _pubkey_hint(pubkey: str) -> str:
    """Return a truncated public key hint for safe display."""
    if len(pubkey) <= 12:
        return pubkey
    return pubkey[:8] + "..." + pubkey[-3:]


def init(*, label: str = "", force: bool = False) -> dict[str, Any]:
    """Generate an age X25519 identity and store it in the OS keychain.

    Args:
        label: Optional label to identify this identity (e.g., "macbook-gavin").
        force: If True, overwrite existing identity.

    Returns:
        Dict with pubkey, label, and status.
    """
    with LogSpan(span="ot_secrets.init") as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        _assert_secure_keyring_backend(keyring)

        existing = keyring.get_password(_SERVICE, _KEY_IDENTITY)
        if existing and not force:
            s.add(status="exists")
            return {
                "error": "Identity already exists in keychain. Pass force=True to overwrite.",
                "status": "exists",
            }

        identity = pyrage.x25519.Identity.generate()
        private_key = str(identity)
        public_key = str(identity.to_public())

        keyring.set_password(_SERVICE, _KEY_IDENTITY, private_key)
        keyring.set_password(_SERVICE, _KEY_PUBKEY, public_key)
        keyring.set_password(_SERVICE, _KEY_LABEL, label)

        s.add(status="stored")
        return {
            "pubkey": public_key,
            "label": label,
            "status": "stored",
        }


def encrypt(*, file: str | None = None, backup: bool = False) -> dict[str, Any]:
    """Encrypt plain values in a secrets YAML file in-place.

    Skips values already prefixed with `age1enc:`. Writes atomically at mode 0600.

    Args:
        file: Path to secrets YAML file. Defaults to the configured secrets path.
        backup: If True, create a plaintext .bak copy (mode 0600) before modifying.
            Defaults to False — an unencrypted backup on disk defeats "safe to commit".

    Returns:
        Dict with encryption summary including encrypted, skipped, and plain key lists.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.encrypt", file=str(path)) as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        _assert_secure_keyring_backend(keyring)

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        if not pubkey_str:
            s.add(status="no_identity")
            return {
                "error": _NO_IDENTITY_MSG,
                "status": "no_identity",
            }

        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {path}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="invalid_yaml")
            return {"error": "File must be a YAML mapping", "status": "invalid_yaml"}

        recipient = pyrage.x25519.Recipient.from_str(pubkey_str)

        backup_path: str | None = None
        if backup:
            backup_path = str(path) + ".bak"
            shutil.copy2(path, backup_path)
            Path(backup_path).chmod(0o600)

        encrypted_keys: list[str] = []
        skipped_keys: list[str] = []
        null_keys: list[str] = []
        updated = dict(data)

        for key, value in data.items():
            if value is None:
                null_keys.append(key)
                continue
            str_val = str(value)
            if str_val.startswith(_PREFIX):
                skipped_keys.append(key)
            else:
                ciphertext = pyrage.encrypt(str_val.encode(), [recipient])
                encoded = base64.b64encode(ciphertext).decode()
                updated[key] = _PREFIX + encoded
                encrypted_keys.append(key)

        _atomic_write_yaml(path, updated)

        s.add(encryptedCount=len(encrypted_keys), skippedCount=len(skipped_keys))
        return {
            "file": str(path),
            "backup": backup_path,
            "encrypted": encrypted_keys,
            "skipped": skipped_keys,
            "null_keys": null_keys,
            "pubkey_hint": _pubkey_hint(pubkey_str),
        }


def status(*, file: str | None = None) -> dict[str, Any]:
    """Check secrets identity status and optionally inspect a secrets file.

    Args:
        file: Optional path to secrets YAML file to count encrypted vs plain values.

    Returns:
        Dict with identity status and optional value counts.
    """
    with LogSpan(span="ot_secrets.status", file=file) as s:
        keyring = _require_keyring()

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        label = keyring.get_password(_SERVICE, _KEY_LABEL) or ""

        if not pubkey_str:
            s.add(identity="not_found")
            return {
                "identity": "not found",
                "pubkey_hint": None,
                "label": None,
                "file": None,
                "values": None,
                "hint": "Run ot_secrets.init() to generate an identity.",
            }

        result: dict[str, Any] = {
            "identity": "found",
            "pubkey_hint": _pubkey_hint(pubkey_str),
            "label": label,
            "file": None,
            "values": None,
        }

        # Resolve the secrets file to inspect: explicit file, else the configured
        # default (best-effort — an identity-only status() still works with no file).
        resolved: Path | None = None
        if file is not None:
            resolved = Path(file).expanduser()
        else:
            with contextlib.suppress(Exception):
                resolved = _resolve_secrets_file(None)

        if resolved is not None and (file is not None or resolved.exists()):
            path = resolved
            if not path.exists():
                result["file_error"] = f"File not found: {path}"
            else:
                try:
                    with path.open() as f:
                        data = yaml.safe_load(f)
                except yaml.YAMLError as exc:
                    result["file_error"] = str(exc)
                    s.add(identity="found", file_error="invalid_yaml")
                    return result
                if not isinstance(data, dict):
                    result["file_error"] = "File must be a YAML mapping"
                else:
                    encrypted = []
                    plain = []
                    nulls = []
                    # Falsy non-None values (e.g. empty string) are treated as plain,
                    # not null — they are present but unencrypted.
                    for k, v in data.items():
                        if v is None:
                            nulls.append(k)
                        elif str(v).startswith(_PREFIX):
                            encrypted.append(k)
                        else:
                            plain.append(k)
                    result["file"] = str(path)
                    result["values"] = {
                        "encrypted": encrypted,
                        "plain": plain,
                        "null_keys": nulls,
                    }

        s.add(identity="found")
        return result


def rotate(*, file: str | None = None, backup: bool = False) -> dict[str, Any]:
    """Generate a new identity and re-encrypt all encrypted values in-place.

    Plain (non-`age1enc:`) values are left unchanged.

    Args:
        file: Path to secrets YAML file. Defaults to the configured secrets path.
        backup: If True, create a plaintext .bak copy (mode 0600) before modifying.
            Defaults to False.

    Returns:
        Dict with rotation summary.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.rotate", file=str(path)) as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        _assert_secure_keyring_backend(keyring)

        old_private = keyring.get_password(_SERVICE, _KEY_IDENTITY)
        old_pubkey = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        label = keyring.get_password(_SERVICE, _KEY_LABEL) or ""

        if not old_private:
            s.add(status="no_identity")
            return {
                "error": _NO_IDENTITY_MSG,
                "status": "no_identity",
            }

        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {path}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="invalid_yaml")
            return {"error": "File must be a YAML mapping", "status": "invalid_yaml"}

        backup_path: str | None = None
        if backup:
            backup_path = str(path) + ".bak"
            shutil.copy2(path, backup_path)
            Path(backup_path).chmod(0o600)

        old_identity = pyrage.x25519.Identity.from_str(old_private)

        new_identity = pyrage.x25519.Identity.generate()
        new_private = str(new_identity)
        new_pubkey = str(new_identity.to_public())
        new_recipient = pyrage.x25519.Recipient.from_str(new_pubkey)

        rotated_keys: list[str] = []
        skipped_keys: list[str] = []
        updated = dict(data)

        for key, value in data.items():
            if value is None:
                continue
            str_val = str(value)
            if str_val.startswith(_PREFIX):
                encoded = str_val[len(_PREFIX) :]
                ciphertext = base64.b64decode(encoded, validate=True)
                plaintext = pyrage.decrypt(ciphertext, [old_identity])
                new_ciphertext = pyrage.encrypt(plaintext, [new_recipient])
                # Round-trip verify with the NEW identity before committing anything
                # to disk or the keychain (Decision 7) — abort loudly on mismatch.
                verify = pyrage.decrypt(new_ciphertext, [new_identity])
                if verify != plaintext:
                    s.add(status="verify_failed", key=key)
                    return {
                        "error": (
                            f"Rotation aborted: re-encrypted value for '{key}' failed "
                            "round-trip verification with the new identity. No changes "
                            "were written."
                        ),
                        "status": "verify_failed",
                    }
                new_encoded = base64.b64encode(new_ciphertext).decode()
                updated[key] = _PREFIX + new_encoded
                rotated_keys.append(key)
            else:
                skipped_keys.append(key)

        # Crash-safety invariant (Decision 7): write the new-key file atomically
        # FIRST, and only update the keychain to the new identity AFTER the write
        # succeeds. A crash before the write leaves the old file + old identity
        # intact; a crash after the write but before the keychain update is
        # recoverable by re-running rotate() (which fails to decrypt with the
        # mismatched identity — a clear error, not silent data loss).
        _atomic_write_yaml(path, updated)

        keyring.set_password(_SERVICE, _KEY_IDENTITY, new_private)
        keyring.set_password(_SERVICE, _KEY_PUBKEY, new_pubkey)
        keyring.set_password(_SERVICE, _KEY_LABEL, label)

        s.add(rotatedCount=len(rotated_keys), status="rotated")
        return {
            "old_pubkey_hint": _pubkey_hint(old_pubkey) if old_pubkey else None,
            "new_pubkey_hint": _pubkey_hint(new_pubkey),
            "file": str(path),
            "backup": backup_path,
            "rotated": rotated_keys,
            "skipped": skipped_keys,
            "status": "rotated",
        }


def audit(*, file: str | None = None) -> dict[str, Any]:
    """Scan a secrets YAML file for unencrypted values.

    Returns key names only — never exposes actual values.

    Args:
        file: Path to secrets YAML file. Defaults to the configured secrets path.

    Returns:
        Dict with safe status, plain_keys, and encrypted_keys.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.audit", file=str(path)) as s:
        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {path}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="no_mapping")
            return {"error": "File must be a YAML mapping", "status": "no_mapping"}

        encrypted_keys: list[str] = []
        plain_keys: list[str] = []
        null_keys: list[str] = []

        for key, value in data.items():
            if value is None:
                null_keys.append(key)
            elif str(value).startswith(_PREFIX):
                encrypted_keys.append(key)
            else:
                plain_keys.append(key)

        safe = len(plain_keys) == 0
        s.add(
            safe=safe, plain_count=len(plain_keys), encrypted_count=len(encrypted_keys)
        )
        result: dict[str, Any] = {
            "file": str(path),
            "safe": safe,
            "plain_keys": plain_keys,
            "encrypted_keys": encrypted_keys,
            "null_keys": null_keys,
        }
        if not safe:
            result["message"] = (
                "Run ot_secrets.encrypt() to secure these values before committing."
            )
        return result


def set(*, key: str, value: str, file: str | None = None) -> dict[str, Any]:
    """Set a single secret, encrypting it in place if an identity exists.

    Encrypts ``value`` in memory (never touching disk in plaintext) and round-trip
    verifies before the atomic 0600 write. If no identity is present, the value is
    stored in plaintext and a ``warning`` is returned.

    Args:
        key: Secret name.
        value: Secret value (encrypted in place when an identity exists).
        file: Path to secrets YAML file. Defaults to the configured secrets path.

    Returns:
        Dict summarising the write. Never contains the plaintext value.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.set", file=str(path), key=key) as s:
        keyring = _require_keyring()

        data: dict[str, Any] = {}
        if path.exists():
            try:
                with path.open() as f:
                    loaded = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                s.add(status="invalid_yaml")
                return {"error": str(exc), "status": "invalid_yaml"}
            if loaded is not None:
                if not isinstance(loaded, dict):
                    s.add(status="invalid_yaml")
                    return {
                        "error": "File must be a YAML mapping",
                        "status": "invalid_yaml",
                    }
                data = loaded

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        encrypted = False
        warning: str | None = None

        if pubkey_str:
            _assert_secure_keyring_backend(keyring)
            private_key = keyring.get_password(_SERVICE, _KEY_IDENTITY)
            if not private_key:
                # Keychain has the pubkey but lost the identity (e.g. keychain
                # entry deleted out-of-band) — fail with the canonical guidance
                # instead of an unhandled TypeError from Identity.from_str(None).
                s.add(status="no_identity")
                return {"error": _NO_IDENTITY_MSG, "status": "no_identity"}
            pyrage = _require_pyrage()
            recipient = pyrage.x25519.Recipient.from_str(pubkey_str)
            ciphertext = pyrage.encrypt(value.encode(), [recipient])
            encoded = base64.b64encode(ciphertext).decode()
            # Round-trip verify before writing anything.
            identity = pyrage.x25519.Identity.from_str(private_key)
            if pyrage.decrypt(ciphertext, [identity]).decode() != value:
                s.add(status="verify_failed")
                return {
                    "error": (
                        f"Round-trip verification failed for '{key}'. Nothing written."
                    ),
                    "status": "verify_failed",
                }
            data[key] = _PREFIX + encoded
            encrypted = True
        else:
            data[key] = value
            warning = (
                "No age identity found — value stored in plaintext. Run "
                "ot_secrets.init() then ot_secrets.encrypt() to secure it."
            )

        _atomic_write_yaml(path, data)
        s.add(encrypted=encrypted)
        result: dict[str, Any] = {
            "file": str(path),
            "key": key,
            "encrypted": encrypted,
            "status": "set",
        }
        if warning:
            result["warning"] = warning
        return result


def get(
    *, key: str, file: str | None = None, out_file: str | None = None
) -> dict[str, Any]:
    """Look up a secret's existence/metadata, never returning its plaintext value.

    The plaintext value is *never* placed in the returned dict, a log line, or the
    LogSpan — there is intentionally no escape hatch. To obtain the value, pass
    ``out_file`` and the decrypted value is written to that 0600 file.

    Args:
        key: Secret name.
        file: Path to secrets YAML file. Defaults to the configured secrets path.
        out_file: If given, decrypt/pass-through the value into this 0600 file.

    Returns:
        Dict with ``found``/``encrypted`` (and ``written_to`` when ``out_file`` is
        used). Never contains the value itself.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.get", file=str(path), key=key) as s:
        if not path.exists():
            s.add(found=False)
            return {"found": False, "encrypted": None}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict) or key not in data:
            s.add(found=False)
            return {"found": False, "encrypted": None}

        raw = data[key]
        raw_str = "" if raw is None else str(raw)
        is_encrypted = raw_str.startswith(_PREFIX)
        result: dict[str, Any] = {"found": True, "encrypted": is_encrypted}

        if out_file is not None:
            if is_encrypted:
                keyring = _require_keyring()
                _assert_secure_keyring_backend(keyring)
                private_key = keyring.get_password(_SERVICE, _KEY_IDENTITY)
                if not private_key:
                    s.add(status="no_identity")
                    return {"error": _NO_IDENTITY_MSG, "status": "no_identity"}
                pyrage = _require_pyrage()
                identity = pyrage.x25519.Identity.from_str(private_key)
                ciphertext = base64.b64decode(raw_str[len(_PREFIX) :], validate=True)
                plaintext = pyrage.decrypt(ciphertext, [identity]).decode()
            else:
                plaintext = raw_str
            out_path = Path(out_file).expanduser()
            fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(plaintext)
            out_path.chmod(0o600)
            result["written_to"] = str(out_path)

        s.add(found=True, encrypted=is_encrypted)
        return result
